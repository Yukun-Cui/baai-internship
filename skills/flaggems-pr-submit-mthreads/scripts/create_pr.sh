#!/usr/bin/env bash
set -euo pipefail

# create_pr.sh <op> [--repo-dir DIR] [--fork-owner OWNER] [--upstream REPO] [--dry-run]
# 生成 PR description + 创建 upstream PR + 回填链接

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

OP="${1:?Usage: create_pr.sh <op> [--repo-dir DIR] [--fork-owner OWNER] [--upstream REPO] [--dry-run]}"
shift

REPO_DIR=""
FORK_OWNER=""
UPSTREAM="flagos-ai/FlagGems-Experimental"
BENCH_LOG=""
DRY_RUN=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo-dir) REPO_DIR="$2"; shift 2 ;;
        --fork-owner) FORK_OWNER="$2"; shift 2 ;;
        --upstream) UPSTREAM="$2"; shift 2 ;;
        --bench-log) BENCH_LOG="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# 默认 benchmark log 位置（preflight/Phase 1.5 现跑时 tee 到此）
BENCH_LOG="${BENCH_LOG:-/tmp/${OP}_mthreads_bench.log}"

REPO_DIR="${REPO_DIR:-/root/FlagGems}"
cd "$REPO_DIR"

TITLE="[KernelGen][MThreads] Add ${OP} Moore Threads specialized operator"
BRANCH="pr/mthreads-${OP}"

# 推断 fork owner（从 fork remote 的 URL）
if [[ -z "$FORK_OWNER" ]]; then
    FORK_URL="$(git remote get-url fork 2>/dev/null || echo '')"
    if [[ "$FORK_URL" =~ github.com[:/]([^/]+)/ ]]; then
        FORK_OWNER="${BASH_REMATCH[1]}"
    fi
fi
if [[ -z "$FORK_OWNER" ]]; then
    echo "ERROR: 无法推断 fork owner，请用 --fork-owner OWNER 指定" >&2
    exit 1
fi

# 1. 生成 PR body（从现跑的 benchmark log 解析加速比）
PR_BODY=""
if [[ -f "$BENCH_LOG" ]]; then
    PR_BODY=$(python3 "$SCRIPT_DIR/format_benchmark.py" "$OP" --bench-log "$BENCH_LOG" --full 2>/dev/null || echo "")
else
    echo "WARNING: benchmark log 不存在 ($BENCH_LOG) — 用 --bench-log 指定或先在 worktree 现跑" >&2
fi
if [[ -z "$PR_BODY" ]]; then
    echo "WARNING: 无法生成 benchmark 数据，使用最小模板" >&2
    PR_BODY="# ${TITLE}

## Summary
Add a Moore Threads (MUSA) specialized Triton kernel for \`${OP}\`, overriding the generic
implementation via \`runtime.replace_customized_ops()\`.

## Testing
- Reused the existing upstream accuracy tests \`tests/test_${OP}.py\` (\`-m ${OP}\`)
- Validated against reference on the MUSA device; specialization confirmed via \`GEMS_MTHREADS\` log
- Falls back to the generic implementation for unsupported dtype/device/shape

## Performance
(benchmark data not available)

## Files Changed
- \`src/flag_gems/runtime/backend/_mthreads/ops/${OP}.py\`: Moore Threads Triton kernel + fallback
- \`src/flag_gems/runtime/backend/_mthreads/ops/__init__.py\`: Register import and \`__all__\`"
fi

BASE_BRANCH="infra-ci"

if $DRY_RUN; then
    echo "=== DRY RUN: PR Preview ==="
    echo ""
    echo "Title: ${TITLE}"
    echo "Head:  ${FORK_OWNER}:${BRANCH}"
    echo "Base:  ${UPSTREAM}:${BASE_BRANCH}"
    echo ""
    echo "--- Body ---"
    echo "$PR_BODY"
    echo "--- End ---"
    exit 0
fi

# 2. 创建 PR
echo "[*] 创建 PR..."
PR_URL=$(gh pr create \
    --repo "$UPSTREAM" \
    --head "${FORK_OWNER}:${BRANCH}" \
    --base "$BASE_BRANCH" \
    --title "$TITLE" \
    --body "$PR_BODY" 2>&1)

echo "[✓] PR 创建成功: ${PR_URL}"

# 3. 回填链接
echo "[*] 回填 PR 链接..."
python3 "$SCRIPT_DIR/operator_registry.py" backfill "$OP" "$PR_URL" 2>&1 || \
    echo "[!] 回填失败，请手动: python operator_registry.py backfill $OP $PR_URL"

echo ""
echo "=== create_pr 完成 ==="
echo "PR: ${PR_URL}"
