#!/usr/bin/env bash
set -euo pipefail

# commit_and_push.sh <op> [--repo-dir DIR] [--dry-run]
# 验证 author + stage 5 文件 + commit + push to fork
#
# 路径来自 --repo-dir / FLAGGEMS_REPO。详见 config.sh 顶部的环境变量说明。

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=config.sh
source "$SCRIPT_DIR/config.sh"

OP="${1:?Usage: commit_and_push.sh <op> [--repo-dir DIR] [--dry-run]}"
shift

REPO_DIR=""
DRY_RUN=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo-dir) REPO_DIR="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

REPO_DIR="$(resolve_repo_dir "$REPO_DIR")"

cd "$REPO_DIR"

# 1. 验证 git author（只读校验 —— 不改写用户的 git config）
check_git_identity
case "$GIT_IDENTITY" in
    ok)
        echo "[✓] Git author: ${GIT_NAME} <${GIT_EMAIL}>"
        ;;
    missing)
        echo "ERROR: git 提交身份未配置" >&2
        echo "  修复: git config user.name '<name>' && git config user.email '<email>'" >&2
        exit 1
        ;;
    mismatch)
        echo "ERROR: git author 不匹配: ${GIT_NAME} <${GIT_EMAIL}>" >&2
        echo "  期望: $(expected_identity_desc)" >&2
        echo "  修复: 手动 git config，或调整 FLAGGEMS_GIT_NAME / FLAGGEMS_GIT_EMAIL" >&2
        exit 1
        ;;
esac

# 2. 验证分支
BRANCH="$(git branch --show-current)"
EXPECTED="${BRANCH_PREFIX}${OP}"
if [[ "$BRANCH" != "$EXPECTED" ]]; then
    echo "ERROR: 当前分支 ${BRANCH}, 期望 ${EXPECTED}" >&2
    exit 1
fi
echo "[✓] 分支: ${BRANCH}"

# 3. 定义要 stage 的文件
FILES=(
    "${ASCEND_OPS}/${OP}.py"
    "${ASCEND_OPS}/__init__.py"
    "tests/test_${OP}.py"
    "benchmark/test_${OP}.py"
    "conf/operators.yaml"
)

# 检查文件存在
for f in "${FILES[@]}"; do
    if [[ ! -f "$f" ]]; then
        echo "ERROR: 文件不存在: $f" >&2
        exit 1
    fi
done
echo "[✓] ${#FILES[@]} 个文件全部存在"

# 4. 检查是否有不该提交的文件
DIRTY=$(git diff --name-only 2>/dev/null | grep -v "^${ASCEND_OPS}/\|^tests/test_${OP}\|^benchmark/test_${OP}\|^conf/operators.yaml" || true)
if [[ -n "$DIRTY" ]]; then
    echo "[!] 警告: 以下文件有改动但不在提交范围:"
    echo "$DIRTY" | sed 's/^/     /'
fi

COMMIT_MSG="${TITLE_PREFIX} Add ${OP} operator with Triton kernel"

if $DRY_RUN; then
    echo ""
    echo "[DRY RUN] 将要执行:"
    echo "  git add ${FILES[*]}"
    echo "  git commit -m '${COMMIT_MSG}'"
    echo "  git push ${FORK_REMOTE} ${EXPECTED}"
    exit 0
fi

# 5. Stage
git add "${FILES[@]}"
echo "[✓] Staged ${#FILES[@]} files"

# 6. Commit（不带 Co-Authored-By）
git commit -m "$COMMIT_MSG"
echo "[✓] Committed: ${COMMIT_MSG}"

# 7. 验证 author
AUTHOR="$(git log -1 --format='%an <%ae>')"
echo "[✓] Author: ${AUTHOR}"

# 8. Push（失败不自动 force —— force push 会覆盖远端历史，需人工确认）
if git push "$FORK_REMOTE" "$EXPECTED"; then
    echo "[✓] Pushed to ${FORK_REMOTE}/${EXPECTED}"
else
    echo "" >&2
    echo "[✗] Push 失败。" >&2
    echo "    若确实需要覆盖远端分支，请手动确认后执行:" >&2
    echo "      git push ${FORK_REMOTE} ${EXPECTED} --force-with-lease" >&2
    exit 1
fi

echo ""
echo "=== commit_and_push 完成 ==="
