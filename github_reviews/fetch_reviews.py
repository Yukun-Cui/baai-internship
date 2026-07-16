#!/usr/bin/env python3
"""Fetch GitHub PR reviews/comments and report reply status."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR / "results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch review/comment activity on author's GitHub PRs."
    )
    parser.add_argument("--days", type=int, help="Only count reviews/comments from last N days.")
    parser.add_argument("--since", help="Only count reviews/comments since YYYY-MM-DD.")
    parser.add_argument("--date", help='Only count reviews/comments on YYYY-MM-DD, or "today".')
    parser.add_argument("--unreplied", action="store_true", help="Only show unreplied actionable external comments.")
    parser.add_argument("--state", choices=["open", "closed", "all"], default="all", help="Filter PR state.")
    parser.add_argument("--open", action="store_true", help="Shortcut for --state open.")
    parser.add_argument("--repo", default=os.environ.get("UPSTREAM", "flagos-ai/FlagGems-Experimental"))
    parser.add_argument("--author", default=os.environ.get("AUTHOR", "Yukun-Cui"))
    parser.add_argument("--output", help="Write report to this file.")
    return parser.parse_args()


def parse_time(value: str | None):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def format_time(value: str | None) -> str:
    dt = parse_time(value)
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def date_part(value: str | None) -> str:
    return (value or "")[:10]


def get_cutoff(args: argparse.Namespace):
    if args.date:
        date_value = datetime.now().strftime("%Y-%m-%d") if args.date == "today" else args.date
        return datetime.fromisoformat(date_value).replace(tzinfo=timezone.utc), date_value
    if args.since:
        return datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc), ""
    if args.days:
        return datetime.now(timezone.utc) - timedelta(days=args.days), ""
    return None, ""


def default_output_path() -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = RESULTS_DIR / f"reviews_{timestamp}.md"
    suffix = 1
    while output.exists():
        output = RESULTS_DIR / f"reviews_{timestamp}_{suffix}.md"
        suffix += 1
    return output


def gh_api(endpoint: str, paginate: bool = True) -> list:
    cmd = ["gh", "api"]
    if paginate:
        cmd.append("--paginate")
    cmd.append(endpoint)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except Exception as exc:
        print(f"[API Error] {endpoint}: {exc}", file=sys.stderr)
        return []

    if result.returncode != 0:
        print(f"[API Error] {endpoint}: {result.stderr[-500:]}", file=sys.stderr)
        return []

    text = result.stdout.strip()
    if not text:
        return []

    try:
        data = json.loads(text)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        items = []
        decoder = json.JSONDecoder()
        idx = 0
        while idx < len(text):
            while idx < len(text) and text[idx] in " \t\r\n":
                idx += 1
            if idx >= len(text):
                break
            obj, end_idx = decoder.raw_decode(text, idx)
            items.extend(obj if isinstance(obj, list) else [obj])
            idx = end_idx
        return items


def gh_graphql_search(query: str) -> list[dict]:
    gql = """
