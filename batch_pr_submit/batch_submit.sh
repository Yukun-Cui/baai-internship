#!/bin/bash
# Batch parallel PR submission script.
# Reads operator list, creates independent git worktrees, submits PRs in parallel.
# Each operator produces a JSON record and a text log (no stdout streaming).
#
# Usage:
#   ./batch_submit.sh                          # defaults: 8 parallel, default list
#   ./batch_submit.sh -j 4                     # 4 parallel jobs
#   ./batch_submit.sh -l /path/to/list.txt     # custom operator list
#   ./batch_submit.sh --start 5 --end 10       # only operators at lines 5-10
#   ./batch_submit.sh --dry-run                # show plan without executing

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.env"

# --- Parse arguments ---
PARALLEL_JOBS="$MAX_PARALLEL"
INPUT_LIST="$OP_LIST"
START_LINE=1
END_LINE=99999
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        -j|--jobs)      PARALLEL_JOBS="$2"; shift 2 ;;
        -l|--list)      INPUT_LIST="$2"; shift 2 ;;
        --start)        START_LINE="$2"; shift 2 ;;
        --end)          END_LINE="$2"; shift 2 ;;
        --dry-run)      DRY_RUN=true; shift ;;
        -h|--help)
            echo "Usage: $0 [-j N] [-l list.txt] [--start N] [--end N] [--dry-run]"
            exit 0 ;;
        *)              echo "Unknown option: $1"; exit 1 ;;
    esac
done

# --- Validate inputs ---
if [[ ! -f "$INPUT_LIST" ]]; then
    echo "[ERROR] Operator list not found: $INPUT_LIST"
    exit 1
fi

if ! $DRY_RUN && [[ -z "${GH_TOKEN:-}" ]]; then
    echo "[ERROR] GH_TOKEN is not set. Export a GitHub token before starting."
    exit 1
fi

# --- Detect available GPUs ---
if command -v nvidia-smi &>/dev/null; then
    GPU_COUNT=$(nvidia-smi -L 2>/dev/null | wc -l)
else
    GPU_COUNT=1
fi

if [[ "$PARALLEL_JOBS" -gt "$GPU_COUNT" ]]; then
    echo "[WARN] Requested $PARALLEL_JOBS parallel jobs but only $GPU_COUNT GPUs detected. Capping at $GPU_COUNT."
    PARALLEL_JOBS="$GPU_COUNT"
fi

# --- Create timestamped log directory ---
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
RUN_LOG_DIR="$LOG_DIR/$TIMESTAMP"
mkdir -p "$RUN_LOG_DIR"

