#!/usr/bin/env python3
"""一键 rebase PR 分支到 upstream/<base> 并自动解决常见冲突。

自动处理的冲突类型：
  - src/flag_gems/__init__.py (_FULL_CONFIG 排序冲突)
  - src/flag_gems/ops/__init__.py (import + __all__ 排序冲突)

无法自动处理的冲突会报告路径，需要手动解决后再 `git rebase --continue`。

用法：
    # 在 PR 分支上运行（默认 base 为 infra-ci，fork remote 为 origin）
    python rebase_and_resolve.py --repo-dir /root/FlagGems

    # 预览模式（不实际 push）
    python rebase_and_resolve.py --repo-dir /root/FlagGems --no-push

    # 指定远程名称 / base 分支
    python rebase_and_resolve.py --repo-dir /root/FlagGems --upstream upstream --fork origin --base infra-ci

流程：
    1. git fetch upstream
    2. 检测 merge commit → 如果存在则 reset 到最近的非 merge 提交
    3. git rebase upstream/<base>
    4. 自动解决 __init__.py / ops/__init__.py 冲突
    5. git rebase --continue
    6. git push <fork> <branch> --force
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def run(cmd: list[str], cwd: str = None, check: bool = True,
        capture: bool = True) -> subprocess.CompletedProcess:
    """运行命令并返回结果。"""
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=capture, text=True
    )
    if check and result.returncode != 0:
        return result  # 不抛异常，由调用者检查
    return result


def git(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    """运行 git 命令。"""
    return run(["git"] + args, cwd=cwd, check=False)


def get_current_branch(cwd: str) -> str:
    r = git(["branch", "--show-current"], cwd)
    return r.stdout.strip()


def get_our_commits(cwd: str, upstream: str, base: str) -> list[str]:
    """获取 upstream/<base> 之后的我们的 commit（非 merge）。"""
    r = git(["log", "--oneline", "--no-merges", f"{upstream}/{base}..HEAD"], cwd)
    if r.returncode != 0:
        return []
    return [l for l in r.stdout.strip().split("\n") if l]


def has_merge_commits(cwd: str, upstream: str, base: str) -> bool:
    """检查是否有 merge commit。"""
    r = git(["log", "--oneline", "--merges", f"{upstream}/{base}..HEAD"], cwd)
    return bool(r.stdout.strip())


def find_first_own_commit(cwd: str, upstream: str, base: str) -> str | None:
    """找到我们最早的非 merge commit hash。"""
    r = git(["log", "--reverse", "--format=%H", "--no-merges",
             f"{upstream}/{base}..HEAD"], cwd)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    lines = r.stdout.strip().split("\n")
    return lines[0] if lines else None


def get_conflicted_files(cwd: str) -> list[str]:
    """获取冲突文件列表。"""
    r = git(["diff", "--name-only", "--diff-filter=U"], cwd)
    if r.returncode != 0:
        return []
    return [f for f in r.stdout.strip().split("\n") if f]


def resolve_init_py(cwd: str) -> bool:
    """尝试解决 src/flag_gems/__init__.py 的冲突。"""
    script = SCRIPT_DIR / "resolve_init_conflicts.py"
    r = run([sys.executable, str(script), "--repo-dir", cwd], cwd=cwd)
    if r.returncode == 0:
        git(["add", "src/flag_gems/__init__.py"], cwd)
        print(f"  ✅ src/flag_gems/__init__.py 冲突已解决")
        return True
    else:
        print(f"  ❌ src/flag_gems/__init__.py 自动解决失败:")
        print(f"     {r.stderr.strip()}")
        return False


def resolve_ops_init_py(cwd: str) -> bool:
    """尝试解决 src/flag_gems/ops/__init__.py 的冲突。"""
    script = SCRIPT_DIR / "resolve_ops_init_conflicts.py"
    r = run([sys.executable, str(script), "--repo-dir", cwd], cwd=cwd)
    if r.returncode == 0:
        git(["add", "src/flag_gems/ops/__init__.py"], cwd)
        print(f"  ✅ src/flag_gems/ops/__init__.py 冲突已解决")
        return True
    else:
        print(f"  ❌ src/flag_gems/ops/__init__.py 自动解决失败:")
        print(f"     {r.stderr.strip()}")
        return False


# 可自动解决的文件映射
AUTO_RESOLVABLE = {
    "src/flag_gems/__init__.py": resolve_init_py,
    "src/flag_gems/ops/__init__.py": resolve_ops_init_py,
}


def main():
    parser = argparse.ArgumentParser(
        description="一键 rebase PR 分支并自动解决常见冲突"
    )
    parser.add_argument(
        "--repo-dir", default=".",
        help="FlagGems 仓库根目录 (默认: 当前目录)",
    )
    parser.add_argument(
        "--upstream", default="upstream",
        help="上游远程名称 (默认: upstream)",
    )
    parser.add_argument(
        "--fork", default="origin",
        help="我们 fork 的远程名称 (默认: origin)",
    )
    parser.add_argument(
        "--base", default="infra-ci",
        help="上游 base 分支 (默认: infra-ci)",
    )
    parser.add_argument(
        "--no-push", action="store_true",
        help="不自动 push（只做 rebase + 解冲突）",
    )
    args = parser.parse_args()
    cwd = os.path.abspath(args.repo_dir)

    # 检查是否在 git 仓库
    r = git(["rev-parse", "--git-dir"], cwd)
    if r.returncode != 0:
        print("错误: 不在 git 仓库中", file=sys.stderr)
        sys.exit(1)

    branch = get_current_branch(cwd)
    if not branch:
        print("错误: 无法获取当前分支", file=sys.stderr)
        sys.exit(1)

    print(f"📌 当前分支: {branch}")

    # Step 1: fetch upstream
    print(f"\n🔄 Fetching {args.upstream}...")
    r = git(["fetch", args.upstream], cwd)
    if r.returncode != 0:
        print(f"错误: fetch 失败: {r.stderr}", file=sys.stderr)
        sys.exit(1)

    # Step 2: 检查 merge commit
    our_commits = get_our_commits(cwd, args.upstream, args.base)
    if not our_commits:
        print("错误: 没有找到我们的 commit", file=sys.stderr)
        sys.exit(1)

    print(f"   我们的 commits ({len(our_commits)}):")
    for c in our_commits[:5]:
        print(f"     {c}")

    if has_merge_commits(cwd, args.upstream, args.base):
        print("\n⚠️  检测到 merge commit，需要 reset 后再 rebase")
        first_commit = find_first_own_commit(cwd, args.upstream, args.base)
        if first_commit:
            # 如果只有一个 commit，reset 到它；如果多个，reset 到第一个的 parent
            if len(our_commits) == 1:
                target = first_commit
            else:
                # 找到最后一个 commit (最新的)
                r = git(["log", "--format=%H", "--no-merges",
                         f"{args.upstream}/{args.base}..HEAD"], cwd)
                last_commit = r.stdout.strip().split("\n")[0]
                target = last_commit

            print(f"   Resetting to: {target[:12]}")
            r = git(["reset", "--hard", target], cwd)
            if r.returncode != 0:
                print(f"错误: reset 失败: {r.stderr}", file=sys.stderr)
                sys.exit(1)

    # Step 3: rebase
    print(f"\n🔄 Rebasing onto {args.upstream}/{args.base}...")
    r = git(["rebase", f"{args.upstream}/{args.base}"], cwd)

    if r.returncode == 0:
        print("✅ Rebase 成功，无冲突")
    else:
        print("⚡ Rebase 产生冲突，尝试自动解决...")

        # 循环解决冲突（rebase 可能有多个 commit 需要逐个处理）
        max_iterations = 20
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            conflicts = get_conflicted_files(cwd)
            if not conflicts:
                break

            print(f"\n--- Rebase 冲突 (轮次 {iteration}) ---")
            print(f"   冲突文件: {conflicts}")

            all_resolved = True
            for f in conflicts:
                if f in AUTO_RESOLVABLE:
                    if not AUTO_RESOLVABLE[f](cwd):
                        all_resolved = False
                else:
                    print(f"  ❌ {f} 需要手动解决")
                    all_resolved = False

            if not all_resolved:
                print("\n❌ 部分冲突无法自动解决，请手动处理后运行：")
                print(f"   cd {cwd}")
                print("   # 解决冲突...")
                print("   git add <files>")
                print("   git rebase --continue")
                sys.exit(1)

            # 继续 rebase
            env = os.environ.copy()
            env["GIT_EDITOR"] = "true"
            r = subprocess.run(
                ["git", "rebase", "--continue"],
                cwd=cwd, capture_output=True, text=True, env=env
            )
            if r.returncode == 0:
                print("\n✅ Rebase 继续成功")
                break
            elif "CONFLICT" in r.stdout + r.stderr:
                # 还有更多冲突，继续循环
                continue
            else:
                # 检查是否真的完成了
                r2 = git(["status", "--porcelain"], cwd)
                if "rebase" not in (git(["status"], cwd).stdout):
                    print("\n✅ Rebase 完成")
                    break
                print(f"\n❌ Rebase continue 失败:")
                print(f"   stdout: {r.stdout}")
                print(f"   stderr: {r.stderr}")
                sys.exit(1)

    # 验证最终状态
    final_commits = get_our_commits(cwd, args.upstream, args.base)
    print(f"\n📋 最终 commits ({len(final_commits)}):")
    for c in final_commits:
        print(f"   {c}")

    # Step 4: push
    if args.no_push:
        print(f"\n🏁 完成 (--no-push 模式，未推送)")
        print(f"   手动推送: git push {args.fork} {branch} --force")
    else:
        print(f"\n🚀 Pushing to {args.fork}/{branch}...")
        r = git(["push", args.fork, branch, "--force"], cwd)
        if r.returncode == 0:
            print(f"✅ 已推送到 {args.fork}/{branch}")
        else:
            print(f"❌ Push 失败: {r.stderr}")
            sys.exit(1)

    print("\n🎉 完成!")


if __name__ == "__main__":
    main()
