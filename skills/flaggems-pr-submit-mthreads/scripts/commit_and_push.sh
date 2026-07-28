#!/usr/bin/env bash
set -euo pipefail

# commit_and_push.sh <op> [--repo-dir DIR] [--fork REMOTE] [--dry-run]
# 验证分支 + stage 摩尔线程特化文件（通常 2 个）+ commit（无 AI 署名）+ push to fork

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

OP="${1:?Usage: commit_and_push.sh <op> [--repo-dir DIR] [--fork REMOTE] [--dry-run]}"
shift

REPO_DIR=""
FORK="fork"
DRY_RUN=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo-dir) REPO_DIR="$2"; shift 2 ;;
        --fork) FORK="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

REPO_DIR="${REPO_DIR:-/root/FlagGems}"
MTHREADS_OPS="src/flag_gems/runtime/backend/_mthreads/ops"

cd "$REPO_DIR"

# 1. 验证分支
BRANCH="$(git branch --show-current)"
EXPECTED="pr/mthreads-${OP}"
if [[ "$BRANCH" != "$EXPECTED" ]]; then
    echo "ERROR: 当前分支 ${BRANCH}, 期望 ${EXPECTED}" >&2
    exit 1
fi
echo "[✓] 分支: ${BRANCH}"

# 2. 要 stage 的文件（kernel + __init__ 必须；test/benchmark 仅当上游缺失需新建时才提交）
FILES=(
    "${MTHREADS_OPS}/${OP}.py"
    "${MTHREADS_OPS}/__init__.py"
)
for extra in "tests/test_${OP}.py" "benchmark/test_${OP}.py"; do
    # 只在该文件相对 upstream/infra-ci 有改动时才纳入（新建/修改）
    if git status --porcelain "$extra" 2>/dev/null | grep -q .; then
        if ! git show "upstream/infra-ci:${extra}" &>/dev/null; then
            echo "[!] ${extra} 是新建文件（上游无）→ 纳入提交"
            FILES+=("$extra")
        else
            echo "[!] 警告: ${extra} 有改动但上游已存在 — 摩尔线程特化不应修改上游测试，请检查！"
        fi
    fi
done

# 检查必需文件存在
for f in "${FILES[@]}"; do
    if [[ ! -f "$f" ]]; then
        echo "ERROR: 文件不存在: $f" >&2
        exit 1
    fi
done
echo "[✓] ${#FILES[@]} 个文件全部存在: ${FILES[*]}"

# 3. 检查是否有不该提交的改动
PATTERN="^${MTHREADS_OPS}/\|^tests/test_${OP}\.py\|^benchmark/test_${OP}\.py"
DIRTY=$(git diff --name-only 2>/dev/null | grep -v "$PATTERN" || true)
if [[ -n "$DIRTY" ]]; then
    echo "[!] 警告: 以下文件有改动但不在提交范围:"
    echo "$DIRTY" | sed 's/^/     /'
fi

COMMIT_MSG="[KernelGen][MThreads] Add ${OP} Moore Threads specialized operator"

if $DRY_RUN; then
    echo ""
    echo "[DRY RUN] 将要执行:"
    echo "  git add ${FILES[*]}"
    echo "  git commit -m '${COMMIT_MSG}'"
    echo "  git push ${FORK} ${EXPECTED}"
    exit 0
fi

# 4. Stage（逐文件，禁止 git add -A）
git add "${FILES[@]}"
echo "[✓] Staged ${#FILES[@]} files"

# 5. Commit（无 Co-Authored-By / AI 署名）
git commit -m "$COMMIT_MSG"
echo "[✓] Committed: ${COMMIT_MSG}"

AUTHOR="$(git log -1 --format='%an <%ae>')"
echo "[✓] Author: ${AUTHOR}"

# 6. Push
if git push -u "$FORK" "$EXPECTED" 2>&1; then
    echo "[✓] Pushed to ${FORK}/${EXPECTED}"
else
    echo "[!] Push 失败，如需覆盖请手动: git push ${FORK} ${EXPECTED} --force"
    exit 1
fi

echo ""
echo "=== commit_and_push 完成 ==="
