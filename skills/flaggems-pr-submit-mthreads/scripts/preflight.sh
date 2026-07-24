#!/usr/bin/env bash
set -euo pipefail

# preflight.sh <op> [--repo-dir DIR]
# 摩尔线程特化提交前预检：worktree kernel、通用算子存在上游、摩尔线程特化不存在上游、
# 上游 test/benchmark 复用判定、git author、benchmark 数据。

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

OP="${1:?Usage: preflight.sh <op> [--repo-dir DIR]}"
shift

REPO_DIR=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo-dir) REPO_DIR="$2"; shift 2 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

REPO_DIR="${REPO_DIR:-/root/FlagGems}"
MTHREADS_OPS="src/flag_gems/runtime/backend/_mthreads/ops"
GENERIC_OPS="src/flag_gems/ops"
WORKTREE_DIR="${REPO_DIR}/.worktrees/gen-${OP}"

cd "$REPO_DIR"

PASS=0
FAIL=0
WARN=0

ok()   { echo "[✓] $1"; PASS=$((PASS + 1)); }
fail() { echo "[✗] $1"; FAIL=$((FAIL + 1)); }
warn() { echo "[!] $1"; WARN=$((WARN + 1)); }

echo "=== Preflight (摩尔线程): ${OP} ==="
echo ""

# 1. Worktree 存在
KERNEL_PATH="${WORKTREE_DIR}/${MTHREADS_OPS}/${OP}.py"
if [[ -f "$KERNEL_PATH" ]]; then
    ok "Worktree kernel: ${KERNEL_PATH##*/}"
else
    warn "Worktree kernel 不存在: $KERNEL_PATH（可能已手动准备）"
fi

# 2. 通用算子必须存在上游（摩尔线程特化覆盖通用算子）
if git show "upstream/master:${GENERIC_OPS}/${OP}.py" &>/dev/null; then
    ok "通用算子存在上游: ${GENERIC_OPS}/${OP}.py"
else
    warn "通用算子未在 upstream/master 找到 — 确认通用版已 merge，否则先提交通用版"
fi

# 3. 摩尔线程特化不能已存在上游
if git show "upstream/master:${MTHREADS_OPS}/${OP}.py" &>/dev/null; then
    fail "Upstream 已有摩尔线程特化: ${MTHREADS_OPS}/${OP}.py"
else
    ok "Upstream: 摩尔线程特化不存在（可以提交）"
fi

# 4. Test 文件（复用上游已有）
TEST_FILE="tests/test_${OP}.py"
if git show "upstream/master:${TEST_FILE}" &>/dev/null; then
    ok "Test file: upstream 已有 ${TEST_FILE} → 复用验证（不提交）"
else
    warn "Test file: upstream 无 ${TEST_FILE} → 需新建（参考 tests/test_relu.py）"
fi

# 5. Benchmark 文件（复用上游已有）
BENCH_FILE="benchmark/test_${OP}.py"
if git show "upstream/master:${BENCH_FILE}" &>/dev/null; then
    ok "Benchmark file: upstream 已有 ${BENCH_FILE} → 复用验证（不提交）"
else
    warn "Benchmark file: upstream 无 ${BENCH_FILE} → 需新建"
fi

# 6. Git author 检查
GIT_NAME="$(git config user.name 2>/dev/null || echo '')"
GIT_EMAIL="$(git config user.email 2>/dev/null || echo '')"
if [[ -n "$GIT_EMAIL" ]]; then
    ok "Git author: ${GIT_NAME} <${GIT_EMAIL}>"
else
    warn "Git author 未配置 — 设置 git config user.name / user.email"
fi

# 7. Benchmark 提示（无预生成 summary；在 worktree 现跑 pytest 获取加速比）
BENCH_LOG="${BENCH_LOG:-/tmp/${OP}_mthreads_bench.log}"
if [[ -f "$BENCH_LOG" ]]; then
    ROWS=$(grep -c "SUCCESS" "$BENCH_LOG" 2>/dev/null || echo 0)
    if [[ "$ROWS" -gt 0 ]]; then
        ok "Benchmark log: ${BENCH_LOG}（${ROWS} 条 SUCCESS 行，可用于生成 PR 表格）"
    else
        warn "Benchmark log 存在但无 SUCCESS 行: ${BENCH_LOG}"
    fi
else
    warn "Benchmark: 未找到 ${BENCH_LOG} — 需在 worktree 现跑："
    echo "      cd \$WORKTREE && MUSA_VISIBLE_DEVICES=<gpu> python3 <auto_gen>/fix_worktree_import.py \\"
    echo "          --pytest benchmark/test_${OP}.py -m ${OP} -vs | tee ${BENCH_LOG}"
fi

# 8. 规范名查询
REG_OUT=$(python3 "$SCRIPT_DIR/operator_registry.py" lookup "$OP" 2>/dev/null || echo "ERROR")
if [[ "$REG_OUT" != "ERROR" ]]; then
    echo ""
    echo "$REG_OUT"
else
    warn "operator_registry.py 执行失败（确认 openpyxl/pandas 已装、xlsx 存在）"
fi

# Summary
echo ""
echo "=== 结果: ${PASS} passed, ${FAIL} failed, ${WARN} warnings ==="

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0
