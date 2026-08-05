#!/bin/bash
# Submit a single operator PR by running the authoritative flaggems-pr-submit skill scripts.
# Uses git worktree for isolation. PR title/body/gh pr create are owned by submit_operator.py.
#
# Usage: submit_one.sh <op_name> <cuda_device> <run_log_dir>
#
# Produces:
#   <run_log_dir>/<op_name>.log   — full script output log
#   <run_log_dir>/<op_name>.json  — structured result record

set -uo pipefail

OP_NAME="$1"
CUDA_DEVICE="$2"
RUN_LOG_DIR="$3"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.env"

export GH_TOKEN
export CUDA_VISIBLE_DEVICES="$CUDA_DEVICE"

LOG_FILE="$RUN_LOG_DIR/${OP_NAME}.log"
JSON_FILE="$RUN_LOG_DIR/${OP_NAME}.json"

START_TIME=$(date '+%Y-%m-%dT%H:%M:%S')
START_EPOCH=$(date +%s)

WORKTREE_DIR="$WORKTREE_BASE_DIR/wt_${OP_NAME}_$$"
BRANCH_NAME="pr/$OP_NAME"

GIT_LOCK="$REPO_DIR/.git/batch_pr.lock"

write_json() {
    local status="$1"
    local phase_failed="${2:-}"
    local error_summary="${3:-}"
    local pr_url="${4:-}"
    local end_time=$(date '+%Y-%m-%dT%H:%M:%S')
    local end_epoch=$(date +%s)
    local duration=$((end_epoch - START_EPOCH))
    python3 -c "
import json, sys
d = {
    'operator': sys.argv[1],
    'status': sys.argv[2],
    'phase_failed': sys.argv[3] if sys.argv[3] else None,
    'error_summary': sys.argv[4] if sys.argv[4] else None,
    'pr_url': sys.argv[5] if sys.argv[5] else None,
    'gpu': int(sys.argv[6]),
    'start_time': sys.argv[7],
    'end_time': sys.argv[8],
    'duration_seconds': int(sys.argv[9]),
    'log_file': sys.argv[10]
}
json.dump(d, open(sys.argv[11], 'w'), indent=2, ensure_ascii=False)
" "$OP_NAME" "$status" "$phase_failed" "$error_summary" "$pr_url" \
  "$CUDA_DEVICE" "$START_TIME" "$end_time" "$duration" \
  "${OP_NAME}.log" "$JSON_FILE"
}

cleanup() {
    (
        flock -w 30 200 || true
        cd "$REPO_DIR"
        if [[ -d "$WORKTREE_DIR" ]]; then
            git worktree remove --force "$WORKTREE_DIR" 2>/dev/null || rm -rf "$WORKTREE_DIR"
        fi
        git branch -D "$BRANCH_NAME" 2>/dev/null || true
    ) 200>"$GIT_LOCK"
}
trap cleanup EXIT

# --- Phase 1: Create worktree (locked) ---
mkdir -p "$WORKTREE_BASE_DIR"
(
    flock -w 120 200 || { echo "Could not acquire git lock" >> "$LOG_FILE"; write_json "failed" "Phase 1" "git lock timeout"; exit 1; }
    cd "$REPO_DIR"
    git worktree remove --force "$WORKTREE_DIR" 2>/dev/null || true
    git branch -D "$BRANCH_NAME" 2>/dev/null || true
    git worktree add -b "$BRANCH_NAME" "$WORKTREE_DIR" "${UPSTREAM_REMOTE}/${BASE_BRANCH}" --quiet
) 200>"$GIT_LOCK"

if [[ $? -ne 0 ]]; then
    write_json "failed" "Phase 1" "Could not create worktree"
    exit 1
fi

# Symlink source worktrees so extract_from_worktree.py can find gen-<op>
ln -sf "$REPO_DIR/.worktrees" "$WORKTREE_DIR/.worktrees"

# Setup push remote in worktree
cd "$WORKTREE_DIR"
git remote set-url origin "https://${GH_TOKEN}@github.com/${FORK_REPO}.git" 2>/dev/null || true

# ============================================================================
# Phase 2: operator_registry.py lookup
# ============================================================================
echo "=== Phase 2: operator_registry.py lookup ===" >> "$LOG_FILE"
if ! python "$SCRIPTS_DIR/operator_registry.py" lookup "$OP_NAME" >> "$LOG_FILE" 2>&1; then
    write_json "failed" "Phase 2" "operator_registry.py lookup failed"
    exit 1
fi

# ============================================================================
# Phase 3: extract_from_worktree.py
# ============================================================================
echo "=== Phase 3: extract_from_worktree.py ===" >> "$LOG_FILE"
if ! python "$SCRIPTS_DIR/extract_from_worktree.py" "$OP_NAME" --repo-dir "$WORKTREE_DIR" >> "$LOG_FILE" 2>&1; then
    write_json "failed" "Phase 3" "extract_from_worktree.py failed"
    exit 1
fi

# ============================================================================
# Phase 4-7: submit_operator.py (validate, test, benchmark, commit, push, PR, backfill)
#   submit_operator.py 串行执行 9 步，任何一步失败立即 exit(1)。
#   PR title/body/gh pr create 完全由 submit_operator.py 内部完成，
#   batch 层不参与 PR 描述生成。
# ============================================================================
echo "=== Phase 4-7: submit_operator.py ===" >> "$LOG_FILE"
SUBMIT_OUTPUT=$(python "$SCRIPTS_DIR/submit_operator.py" "$OP_NAME" \
    --repo-dir "$WORKTREE_DIR" \
    --gpu "$CUDA_DEVICE" \
    --base "$BASE_BRANCH" \
    --token "$GH_TOKEN" 2>&1)
SUBMIT_EXIT=$?
echo "$SUBMIT_OUTPUT" >> "$LOG_FILE"

if [[ $SUBMIT_EXIT -eq 0 ]]; then
    # Extract PR URL from submit_operator.py output
    PR_URL=$(echo "$SUBMIT_OUTPUT" | grep -oP 'PR:\s*\Khttps://github\.com/[^/]+/[^/]+/pull/\d+' | tail -1)
    write_json "success" "" "" "$PR_URL"
    exit 0
else
    FAIL_REASON=$(echo "$SUBMIT_OUTPUT" | grep -iE "FATAL" | tail -1 | sed 's/\x1b\[[0-9;]*m//g' | head -c 200)
    if [[ -z "$FAIL_REASON" ]]; then
        FAIL_REASON="submit_operator.py exited with code $SUBMIT_EXIT"
    fi
    write_json "failed" "Phase 4-7" "$FAIL_REASON"
    exit 1
fi
