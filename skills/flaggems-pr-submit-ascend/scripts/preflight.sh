#!/usr/bin/env bash
set -euo pipefail

# preflight.sh <op> [--repo-dir DIR] [--summary PATH]
# 提交前预检：upstream 冲突、文件模式、git author、worktree、benchmark 数据
# agent 根据输出决定追加/新建测试文件
#
# 路径来自 --repo-dir / FLAGGEMS_REPO，benchmark 数据来自 --summary / FLAGGEMS_SUMMARY_JSON。
# 详见 config.sh 顶部的环境变量说明。

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=config.sh
source "$SCRIPT_DIR/config.sh"

OP="${1:?Usage: preflight.sh <op> [--repo-dir DIR] [--summary PATH]}"
shift

REPO_DIR=""
SUMMARY_ARG=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo-dir) REPO_DIR="$2"; shift 2 ;;
        --summary) SUMMARY_ARG="$2"; shift 2 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

REPO_DIR="$(resolve_repo_dir "$REPO_DIR")"
SUMMARY_JSON="$(resolve_summary_json "$SUMMARY_ARG")"
WORKTREE_DIR="${REPO_DIR}/.worktrees/gen-${OP}"

cd "$REPO_DIR"

PASS=0
FAIL=0
WARN=0

ok()   { echo "[✓] $1"; PASS=$((PASS + 1)); }
fail() { echo "[✗] $1"; FAIL=$((FAIL + 1)); }
warn() { echo "[!] $1"; WARN=$((WARN + 1)); }

echo "=== Preflight: ${OP} ==="
echo "Repo: ${REPO_DIR}"
echo ""

# 1. Worktree 存在
KERNEL_PATH="${WORKTREE_DIR}/${ASCEND_OPS}/${OP}.py"
if [[ -f "$KERNEL_PATH" ]]; then
    ok "Worktree kernel: ${KERNEL_PATH##*/}"
else
    fail "Worktree kernel 不存在: $KERNEL_PATH"
fi

# 2. Upstream 检查
UPSTREAM_REF="${UPSTREAM_REMOTE}/${BASE_BRANCH}"
if ! git rev-parse --verify --quiet "$UPSTREAM_REF" >/dev/null; then
    warn "无法解析 ${UPSTREAM_REF} —— 跳过上游冲突检查（先 git fetch ${UPSTREAM_REMOTE}）"
    SKIP_UPSTREAM=true
else
    SKIP_UPSTREAM=false
fi

if ! $SKIP_UPSTREAM; then
    if git show "${UPSTREAM_REF}:${ASCEND_OPS}/${OP}.py" &>/dev/null; then
        fail "Upstream 已有 kernel: ${ASCEND_OPS}/${OP}.py"
    else
        ok "Upstream: kernel 不存在（可以提交）"
    fi
fi

# 3. Test 文件冲突检查
TEST_FILE="tests/test_${OP}.py"
if ! $SKIP_UPSTREAM; then
    if git show "${UPSTREAM_REF}:${TEST_FILE}" &>/dev/null; then
        warn "Test file: upstream 已有 ${TEST_FILE} → 追加模式"
        echo "     已有内容预览:"
        git show "${UPSTREAM_REF}:${TEST_FILE}" 2>/dev/null | grep "^@pytest.mark\|^def test_" | head -10 | sed 's/^/     /'
    else
        ok "Test file: upstream 无 ${TEST_FILE} → 新建模式"
    fi
fi

# 4. Benchmark 文件冲突检查
BENCH_FILE="benchmark/test_${OP}.py"
if ! $SKIP_UPSTREAM; then
    if git show "${UPSTREAM_REF}:${BENCH_FILE}" &>/dev/null; then
        warn "Benchmark file: upstream 已有 ${BENCH_FILE} → 追加模式"
        echo "     已有内容预览:"
        git show "${UPSTREAM_REF}:${BENCH_FILE}" 2>/dev/null | grep "^@pytest.mark\|^def test_\|^def .*input_fn" | head -10 | sed 's/^/     /'
    else
        ok "Benchmark file: upstream 无 ${BENCH_FILE} → 新建模式"
    fi
fi

# 5. Git author 检查（只读校验，不改写 git config）
check_git_identity
case "$GIT_IDENTITY" in
    ok)
        ok "Git author: ${GIT_NAME} <${GIT_EMAIL}>"
        ;;
    missing)
        fail "Git author 未配置"
        echo "     修复: git config user.name '<name>' && git config user.email '<email>'"
        ;;
    mismatch)
        fail "Git author 不匹配: ${GIT_NAME} <${GIT_EMAIL}> (期望 $(expected_identity_desc))"
        echo "     修复: 手动 git config，或调整 FLAGGEMS_GIT_NAME / FLAGGEMS_GIT_EMAIL"
        ;;
esac

# 6. Benchmark 数据
if [[ -z "$SUMMARY_JSON" ]]; then
    warn "Benchmark: 未配置 summary.json（--summary 或 FLAGGEMS_SUMMARY_JSON），跳过"
elif [[ -f "$SUMMARY_JSON" ]]; then
    BENCH_COUNT=$("$PYTHON_BIN" - "$SUMMARY_JSON" "$OP" <<'PYEOF' 2>/dev/null || echo "ERROR"
import json
import sys

summary_path, op = sys.argv[1], sys.argv[2]
with open(summary_path) as f:
    data = json.load(f)
op_data = data.get("operators", {}).get(op, {})
if not op_data:
    print("NOT_FOUND")
    sys.exit(0)
cc = op_data.get("cc_result", {})
items = cc.get("benchmark_results", {}).get("data", [])
status = op_data.get("status", "unknown")
acc = op_data.get("accuracy_passed", False)
print(f"{len(items)}|{status}|{acc}")
PYEOF
)

    if [[ "$BENCH_COUNT" == "NOT_FOUND" ]]; then
        fail "Benchmark: summary.json 中无 ${OP}"
    elif [[ "$BENCH_COUNT" == "ERROR" ]]; then
        fail "Benchmark: 无法解析 summary.json"
    else
        IFS='|' read -r COUNT STATUS ACC <<< "$BENCH_COUNT"
        if [[ "$STATUS" == "success" && "$ACC" == "True" ]]; then
            ok "Benchmark: ${COUNT} 条记录, status=${STATUS}, accuracy=${ACC}"
        else
            warn "Benchmark: ${COUNT} 条记录, status=${STATUS}, accuracy=${ACC}"
        fi
    fi
else
    warn "Benchmark: summary.json 不存在 ($SUMMARY_JSON)"
fi

# Summary
echo ""
echo "=== 结果: ${PASS} passed, ${FAIL} failed, ${WARN} warnings ==="

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0
