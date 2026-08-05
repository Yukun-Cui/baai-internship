#!/usr/bin/env python3
"""提交目标（target）预设，供 submit_operator.py / check_operator.py 等共用。

一套 skill 可投到多个不同的上游仓库/分支。每个 target 固化一组配置：
上游仓库、base 分支、fork owner、push remote、分支前缀，以及本地 remote 名。

用法：
    from targets import add_target_args, resolve_target
    add_target_args(parser)
    ...
    target = resolve_target(args)
    print(target.upstream_repo, target.base)

选择优先级（高 → 低）：
    显式 CLI 覆盖参数（--base 等） > --target 预设 > FLAGGEMS_TARGET 环境变量 > 默认 experimental

注意：两个 target 是不同的 GitHub 仓库，本地 `upstream` remote 一次只能指向其一。
切到 mainline 前，请确保本地 `upstream` 指向 flagos-ai/FlagGems（见 SKILL.md）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Target:
    name: str
    upstream_repo: str      # PR 目标仓库 owner/name
    base: str               # 上游 base 分支
    fork_owner: str         # 我们 fork 的 owner（用于 gh PR head=owner:branch）
    push_remote: str        # 本地 push 用的 remote 名
    branch_prefix: str      # PR 分支前缀，分支名 = prefix + op
    upstream_remote: str    # 本地上游 remote 名（fetch/diff 用）


TARGETS: dict[str, Target] = {
    "experimental": Target(
        name="experimental",
        upstream_repo="flagos-ai/FlagGems-Experimental",
        base="infra-ci",
        fork_owner="Yukun-Cui",
        push_remote="origin",
        branch_prefix="pr/",
        upstream_remote="upstream",
    ),
    "mainline": Target(
        name="mainline",
        upstream_repo="flagos-ai/FlagGems",
        base="master",
        fork_owner="Yukun-Cui",
        push_remote="origin",
        branch_prefix="pr/",
        upstream_remote="upstream",
    ),
}

DEFAULT_TARGET = "experimental"


def add_target_args(parser) -> None:
    """给 argparse parser 挂上 target 选择与可选覆盖参数。"""
    parser.add_argument(
        "--target",
        default=os.environ.get("FLAGGEMS_TARGET", DEFAULT_TARGET),
        choices=sorted(TARGETS),
        help=f"提交目标预设 (默认: {DEFAULT_TARGET}；也可用 FLAGGEMS_TARGET 环境变量)",
    )
    # 逐项覆盖（不常用；留作特殊情况的逃生舱）
    parser.add_argument("--upstream-repo", help="覆盖 target 的上游仓库 owner/name")
    parser.add_argument("--base", help="覆盖 target 的 base 分支")
    parser.add_argument("--fork-owner", help="覆盖 target 的 fork owner")
    parser.add_argument("--push-remote", help="覆盖 target 的 push remote 名")
    parser.add_argument("--branch-prefix", help="覆盖 target 的分支前缀")
    parser.add_argument("--upstream-remote", help="覆盖本地上游 remote 名")


def resolve_target(args) -> Target:
    """按 args 解析出最终 Target（预设 + 逐项覆盖）。"""
    base_target = TARGETS[getattr(args, "target", None) or DEFAULT_TARGET]
    return Target(
        name=base_target.name,
        upstream_repo=getattr(args, "upstream_repo", None) or base_target.upstream_repo,
        base=getattr(args, "base", None) or base_target.base,
        fork_owner=getattr(args, "fork_owner", None) or base_target.fork_owner,
        push_remote=getattr(args, "push_remote", None) or base_target.push_remote,
        branch_prefix=getattr(args, "branch_prefix", None) or base_target.branch_prefix,
        upstream_remote=getattr(args, "upstream_remote", None) or base_target.upstream_remote,
    )
