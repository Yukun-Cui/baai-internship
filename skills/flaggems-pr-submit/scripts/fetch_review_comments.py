#!/usr/bin/env python3
"""Fetch and filter actionable review comments from open PRs.

Usage:
    python fetch_review_comments.py [--repo REPO] [--fork-owner USER] [--json]

Outputs a structured list of PRs with pending review comments that need to be addressed.
"""
import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class ReviewComment:
    pr_number: int
    pr_title: str
    branch: str
    reviewer: str
    path: str
    line: Optional[int]
    body: str
    created_at: str


def run_gh(args: list[str]) -> str:
    result = subprocess.run(
        ["gh"] + args, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def get_open_prs(repo: str, fork_owner: str) -> list[dict]:
    raw = run_gh([
        "api", f"repos/{repo}/pulls",
        "--paginate",
        "-q",
        f'.[] | select(.user.login == "{fork_owner}") '
        f'| {{number, title, head_ref: .head.ref}}',
    ])
    if not raw:
        return []
    prs = []
    for line in raw.strip().split("\n"):
        if line.strip():
            prs.append(json.loads(line))
    return prs


def get_review_comments(repo: str, pr_number: int) -> list[dict]:
    raw = run_gh([
        "api", f"repos/{repo}/pulls/{pr_number}/comments",
        "--paginate",
        "-q", '.[] | {user: .user.login, path, line, body, created_at: .created_at}',
    ])
    if not raw:
        return []
    comments = []
    for line in raw.strip().split("\n"):
        if line.strip():
            comments.append(json.loads(line))
    return comments


def get_last_push_time(repo: str, pr_number: int) -> Optional[str]:
    """Get the timestamp of the most recent commit on the PR branch.

    If a comment was made before this time, it's likely already addressed
    by subsequent commits and can be considered outdated.
    """
    raw = run_gh([
        "api", f"repos/{repo}/pulls/{pr_number}/commits",
        "--paginate",
        "-q", '.[-1].commit.committer.date',
    ])
    return raw.strip() if raw.strip() else None


def get_issue_comments(repo: str, pr_number: int) -> list[dict]:
    raw = run_gh([
        "api", f"repos/{repo}/issues/{pr_number}/comments",
        "--paginate",
        "-q", '.[] | {user: .user.login, body, created_at: .created_at}',
    ])
    if not raw:
        return []
    comments = []
    for line in raw.strip().split("\n"):
        if line.strip():
            comments.append(json.loads(line))
    return comments


def is_actionable(comment: dict, fork_owner: str) -> bool:
    user = comment.get("user", "")
    if user.lower() == fork_owner.lower():
        return False
    bots = {"github-actions", "codecov", "dependabot", "renovate"}
    if user.lower() in bots or user.endswith("[bot]"):
        return False
    body = comment.get("body", "").strip()
    if not body or len(body) <= 2:
        return False
    return True


def fetch_all_comments(repo: str, fork_owner: str, include_outdated: bool = False) -> list[ReviewComment]:
    prs = get_open_prs(repo, fork_owner)
    if not prs:
        print(f"No open PRs found for {fork_owner} in {repo}", file=sys.stderr)
        return []

    all_comments: list[ReviewComment] = []

    for pr in prs:
        pr_number = pr["number"]
        pr_title = pr["title"]
        branch = pr["head_ref"]

        # Get last commit time to filter outdated comments
        last_push = get_last_push_time(repo, pr_number) if not include_outdated else None

        for c in get_review_comments(repo, pr_number):
            if is_actionable(c, fork_owner):
                # Skip comments that predate the last commit (already addressed)
                if last_push and c["created_at"] < last_push:
                    continue
                all_comments.append(ReviewComment(
                    pr_number=pr_number,
                    pr_title=pr_title,
                    branch=branch,
                    reviewer=c["user"],
                    path=c.get("path", ""),
                    line=c.get("line"),
                    body=c["body"],
                    created_at=c["created_at"],
                ))

        for c in get_issue_comments(repo, pr_number):
            if is_actionable(c, fork_owner):
                # Skip comments that predate the last commit (already addressed)
                if last_push and c["created_at"] < last_push:
                    continue
                all_comments.append(ReviewComment(
                    pr_number=pr_number,
                    pr_title=pr_title,
                    branch=branch,
                    reviewer=c["user"],
                    path="",
                    line=None,
                    body=c["body"],
                    created_at=c["created_at"],
                ))

    return all_comments


def format_text(comments: list[ReviewComment]) -> str:
    if not comments:
        return "No actionable review comments found."

    by_pr: dict[int, list[ReviewComment]] = {}
    for c in comments:
        by_pr.setdefault(c.pr_number, []).append(c)

    lines = []
    for pr_number in sorted(by_pr.keys()):
        group = by_pr[pr_number]
        pr_title = group[0].pr_title
        branch = group[0].branch
        lines.append(f"\n## PR #{pr_number}: {pr_title}")
        lines.append(f"   Branch: {branch}")
        for c in group:
            loc = f"{c.path}:{c.line}" if c.path else "(PR-level)"
            lines.append(f"   - @{c.reviewer} [{loc}]: {c.body}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch actionable review comments from open PRs"
    )
    parser.add_argument(
        "--repo", default="flagos-ai/FlagGems-Experimental",
        help="Upstream repo (owner/name)"
    )
    parser.add_argument(
        "--fork-owner", default="Yukun-Cui",
        help="Fork owner username on GitHub"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON instead of text"
    )
    parser.add_argument(
        "--include-outdated", action="store_true",
        help="Include comments that predate the latest commit (likely already addressed)"
    )
    args = parser.parse_args()

    comments = fetch_all_comments(args.repo, args.fork_owner, include_outdated=args.include_outdated)

    if args.json:
        data = [
            {
                "pr_number": c.pr_number,
                "pr_title": c.pr_title,
                "branch": c.branch,
                "reviewer": c.reviewer,
                "path": c.path,
                "line": c.line,
                "body": c.body,
                "created_at": c.created_at,
            }
            for c in comments
        ]
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(format_text(comments))


if __name__ == "__main__":
    main()