query($q: String!, $cursor: String) {
  search(query: $q, type: ISSUE, first: 100, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {
        number
        title
        state
        url
        createdAt
        updatedAt
      }
    }
  }
}
"""
    all_nodes = []
    cursor = None
    while True:
        cmd = ["gh", "api", "graphql", "-f", f"query={gql}", "-f", f"q={query}"]
        if cursor:
            cmd += ["-f", f"cursor={cursor}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            print(f"[GraphQL Error] {result.stderr[-500:]}", file=sys.stderr)
            raise SystemExit(1)
        data = json.loads(result.stdout)
        search = data.get("data", {}).get("search", {})
        all_nodes.extend(node for node in search.get("nodes", []) if node)
        page_info = search.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
    return all_nodes


def ensure_github_auth() -> bool:
    result = subprocess.run(
        ["gh", "api", "rate_limit"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        print("GitHub API authentication failed.", file=sys.stderr)
        print("Set GH_TOKEN or run `gh auth login` before using this script.", file=sys.stderr)
        print(result.stderr[-800:], file=sys.stderr)
        return False
    return True


def is_bot(user: str) -> bool:
    return user.endswith("[bot]") or user in {"github-actions", "github-actions[bot]"}


def normalize_review_comment(pr: dict, comment: dict) -> dict:
    return {
        "kind": "review_comment",
        "type": "代码行级评论",
        "id": comment.get("id"),
        "pr_num": pr["number"],
        "pr_title": pr["title"],
        "pr_state": pr["state"],
        "pr_url": pr["url"],
        "user": comment.get("user", {}).get("login", "unknown"),
        "time": comment.get("created_at", ""),
        "body": comment.get("body", ""),
        "path": comment.get("path", ""),
        "line": comment.get("line") or comment.get("original_line") or "N/A",
        "diff_hunk": comment.get("diff_hunk", ""),
        "in_reply_to_id": comment.get("in_reply_to_id"),
        "html_url": comment.get("html_url", ""),
        "review_state": "",
    }


def normalize_review(pr: dict, review: dict) -> dict:
    state = review.get("state", "")
    state_map = {
        "APPROVED": "Approved",
        "CHANGES_REQUESTED": "Changes Requested",
        "COMMENTED": "Commented",
        "DISMISSED": "Dismissed",
    }
    return {
        "kind": "review",
        "type": f"PR Review ({state_map.get(state, state)})",
        "id": review.get("id"),
        "pr_num": pr["number"],
        "pr_title": pr["title"],
        "pr_state": pr["state"],
        "pr_url": pr["url"],
        "user": review.get("user", {}).get("login", "unknown"),
        "time": review.get("submitted_at", ""),
        "body": review.get("body", ""),
        "path": "",
        "line": "",
        "diff_hunk": "",
        "in_reply_to_id": None,
        "html_url": review.get("html_url", ""),
        "review_state": state,
    }


def normalize_issue_comment(pr: dict, comment: dict) -> dict:
    return {
        "kind": "issue_comment",
        "type": "PR 对话评论",
        "id": comment.get("id"),
        "pr_num": pr["number"],
        "pr_title": pr["title"],
        "pr_state": pr["state"],
        "pr_url": pr["url"],
        "user": comment.get("user", {}).get("login", "unknown"),
        "time": comment.get("created_at", ""),
        "body": comment.get("body", ""),
        "path": "",
        "line": "",
        "diff_hunk": "",
        "in_reply_to_id": None,
        "html_url": comment.get("html_url", ""),
        "review_state": "",
    }


def is_actionable_external(event: dict, author: str) -> bool:
    if event["user"] == author or is_bot(event["user"]):
        return False
    if event["kind"] in {"review_comment", "issue_comment"}:
        return True
    if event["kind"] == "review":
        return event.get("review_state") in {"CHANGES_REQUESTED", "COMMENTED", "DISMISSED"} and bool(event.get("body", "").strip())
    return False


def has_author_reply(event: dict, pr_events: list[dict], author: str):
    event_dt = parse_time(event["time"])
    if not event_dt:
        return False, None

    author_events = [
        e for e in pr_events
        if e["user"] == author and parse_time(e["time"]) and parse_time(e["time"]) > event_dt
    ]
    if not author_events:
        return False, None

    if event["kind"] == "review_comment":
        root_id = event.get("in_reply_to_id") or event.get("id")
        for reply in author_events:
            if reply["kind"] == "review_comment" and reply.get("in_reply_to_id") == root_id:
                return True, reply
        return False, None

    for reply in author_events:
        if reply["kind"] in {"issue_comment", "review_comment", "review"}:
            return True, reply
    return False, None


def write_event(f, event: dict) -> None:
    status = "N/A"
    if event.get("actionable_external"):
        status = "已回复" if event.get("replied_by_author") else "未回复"

    f.write(f"### PR #{event['pr_num']}: {event['pr_title']} [{event['pr_state']}]\n\n")
    f.write(f"- **PR**: {event['pr_url']}\n")
    f.write(f"- **评论者**: @{event['user']}\n")
    f.write(f"- **类型**: {event['type']}\n")
    f.write(f"- **时间**: {format_time(event['time'])}\n")
    f.write(f"- **回复状态**: {status}\n")
    if event.get("reply_time"):
        f.write(f"- **你的回复时间**: {format_time(event['reply_time'])}\n")
    if event.get("reply_url"):
        f.write(f"- **你的回复链接**: {event['reply_url']}\n")
    if event.get("path"):
        f.write(f"- **文件**: `{event['path']}` (Line {event.get('line', 'N/A')})\n")
    if event.get("in_reply_to_id"):
        f.write(f"- **回复到**: comment #{event['in_reply_to_id']}\n")
    if event.get("html_url"):
        f.write(f"- **评论链接**: {event['html_url']}\n")
    if event.get("diff_hunk"):
        f.write(f"\n<details><summary>相关代码片段</summary>\n\n```diff\n{event['diff_hunk']}\n```\n</details>\n\n")
    body = event.get("body", "").strip()
    f.write("\n**评论内容**:\n\n")
    f.write(f"{body}\n\n" if body else "*(无附加评论)*\n\n")
    f.write("---\n\n")


def main() -> int:
    args = parse_args()
    if args.open:
        args.state = "open"
    if not ensure_github_auth():
        return 2

    cutoff, exact_date = get_cutoff(args)
    output_file = Path(args.output) if args.output else default_output_path()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    def in_report_window(event_time: str) -> bool:
        if not event_time:
            return False
        if exact_date:
            return date_part(event_time) == exact_date
        if cutoff:
            dt = parse_time(event_time)
            return bool(dt and dt >= cutoff)
        return True

    print("=========================================")
    print(" GitHub PR Reviews Fetcher")
    print("=========================================")
    print(f"Upstream: {args.repo}")
    print(f"Author:   {args.author}")
    print(f"Output:   {output_file}")
    print(f"PR state: {args.state}")
    if args.days:
        print(f"Filter:   reviews/comments in last {args.days} days")
    if args.since:
        print(f"Filter:   reviews/comments since {args.since}")
    if exact_date:
        print(f"Filter:   reviews/comments on {exact_date}")
    if args.unreplied:
        print("Mode:     unreplied actionable external reviews/comments only")
    print()

    search_query = f"is:pr author:{args.author} repo:{args.repo}"
    if args.state != "all":
        search_query += f" is:{args.state}"
    if cutoff:
        search_query += f" updated:>={cutoff.strftime('%Y-%m-%d')}"

    print("正在获取 PR 列表...")
    prs = gh_graphql_search(search_query)
    print(f"找到 {len(prs)} 个 PR")

    report_events = []
    unreplied_events = []

    for idx, pr in enumerate(prs, start=1):
        pr_num = pr["number"]
        print(f"  [{idx}/{len(prs)}] PR #{pr_num}: {pr['title'][:70]}")
        review_comments = [
            normalize_review_comment(pr, c)
            for c in gh_api(f"repos/{args.repo}/pulls/{pr_num}/comments")
        ]
        reviews = [
            normalize_review(pr, r)
            for r in gh_api(f"repos/{args.repo}/pulls/{pr_num}/reviews")
        ]
        issue_comments = [
            normalize_issue_comment(pr, c)
            for c in gh_api(f"repos/{args.repo}/issues/{pr_num}/comments")
        ]
        pr_events = review_comments + reviews + issue_comments
        pr_events.sort(key=lambda e: e.get("time") or "")

        for event in pr_events:
            if not in_report_window(event["time"]):
                continue
            actionable = is_actionable_external(event, args.author)
            replied, reply = has_author_reply(event, pr_events, args.author) if actionable else (False, None)
            event["actionable_external"] = actionable
            event["replied_by_author"] = replied
            event["reply_time"] = reply["time"] if reply else ""
            event["reply_url"] = reply["html_url"] if reply else ""
            if actionable and not replied:
                unreplied_events.append(event)
            if not args.unreplied or (actionable and not replied):
                report_events.append(event)

    report_events.sort(key=lambda e: e.get("time") or "", reverse=True)
    unreplied_events.sort(key=lambda e: e.get("time") or "", reverse=True)

    by_date = defaultdict(list)
    for event in report_events:
        by_date[date_part(event["time"])].append(event)

    with output_file.open("w", encoding="utf-8") as f:
        f.write("# GitHub PR Review Report\n\n")
        f.write(f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **Upstream**: `{args.repo}`\n")
        f.write(f"- **Author**: `@{args.author}`\n")
        f.write(f"- **PR 查询数**: {len(prs)}\n")
        f.write(f"- **报告事件数**: {len(report_events)}\n")
        f.write(f"- **未回复 actionable 外部 review/comment**: {len(unreplied_events)}\n")
        if args.days:
            f.write(f"- **时间范围**: 最近 {args.days} 天内产生的 review/comment\n")
        if args.since:
            f.write(f"- **时间范围**: 自 {args.since} 起产生的 review/comment\n")
        if exact_date:
            f.write(f"- **日期筛选**: {exact_date}\n")
        if args.unreplied:
            f.write("- **模式**: 只显示未回复 actionable 外部 review/comment\n")
        f.write("\n---\n\n")

        f.write("## 未回复 Review / 评论\n\n")
        if not unreplied_events:
            f.write("当前筛选范围内没有未回复的 actionable 外部 review/comment。\n\n")
        else:
            for event in unreplied_events:
                write_event(f, event)

        if not args.unreplied:
            f.write("\n## 按日期列出全部 Review / 评论\n\n")
            if not by_date:
                f.write("当前筛选范围内没有 review/comment。\n")
            for day in sorted(by_date.keys(), reverse=True):
                f.write(f"## {day} ({len(by_date[day])} 条)\n\n")
                for event in by_date[day]:
                    write_event(f, event)

        f.write("\n## 统计摘要\n\n")
        f.write("| 指标 | 数值 |\n")
        f.write("|---|---:|\n")
        f.write(f"| PR 查询数 | {len(prs)} |\n")
        f.write(f"| 报告事件数 | {len(report_events)} |\n")
        f.write(f"| 未回复 actionable 外部 review/comment | {len(unreplied_events)} |\n")

        reviewer_counts = defaultdict(int)
        unreplied_by_user = defaultdict(int)
        for event in report_events:
            reviewer_counts[event["user"]] += 1
        for event in unreplied_events:
            unreplied_by_user[event["user"]] += 1

        if reviewer_counts:
            f.write("\n### 评论者统计\n\n")
            f.write("| 评论者 | 报告事件数 | 未回复数 |\n")
            f.write("|---|---:|---:|\n")
            for user, count in sorted(reviewer_counts.items(), key=lambda x: (-x[1], x[0])):
                f.write(f"| @{user} | {count} | {unreplied_by_user.get(user, 0)} |\n")

    print()
    print(f"报告已保存到: {output_file}")
    print(f"未回复 actionable 外部 review/comment: {len(unreplied_events)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
