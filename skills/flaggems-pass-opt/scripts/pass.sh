#!/usr/bin/env bash
#
# pass.sh —— 用编译器优化 Pass 驱动 FlagGems 算子优化 的统一入口
#
# 用法:
#   pass.sh gpu                               # 打印并返回最闲置 GPU index
#   pass.sh reinstall                         # git pull FlagTree 后重装 flagtree
#   pass.sh restart                           # git pull FlagGems 后重建 FlagGems-opt
#   pass.sh test    -g <op> [-c <dev|auto>] [-k <expr>]   # 跑 A/B benchmark
#   pass.sh all     -g <op> [-c <dev|auto>] [-k <expr>]   # restart 后跑 A/B benchmark
#
# 说明:
#   -g/--gem     算子名（对应 benchmark/test_<op>.py），默认 var
#   -c/--cuda    GPU index；传 auto 或省略则自动挑最闲置的卡
#   -k/--keyword 透传给 pytest 的 -k 表达式；用于过滤掉与优化无关、
#                因环境（如 torch 预发布版缺 overload）导致的伪失败用例，
#                例如 addmm 需 -k "not dtype" 绕开 aten.addmm.dtype 伪失败

set -euo pipefail

BASE_DIR="/root/pass"

# ----------------------------------------------------------------------------
# 选最闲置 GPU：按 (利用率, 已用显存) 升序，取第一张，回显 index 到 stdout
# ----------------------------------------------------------------------------
pick_idle_gpu() {
    local info idx used total util
    info=$(nvidia-smi \
        --query-gpu=index,memory.used,memory.total,utilization.gpu \
        --format=csv,noheader,nounits \
        | tr -d ' ' \
        | sort -t ',' -k 4,4n -k 2,2n \
        | head -n 1)

    idx=$(echo "$info"   | cut -d ',' -f 1)
    used=$(echo "$info"  | cut -d ',' -f 2)
    total=$(echo "$info" | cut -d ',' -f 3)
    util=$(echo "$info"  | cut -d ',' -f 4)

    echo "✅ 锁定最闲置 GPU: ID ${idx} | 显存 ${used}MB/${total}MB | 利用率 ${util}%" >&2
    echo "$idx"
}

cmd_gpu() {
    local idx
    idx=$(pick_idle_gpu)
    export CUDA_VISIBLE_DEVICES="$idx"
    echo "🚀 已设置 CUDA_VISIBLE_DEVICES=${idx}" >&2
    echo "$idx"
}

# ----------------------------------------------------------------------------
# 重装 flagtree 编译器（改了编译器本身后用）
# ----------------------------------------------------------------------------
cmd_reinstall() {
    cd "${BASE_DIR}/FlagTree"
    git reset --hard HEAD
    git pull
    TARGET_FILE="python/src/ir.cc"
    sed -i 's/\/\*printAfterOnlyOnChange=\*\/false,/\/\*printAfterOnlyOnChange=\*\/true,/g' "$TARGET_FILE"
    sed -i 's/\/\*printAfterOnlyOnFailure\*\/ true,/\/\*printAfterOnlyOnFailure\*\/ false,/g' "$TARGET_FILE"
    git --no-pager diff

    apt update
    apt install zlib1g zlib1g-dev libxml2 libxml2-dev nlohmann-json3-dev
    pip install -r python/requirements.txt
    # rm -rf /root/.triton
    pip install . --no-build-isolation -v
}

# ----------------------------------------------------------------------------
# 重建干净的 FlagGems-opt（会 rm -rf 掉旧的 FlagGems-opt，清空未归档改动）
# ----------------------------------------------------------------------------
cmd_restart() {
    cd "${BASE_DIR}/FlagGems"
    git pull
    rm -rf "${BASE_DIR}/FlagGems-opt"
    cp -r "${BASE_DIR}/FlagGems" "${BASE_DIR}/FlagGems-opt"
    echo "✅ 已重建干净的 FlagGems-opt"
}

