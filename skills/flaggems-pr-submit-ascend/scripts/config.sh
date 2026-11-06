#!/usr/bin/env bash
# 共享配置 + 工具函数，由本目录下的 *.sh 通过 source 引入。
#
# 设计原则：不在脚本里写死个人路径、身份或 fork 名。
# 所有可变项走环境变量，仓库路径也可用 --repo-dir 覆盖。
#
# 必需:
#   FLAGGEMS_REPO           FlagGems 仓库路径（或每次传 --repo-dir）
#
# 可选:
#   FLAGGEMS_SUMMARY_JSON   auto_gen benchmark 结果 summary.json 路径
#   FLAGGEMS_ASCEND_OPS     Ascend kernel 目录（仓库内相对路径）
#   FLAGGEMS_UPSTREAM_REMOTE / FLAGGEMS_UPSTREAM_REPO / FLAGGEMS_BASE_BRANCH
#   FLAGGEMS_FORK_REMOTE / FLAGGEMS_FORK_OWNER   （fork owner 默认从 remote URL 推导）
#   FLAGGEMS_BRANCH_PREFIX  PR 分支前缀，默认 pr/ascend-
#   FLAGGEMS_TITLE_PREFIX   commit / PR 标题前缀，默认 [KernelGen][Ascend]
#   FLAGGEMS_GIT_NAME / FLAGGEMS_GIT_EMAIL  期望的提交身份（仅校验，不改写 git config）
#   FLAGGEMS_PYTHON         python 解释器，默认 python3

ASCEND_OPS="${FLAGGEMS_ASCEND_OPS:-src/flag_gems/runtime/backend/_ascend/ops}"

UPSTREAM_REMOTE="${FLAGGEMS_UPSTREAM_REMOTE:-upstream}"
UPSTREAM_REPO="${FLAGGEMS_UPSTREAM_REPO:-flagos-ai/FlagGems}"
BASE_BRANCH="${FLAGGEMS_BASE_BRANCH:-master}"
FORK_REMOTE="${FLAGGEMS_FORK_REMOTE:-fork}"

BRANCH_PREFIX="${FLAGGEMS_BRANCH_PREFIX:-pr/ascend-}"
TITLE_PREFIX="${FLAGGEMS_TITLE_PREFIX:-[KernelGen][Ascend]}"

PYTHON_BIN="${FLAGGEMS_PYTHON:-python3}"

# 解析仓库路径：--repo-dir 优先，其次 FLAGGEMS_REPO。都没有则报错退出，不猜路径。
resolve_repo_dir() {
    local dir="${1:-}"
    dir="${dir:-${FLAGGEMS_REPO:-}}"

    if [[ -z "$dir" ]]; then
        cat >&2 <<'EOF'
ERROR: 未指定 FlagGems 仓库路径。
  方式 1: --repo-dir /path/to/FlagGems
  方式 2: export FLAGGEMS_REPO=/path/to/FlagGems
EOF
        exit 1
    fi
    if [[ ! -d "$dir" ]]; then
        echo "ERROR: 仓库路径不存在: $dir" >&2
        exit 1
    fi
    if [[ ! -e "$dir/.git" ]]; then
        echo "ERROR: 不是 git 仓库（缺少 .git）: $dir" >&2
        exit 1
    fi
    printf '%s\n' "$dir"
}

# 解析 summary.json 路径：--summary 优先，其次 FLAGGEMS_SUMMARY_JSON。允许为空。
resolve_summary_json() {
    local path="${1:-}"
    printf '%s\n' "${path:-${FLAGGEMS_SUMMARY_JSON:-}}"
}

# 推导 fork owner：FLAGGEMS_FORK_OWNER 优先，其次解析 fork remote 的 URL。
# 需先 cd 到仓库目录。
resolve_fork_owner() {
    if [[ -n "${FLAGGEMS_FORK_OWNER:-}" ]]; then
        printf '%s\n' "$FLAGGEMS_FORK_OWNER"
        return 0
    fi

    local url owner
    url="$(git remote get-url "$FORK_REMOTE" 2>/dev/null || true)"
    if [[ -n "$url" ]]; then
        # git@host:owner/repo.git | https://host/owner/repo.git | ssh://host/owner/repo
        owner="$(printf '%s' "$url" | sed -E 's#\.git$##; s#^.*[:/]([^/:]+)/[^/]+$#\1#')"
        if [[ -n "$owner" && "$owner" != "$url" ]]; then
            printf '%s\n' "$owner"
            return 0
        fi
    fi

    cat >&2 <<EOF
ERROR: 无法确定 fork owner。
  方式 1: export FLAGGEMS_FORK_OWNER=<your-github-org-or-user>
  方式 2: 配置 remote '${FORK_REMOTE}' 指向你的 fork
EOF
    exit 1
}

# 检查 git 提交身份，设置 GIT_NAME / GIT_EMAIL / GIT_IDENTITY (ok|missing|mismatch)。
# 直接调用（不要放进 $(...) —— 子 shell 里的赋值不会传回来）。
# 只读校验 —— 绝不改写用户的 git config。
check_git_identity() {
    GIT_NAME="$(git config user.name 2>/dev/null || true)"
    GIT_EMAIL="$(git config user.email 2>/dev/null || true)"

    if [[ -z "$GIT_NAME" || -z "$GIT_EMAIL" ]]; then
        GIT_IDENTITY="missing"
    elif [[ -n "${FLAGGEMS_GIT_NAME:-}" && "$GIT_NAME" != "$FLAGGEMS_GIT_NAME" ]]; then
        GIT_IDENTITY="mismatch"
    elif [[ -n "${FLAGGEMS_GIT_EMAIL:-}" && "$GIT_EMAIL" != "$FLAGGEMS_GIT_EMAIL" ]]; then
        GIT_IDENTITY="mismatch"
    else
        GIT_IDENTITY="ok"
    fi
}

# 期望身份的可读描述，用于报错信息
expected_identity_desc() {
    if [[ -n "${FLAGGEMS_GIT_NAME:-}" || -n "${FLAGGEMS_GIT_EMAIL:-}" ]]; then
        printf '%s <%s>\n' "${FLAGGEMS_GIT_NAME:-*}" "${FLAGGEMS_GIT_EMAIL:-*}"
    else
        printf '(未设置 FLAGGEMS_GIT_NAME / FLAGGEMS_GIT_EMAIL，跳过匹配)\n'
    fi
}