# --- Load operator list (trim blanks) ---
mapfile -t ALL_OPS < <(sed -n "${START_LINE},${END_LINE}p" "$INPUT_LIST" | sed '/^[[:space:]]*$/d')
TOTAL=${#ALL_OPS[@]}

echo "============================================================"
echo " Batch PR Submit"
echo " Time:       $TIMESTAMP"
echo " List:       $INPUT_LIST"
echo " Operators:  $TOTAL (lines $START_LINE-$END_LINE)"
echo " Parallel:   $PARALLEL_JOBS (GPUs: $GPU_COUNT)"
echo " Log dir:    $RUN_LOG_DIR"
echo "============================================================"

# --- 断点续跑: collect previously succeeded operators from JSON records ---
declare -A DONE_OPS
for prev_json in "$LOG_DIR"/*//*.json; do
    [[ -f "$prev_json" ]] || continue
    prev_status=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('status',''))" "$prev_json" 2>/dev/null) || continue
    if [[ "$prev_status" == "success" ]]; then
        prev_op=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('operator',''))" "$prev_json" 2>/dev/null) || continue
        DONE_OPS["$prev_op"]=1
    fi
done

# Filter out already-done operators
OPS_TO_RUN=()
SKIPPED_OPS=()
for op in "${ALL_OPS[@]}"; do
    if [[ -n "${DONE_OPS[$op]:-}" ]]; then
        SKIPPED_OPS+=("$op")
    else
        OPS_TO_RUN+=("$op")
    fi
done

if [[ ${#SKIPPED_OPS[@]} -gt 0 ]]; then
    echo "[SKIP] ${#SKIPPED_OPS[@]} already-submitted: ${SKIPPED_OPS[*]}"
fi

RUN_COUNT=${#OPS_TO_RUN[@]}
echo "[INFO] Will submit $RUN_COUNT operators"
echo ""

if $DRY_RUN; then
    echo "[DRY-RUN] Would submit:"
    for i in "${!OPS_TO_RUN[@]}"; do
        gpu_id=$((i % GPU_COUNT))
        echo "  [$((i+1))/$RUN_COUNT] ${OPS_TO_RUN[$i]} -> GPU $gpu_id"
    done
    exit 0
fi

if [[ $RUN_COUNT -eq 0 ]]; then
    echo "[INFO] Nothing to submit. All operators already done."
    exit 0
fi

# --- Ensure worktree base dir exists ---
mkdir -p "$WORKTREE_BASE_DIR"

# --- Pre-fetch upstream once (avoid parallel lock contention on .git) ---
echo "[PREP] Fetching upstream/master..."
cd "$REPO_DIR"
fetch_ok=false
for attempt in 1 2 3; do
    if git fetch upstream master --quiet; then
        fetch_ok=true
        break
    fi
    echo "[WARN] git fetch upstream master failed (attempt $attempt/3); retrying..."
    sleep $((attempt * 5))
done
if ! $fetch_ok; then
    echo "[ERROR] git fetch upstream master failed"
    exit 1
fi
echo "[PREP] Fetch done."

# --- Export for child processes ---
export GH_TOKEN

# --- Run in parallel with GPU assignment ---
declare -A PIDS
declare -A GPU_MAP
declare -A OP_MAP
RUNNING=0
SUCCESS_COUNT=0
FAIL_COUNT=0
IDX=0

assign_gpu() {
    for ((g=0; g<GPU_COUNT; g++)); do
        local in_use=false
        for pid in "${!GPU_MAP[@]}"; do
            if [[ "${GPU_MAP[$pid]}" == "$g" ]] && kill -0 "$pid" 2>/dev/null; then
                in_use=true
                break
            fi
        done
        if ! $in_use; then
            echo "$g"
            return
        fi
    done
    echo "-1"
}

collect_finished() {
    for pid in "${!PIDS[@]}"; do
        if ! kill -0 "$pid" 2>/dev/null; then
            wait "$pid" 2>/dev/null
            local exit_code=$?
            local op_name="${PIDS[$pid]}"
            local gpu="${GPU_MAP[$pid]}"

            if [[ $exit_code -eq 0 ]]; then
                echo "  [OK]   $op_name (GPU $gpu)"
                ((SUCCESS_COUNT++))
            else
                echo "  [FAIL] $op_name (GPU $gpu) — see ${op_name}.log"
                ((FAIL_COUNT++))
            fi

            unset "PIDS[$pid]"
            unset "GPU_MAP[$pid]"
            ((RUNNING--))
        fi
    done
}

wait_for_slot() {
    while [[ $RUNNING -ge $PARALLEL_JOBS ]]; do
        collect_finished
        if [[ $RUNNING -ge $PARALLEL_JOBS ]]; then
            sleep 2
        fi
    done
}

# Main loop
for op in "${OPS_TO_RUN[@]}"; do
    wait_for_slot

    gpu_id=$(assign_gpu)
    while [[ "$gpu_id" == "-1" ]]; do
        collect_finished
        sleep 2
        gpu_id=$(assign_gpu)
    done

    ((IDX++))
    echo "[${IDX}/${RUN_COUNT}] Starting: $op (GPU $gpu_id)"

    bash "$SCRIPT_DIR/submit_one.sh" "$op" "$gpu_id" "$RUN_LOG_DIR" &
    local_pid=$!
    PIDS[$local_pid]="$op"
    GPU_MAP[$local_pid]="$gpu_id"
    ((RUNNING++))
done

# Wait for all remaining jobs
while [[ $RUNNING -gt 0 ]]; do
    collect_finished
    if [[ $RUNNING -gt 0 ]]; then
        sleep 2
    fi
done

# --- Generate summary.md from JSON records ---
SUMMARY_FILE="$RUN_LOG_DIR/summary.md"
{
    echo "# Batch PR Submit Summary"
    echo ""
    echo "- **Time**: $TIMESTAMP"
    echo "- **List**: $INPUT_LIST"
    echo "- **Parallel**: $PARALLEL_JOBS"
    echo "- **Total in list**: $TOTAL"
    echo "- **Skipped (already done)**: ${#SKIPPED_OPS[@]}"
    echo "- **Submitted**: $RUN_COUNT"
    echo "- **Success**: $SUCCESS_COUNT"
    echo "- **Failed**: $FAIL_COUNT"
    echo ""
    echo "## Results"
    echo ""
    echo "| Operator | Status | Duration(s) | GPU | Phase Failed | Error |"
    echo "|----------|--------|-------------|-----|--------------|-------|"

    for json_file in "$RUN_LOG_DIR"/*.json; do
        [[ -f "$json_file" ]] || continue
        python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
phase = d.get('phase_failed') or ''
err = d.get('error_summary') or ''
print(f\"| {d['operator']} | {d['status']} | {d['duration_seconds']} | {d['gpu']} | {phase} | {err} |\")
" "$json_file"
    done

    if [[ ${#SKIPPED_OPS[@]} -gt 0 ]]; then
        echo ""
        echo "## Skipped (previously submitted)"
        echo ""
        for op in "${SKIPPED_OPS[@]}"; do
            echo "- $op"
        done
    fi
} > "$SUMMARY_FILE"

echo ""
echo "============================================================"
echo " COMPLETE"
echo " Success: $SUCCESS_COUNT / $RUN_COUNT"
echo " Failed:  $FAIL_COUNT / $RUN_COUNT"
echo " Skipped: ${#SKIPPED_OPS[@]} (previously done)"
echo " Summary: $SUMMARY_FILE"
echo "============================================================"
