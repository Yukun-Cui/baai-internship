#!/usr/bin/env bash
set -euo pipefail

# create_pr.sh <op> [--repo-dir DIR] [--summary PATH] [--dry-run]
# 生成 PR description + 创建 upstream PR + 回填链接
#
# 路径来自 --repo-dir / FLAGGEMS_REPO，benchmark 数据来自 --summary / FLAGGEMS_SUMMARY_JSON。
# fork owner 默认从 fork remote URL 推导，可用 FLAGGEMS_FORK_OWNER 覆盖。

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=config.sh
source "$SCRIPT_DIR/config.sh"

OP="${1:?Usage: create_pr.sh <op> [--repo-dir DIR] [--summary PATH] [--dry-run]}"
shift

REPO_DIR=""
SUMMARY_ARG=""
DRY_RUN=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo-dir) REPO_DIR="$2"; shift 2 ;;
        --summary) SUMMARY_ARG="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

REPO_DIR="$(resolve_repo_dir "$REPO_DIR")"
SUMMARY_JSON="$(resolve_summary_json "$SUMMARY_ARG")"

cd "$REPO_DIR"

FORK_OWNER="$(resolve_fork_owner)"

TITLE="${TITLE_PREFIX} Add ${OP} operator with Triton kernel"
BRANCH="${BRANCH_PREFIX}${OP}"

# 1. 生成 PR body
FMT_ARGS=("$SCRIPT_DIR/format_benchmark.py" "$OP" --full)
if [[ -n "$SUMMARY_JSON" ]]; then
    FMT_ARGS+=(--summary "$SUMMARY_JSON")
fi
PR_BODY=$("$PYTHON_BIN" "${FMT_ARGS[@]}" 2>/dev/null || echo "")
if [[ -z "$PR_BODY" ]]; then
    echo "WARNING: 无法生成 benchmark 数据，使用最小模板" >&2
    PR_BODY="# ${TITLE}

## Summary
Add \`${OP}\` operator Triton kernel implementation for the Ascend backend.

## Testing
- Parametrized tests for shapes × dtypes
- Validated against PyTorch CPU-FP64 reference

## Performance
(benchmark data not available)

## Files Changed
- \`${ASCEND_OPS}/${OP}.py\`: Triton kernel
- \`${ASCEND_OPS}/__init__.py\`: Register
- \`tests/test_${OP}.py\`: Accuracy tests
- \`benchmark/test_${OP}.py\`: Benchmarks
- \`conf/operators.yaml\`: Operator entry"
fi

if $DRY_RUN; then
    echo "=== DRY RUN: PR Preview ==="
    echo ""
    echo "Repo:  ${UPSTREAM_REPO}"
    echo "Title: ${TITLE}"
    echo "Head:  ${FORK_OWNER}:${BRANCH}"
    echo "Base:  ${BASE_BRANCH}"
    echo ""
    echo "--- Body ---"
    echo "$PR_BODY"
    echo "--- End ---"
    exit 0
fi

if ! command -v gh &>/dev/null; then
    echo "ERROR: 未找到 gh CLI，无法创建 PR。" >&2
    echo "  安装: https://cli.github.com/  然后 gh auth login" >&2
    echo "  或用 --dry-run 生成 PR body 后手动提交" >&2
    exit 1
fi

# 2. 创建 PR
echo "[*] 创建 PR to ${UPSTREAM_REPO} (${FORK_OWNER}:${BRANCH} → ${BASE_BRANCH})..."
PR_URL=$(gh pr create \
    --repo "$UPSTREAM_REPO" \
    --head "${FORK_OWNER}:${BRANCH}" \
    --base "$BASE_BRANCH" \
    --title "$TITLE" \
    --body "$PR_BODY" 2>&1)

echo "[✓] PR 创建成功: ${PR_URL}"

# 3. 回填链接
echo "[*] 回填 PR 链接..."
if ! skill_python "$SCRIPT_DIR/operator_registry.py" backfill "$OP" "$PR_URL"; then
    echo "[!] 回填失败，请手动执行:" >&2
    echo "    ${PYTHON_BIN} ${SCRIPT_DIR}/operator_registry.py backfill ${OP} ${PR_URL}" >&2
fi

echo ""
echo "=== create_pr 完成 ==="
echo "PR: ${PR_URL}"