# ----------------------------------------------------------------------------
# A/B benchmark harness
# ----------------------------------------------------------------------------
run_one() {
    local label="$1" dir="$2" gem="$3" kexpr="$4"
    local log_dir="${BASE_DIR}/logs/${gem}"
    local log="${log_dir}/${label}.benchmark"
    local dump="${log_dir}/${label}.dump"
    local diff="${BASE_DIR}/diff/${gem}.diff"
    local bench="benchmark/test_${gem}.py"

    # -k 表达式作为单个参数安全传给 pytest（避免 "not dtype" 被词分割）
    local -a kflag=()
    [[ -n "${kexpr}" ]] && kflag=(-k "${kexpr}")

    echo "=================================================================="
    echo " [${label}] ${dir}"
    echo " GPU : CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES}"
    echo " log : ${log}"
    echo " dump: ${dump}"
    echo "=================================================================="

    cd "${dir}"

    if [[ "${label}" == "opt" ]]; then
        echo "git apply ${diff} ..."
        git apply "${diff}"
        git diff > "${log_dir}/changes.diff" 2>&1
    fi

    echo "pip reinstall flag_gems ..."
    pip uninstall -y flag_gems > /dev/null 2>&1 || true
    pip install -e . > /dev/null 2>&1

    python -c "import flag_gems, os; print('flag_gems from:', os.path.dirname(flag_gems.__file__))" > "${log}" 2>&1

    echo "run MLIR_ENABLE_DUMP=1 ..."
    rm -rf ~/.triton/cache
    MLIR_ENABLE_DUMP=1 pytest "${bench}" "${kflag[@]}" -s -x --level core --dtypes float16 --warmup 0 --iter 1 > /dev/null 2> "${dump}" || true

    echo "run benchmark ..."
    rm -rf ~/.triton/cache
    pytest "${bench}" "${kflag[@]}" -s -x >> "${log}" 2>&1 || true
}

cmd_test() {
    local gem="$1" dev="$2" kexpr="${3:-}"

    if [[ "${dev}" == "auto" ]]; then
        dev=$(pick_idle_gpu)
    fi
    export CUDA_VISIBLE_DEVICES="${dev}"

    local log_dir="${BASE_DIR}/logs/${gem}"
    mkdir -p "${log_dir}"

    echo "### Optimization OFF (baseline) ###"
    run_one "orig" "${BASE_DIR}/FlagGems" "${gem}" "${kexpr}"

    echo
    echo "### Optimization ON (pass-applied) ###"
    run_one "opt" "${BASE_DIR}/FlagGems-opt" "${gem}" "${kexpr}"

    echo
    echo "=================================================================="
    echo " Done. Logs:"
    echo "   baseline-benchmark  : ${log_dir}/orig.benchmark"
    echo "   optimized-benchmark : ${log_dir}/opt.benchmark"
    echo "   baseline-dump       : ${log_dir}/orig.dump"
    echo "   optimized-dump      : ${log_dir}/opt.dump"
    echo "   git diff            : ${log_dir}/changes.diff"
    echo "=================================================================="
}

# ----------------------------------------------------------------------------
# 参数解析 + 分发
# ----------------------------------------------------------------------------
usage() {
    sed -n '3,25p' "$0"
    exit "${1:-0}"
}

main() {
    local sub="${1:-}"
    [[ $# -gt 0 ]] && shift || true

    local gem="var" dev="auto" kexpr=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -g|--gem)     gem="$2";   shift 2 ;;
            -c|--cuda)    dev="$2";   shift 2 ;;
            -k|--keyword) kexpr="$2"; shift 2 ;;
            -h|--help) usage 0 ;;
            *) echo "未知参数: $1" >&2; usage 1 ;;
        esac
    done

    case "${sub}" in
        gpu)       cmd_gpu ;;
        reinstall) cmd_reinstall ;;
        restart)   cmd_restart ;;
        test)      cmd_test "${gem}" "${dev}" "${kexpr}" ;;
        all)       cmd_restart; cmd_test "${gem}" "${dev}" "${kexpr}" ;;
        ""|-h|--help) usage 0 ;;
        *) echo "未知子命令: ${sub}" >&2; usage 1 ;;
    esac
}

main "$@"
