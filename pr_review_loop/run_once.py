#!/usr/bin/env python3
"""Run one conservative PR review loop pass.

This MVP is records-first. It can fetch a markdown report with the existing
github_reviews script, parse unreplied review entries, create per-review task
folders, and prepare DeepSeek/Claude handoffs plus Codex audit prompts.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT
DEFAULT_RECORDS_ROOT = ROOT / "records"
DEFAULT_GITHUB_REVIEWS = WORKSPACE / "github_reviews"
DEFAULT_DEEPSEEK_WORKFLOW = WORKSPACE / "deepseek-workflow"
EXTERNAL_TASK_GLOBS = ("pr-*/ci-fix-*/task.json", "pr-*/rebase-conflict-*/task.json")
EXTERNAL_TERMINAL_STATES = {"ci_passed", "done", "needs_human", "skipped"}
EXTERNAL_FIXER_STATES = {"pending", "needs_revision", "fix_failed"}
APPROVED_STATES = {"approved", "local_approved", "pushed", "ci_passed", "done"}


@dataclass
class ReviewTask:
    task_id: str
    pr_num: int
    pr_title: str
    pr_state: str
    pr_url: str
    reviewer: str
    review_type: str
    review_time: str
    reply_status: str
    path: str
    line: str
    comment_url: str
    body: str
    diff_hunk: str
    decision: str
    decision_reason: str
    shard_key: str
    source_report: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create PR review fix-loop tasks.")
    parser.add_argument("--config", default=str(ROOT / "config.yaml"))
    parser.add_argument("--resume", help="Resume an existing run directory instead of creating a new one.")
    parser.add_argument("--records-root", default=str(DEFAULT_RECORDS_ROOT))
    parser.add_argument("--github-reviews-dir", default=str(DEFAULT_GITHUB_REVIEWS))
    parser.add_argument("--deepseek-workflow-dir", default=str(DEFAULT_DEEPSEEK_WORKFLOW))
    parser.add_argument("--report", help="Use an existing markdown report instead of fetching.")
    parser.add_argument("--fetch", action="store_true", help="Run github_reviews/fetch_reviews.py first.")
    parser.add_argument(
        "--fetch-timeout",
        type=int,
        default=int(os.environ.get("PR_REVIEW_FETCH_TIMEOUT", "1800")),
        help="Maximum seconds to wait for github_reviews/fetch_reviews.py.",
    )
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--since")
    parser.add_argument("--date")
    parser.add_argument("--repo", default=os.environ.get("UPSTREAM", "flagos-ai/FlagGems-Experimental"))
    parser.add_argument("--author", default=os.environ.get("AUTHOR", "Yukun-Cui"))
    parser.add_argument("--state", choices=["open", "closed", "all"], default="open")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--limit-prs",
        type=int,
        default=0,
        help="Limit to the first N unique PRs in the report while keeping all parsed reviews for those PRs.",
    )
    parser.add_argument(
        "--shard-scope",
        choices=["pr", "path", "task"],
        default=os.environ.get("PR_REVIEW_SHARD_SCOPE", "pr"),
        help="How to group normal review tasks for fixer shards. Default groups all actionable reviews by PR.",
    )
    parser.add_argument("--fixer-parallelism", type=int, default=3)
    parser.add_argument("--max-reviews-per-fixer", type=int, default=2)
    parser.add_argument("--max-fix-rounds", type=int, default=2)
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--execute-fixers", action="store_true", help="Run fixer commands for actionable shards.")
    parser.add_argument(
        "--fixer-command",
        default=os.environ.get("PR_REVIEW_FIXER_COMMAND", ""),
        help=(
            "Shell command template for a fixer shard. Placeholders: "
            "{run_dir}, {shard_dir}, {handoff}, {round}."
        ),
    )
    parser.add_argument("--execute-audit", action="store_true", help="Run audit commands for actionable tasks.")
    parser.add_argument("--execute-claude-review", action="store_true", help="Run an independent Claude review before Codex audit.")
    parser.add_argument(
        "--claude-review-command",
        default=os.environ.get("PR_REVIEW_CLAUDE_REVIEW_COMMAND", ""),
        help=(
            "Shell command template for one Claude review gate. Placeholders: "
            "{run_dir}, {task_dir}, {round}, {worktree}."
        ),
    )
    parser.add_argument(
        "--audit-command",
        default=os.environ.get("PR_REVIEW_AUDIT_COMMAND", ""),
        help=(
            "Shell command template for one task audit. Placeholders: "
            "{run_dir}, {task_dir}, {audit_prompt}, {round}."
        ),
    )
    parser.add_argument(
        "--command-timeout",
        type=int,
        default=1800,
        help="Timeout in seconds for each fixer/audit/push/reply command.",
    )
    parser.add_argument(
        "--execute-local-validation",
        action="store_true",
        help="Run local validation commands after fixer changes and before audit.",
    )
    parser.add_argument(
        "--validation-command",
        default=os.environ.get("PR_REVIEW_VALIDATION_COMMAND", ""),
        help=(
            "Shell command template for local validation. Placeholders: "
            "{run_dir}, {task_dir}, {round}."
        ),
    )
    parser.add_argument(
        "--worktree-root",
        default=os.environ.get("PR_REVIEW_WORKTREE_ROOT", ""),
        help="Root containing PR worktrees named pr<NUM>. Used by the built-in validator.",
    )
    parser.add_argument(
        "--worktree-template",
        default=os.environ.get("PR_REVIEW_WORKTREE_TEMPLATE", ""),
        help="Worktree path template. Placeholders: {pr_num}, {task_id}. Overrides --worktree-root.",
    )
    parser.add_argument("--auto-commit", action="store_true", help="Commit approved PR worktrees before pushing.")
    parser.add_argument(
        "--commit-command",
        default=os.environ.get("PR_REVIEW_COMMIT_COMMAND", ""),
        help="Shell command template for committing. Placeholders: {run_dir}.",
    )
    parser.add_argument("--auto-push", action="store_true", help="Run --push-command after audits approve.")
    parser.add_argument(
        "--require-fresh-before-push",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Before push/reply, require a live --fetch run and re-check GitHub "
            "for already-replied review comments."
        ),
    )
    parser.add_argument(
        "--push-command",
        default=os.environ.get("PR_REVIEW_PUSH_COMMAND", ""),
        help="Shell command template for pushing. Placeholders: {run_dir}. Required with --auto-push.",
    )
    parser.add_argument("--wait-ci", action="store_true", help="Wait for GitHub checks after push before replying.")
    parser.add_argument("--ci-timeout", type=int, default=3600, help="Maximum seconds to wait for CI.")
    parser.add_argument("--ci-poll-interval", type=int, default=30, help="Seconds between CI polls.")
    parser.add_argument(
        "--generate-ci-fix-tasks",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Generate Claude/DeepSeek handoff tasks when CI fails.",
    )
    parser.add_argument("--auto-reply", action="store_true", help="Post reply drafts to GitHub after approval.")
    parser.add_argument("--no-package-copy", action="store_true")
    args = parser.parse_args()
    apply_config(args, explicit_dests(parser, sys.argv[1:]))
    return args


# Maps config.yaml keys (section -> yaml key -> argparse dest) onto args.
# Only dests that exist as CLI options are applied; unknown keys are ignored.
CONFIG_MAP: dict[str, dict[str, str]] = {
    "github": {"repo": "repo", "username": "author"},
    "paths": {
        "review_fetcher_dir": "github_reviews_dir",
        "deepseek_workflow_dir": "deepseek_workflow_dir",
        "records_root": "records_root",
    },
    "workflow": {
        "dry_run": "dry_run",
        "auto_push": "auto_push",
        "auto_reply": "auto_reply",
        "execute_fixers": "execute_fixers",
        "execute_local_validation": "execute_local_validation",
        "execute_claude_review": "execute_claude_review",
        "execute_audit": "execute_audit",
        "wait_ci": "wait_ci",
        "ci_timeout": "ci_timeout",
        "ci_poll_interval": "ci_poll_interval",
        "generate_ci_fix_tasks": "generate_ci_fix_tasks",
        "worktree_root": "worktree_root",
        "worktree_template": "worktree_template",
        "fixer_parallelism": "fixer_parallelism",
        "max_reviews_per_fixer": "max_reviews_per_fixer",
        "max_fix_rounds": "max_fix_rounds",
    },
    "commands": {
        "fixer_command": "fixer_command",
        "validation_command": "validation_command",
        "claude_review_command": "claude_review_command",
        "audit_command": "audit_command",
        "commit_command": "commit_command",
        "push_command": "push_command",
    },
}


def explicit_dests(parser: argparse.ArgumentParser, argv: list[str]) -> set[str]:
    """Return the set of arg dests that were explicitly given on the CLI.

    Config values must not override options the user passed by hand (e.g.
    --no-dry-run must win over config's ``dry_run: true``).
    """
    opt_to_dest: dict[str, str] = {}
    for action in parser._actions:
        for opt in action.option_strings:
            opt_to_dest[opt] = action.dest
    seen: set[str] = set()
    for token in argv:
        key = token.split("=", 1)[0]
        if key in opt_to_dest:
            seen.add(opt_to_dest[key])
    return seen


def apply_config(args: argparse.Namespace, explicit: set[str]) -> None:
    """Fill args from config.yaml for any option not set on the CLI.

    Precedence: explicit CLI flag > config.yaml value > argparse/env default.
    Missing or unreadable config is skipped (defaults stand).
    """
    config_path = Path(args.config)
    if not config_path.exists():
        return
    try:
        import yaml  # lazy: only needed when a config file is present
    except ImportError:
        print(f"WARNING: PyYAML not installed; ignoring {config_path}", file=sys.stderr)
        return
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        print(f"WARNING: could not parse {config_path}: {exc}", file=sys.stderr)
        return
    if not isinstance(data, dict):
        return
    for section, keymap in CONFIG_MAP.items():
        block = data.get(section)
        if not isinstance(block, dict):
            continue
        for yaml_key, dest in keymap.items():
            if yaml_key not in block or dest in explicit:
                continue
            value = block[yaml_key]
            if value is None:
                continue
            setattr(args, dest, value)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def run_shell(
    command: str,
    cwd: Path,
    log_prefix: Path,
    timeout: int,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    log_prefix.parent.mkdir(parents=True, exist_ok=True)
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=merged_env,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        timeout_msg = f"\n[TIMEOUT] command exceeded {timeout} seconds\n"
        result = subprocess.CompletedProcess(
            command,
            124,
            stdout=stdout,
            stderr=(stderr + timeout_msg),
        )
    log_prefix.with_suffix(".command.txt").write_text(command + "\n", encoding="utf-8")
    log_prefix.with_suffix(".stdout.log").write_text(result.stdout, encoding="utf-8")
    log_prefix.with_suffix(".stderr.log").write_text(result.stderr, encoding="utf-8")
    log_prefix.with_suffix(".exitcode").write_text(f"{result.returncode}\n", encoding="utf-8")
    return result


class FormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render_command(template: str, values: dict[str, object]) -> str:
    return template.format_map(FormatDict({key: str(value) for key, value in values.items()}))


def fetch_report_to(args: argparse.Namespace, run_dir: Path, output: Path) -> subprocess.CompletedProcess[str]:
    fetcher = Path(args.github_reviews_dir) / "fetch_reviews.py"
    if not fetcher.exists():
        raise FileNotFoundError(f"Missing review fetcher: {fetcher}")

    cmd = [
        sys.executable,
        str(fetcher),
        "--unreplied",
        "--repo",
        args.repo,
        "--author",
        args.author,
        "--state",
        args.state,
        "--output",
        str(output),
    ]
    if args.date:
        cmd.extend(["--date", args.date])
    elif args.since:
        cmd.extend(["--since", args.since])
    elif args.days:
        cmd.extend(["--days", str(args.days)])

    try:
        return run(cmd, cwd=Path(args.github_reviews_dir), timeout=max(1, args.fetch_timeout))
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return subprocess.CompletedProcess(
            cmd,
            124,
            stdout=stdout,
            stderr=stderr + f"\n[TIMEOUT] fetch_reviews.py exceeded {args.fetch_timeout} seconds\n",
        )


def fetch_report(args: argparse.Namespace, run_dir: Path) -> Path:
    output = run_dir / "source_reviews.md"
    result = fetch_report_to(args, run_dir, output)
    (run_dir / "fetch_reviews.stdout.log").write_text(result.stdout, encoding="utf-8")
    (run_dir / "fetch_reviews.stderr.log").write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(
            f"fetch_reviews.py failed with exit code {result.returncode}; "
            f"see {run_dir / 'fetch_reviews.stderr.log'}"
        )
    return output


def latest_report(github_reviews_dir: Path) -> Path:
    results = github_reviews_dir / "results"
    candidates = sorted(results.glob("reviews_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        fallback = github_reviews_dir / "output.md"
        if fallback.exists():
            return fallback
        raise FileNotFoundError(
            f"No review report found in {results}. "
            f"Pass --fetch to fetch reviews from GitHub first, "
            f"or --report <path-to-report.md> to reuse an existing report."
        )
    return candidates[0]


def split_entries(markdown: str) -> Iterable[str]:
    parts = re.split(r"(?m)^### PR #", markdown)
    for part in parts[1:]:
        yield "### PR #" + part.strip()


def field(entry: str, label: str) -> str:
    pattern = rf"^- \*\*{re.escape(label)}\*\*: ?(.*)$"
    match = re.search(pattern, entry, flags=re.MULTILINE)
    if not match:
        return ""
    value = match.group(1).strip()
    value = re.sub(r"^@(.*)$", r"\1", value)
    return value


def parse_body(entry: str) -> str:
    marker = "\n**评论内容**:\n\n"
    if marker not in entry:
        return ""
    tail = entry.split(marker, 1)[1]
    return tail.split("\n---", 1)[0].strip()


def parse_diff_hunk(entry: str) -> str:
    match = re.search(r"```diff\n(.*?)\n```", entry, flags=re.DOTALL)
    return match.group(1).strip() if match else ""


def parse_pr_header(entry: str) -> tuple[int, str, str]:
    first = entry.splitlines()[0]
    match = re.match(r"### PR #(\d+): (.*?) \[(.*?)\]", first)
    if not match:
        return 0, "", ""
    return int(match.group(1)), match.group(2).strip(), match.group(3).strip()


def sanitize_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-")
    return slug[:80] or "item"


def triage(entry: ReviewTask) -> tuple[str, str]:
    text = f"{entry.review_type}\n{entry.body}\n{entry.diff_hunk}".lower()
    if not entry.body.strip() or entry.body.strip() == "*(无附加评论)*":
        return "ignore", "No actionable review body was found."

    positive_review_markers = [
        "代码审查结果",
        "通过的检查",
        "✅",
        "无冲突",
        "mergeable",
        "ci 工作流状态",
        "通过",
    ]
    negative_review_markers = [
        "需要修改",
        "建议修改",
        "待修复",
        "未通过",
        "不通过",
        "失败",
        "报错",
        "failed",
        "changes requested",
        "please",
        "should",
        "fix",
    ]
    if (
        len(entry.body) > 80
        and any(marker in text for marker in positive_review_markers)
        and not any(marker in text for marker in negative_review_markers)
    ):
        return "ignore", "Automated review summary appears to list passing checks only."

    commit_message_keywords = [
        "co-authored-by",
        "co-authored by",
        "commit message",
        "trailer",
        "署名",
    ]
    if any(keyword in text for keyword in commit_message_keywords):
        return "must_fix", "Commit metadata cleanup requested."

    must_fix_keywords = [
        "changes requested",
        "conflict",
        "merge conflict",
        "ci",
        "failed",
        "失败",
        "报错",
        "冲突",
        "注册",
        "register",
        "syntax",
        "命名",
        "naming",
        "order",
        "ordering",
        "should",
        "please",
        "需要",
        "改",
        "fix",
    ]
    reply_keywords = ["why", "为什么", "确认", "question", "?", "？"]
    if any(keyword in text for keyword in must_fix_keywords):
        return "must_fix", "Matched concrete fix-oriented review keywords."
    if any(keyword in text for keyword in reply_keywords):
        return "should_reply", "Looks like a question or clarification request."
    if entry.review_type.startswith("PR Review"):
        return "should_reply", "Top-level review text needs at least a response."
    return "need_human", "Could not confidently classify with deterministic rules."


def shard_key_for(task: ReviewTask, shard_scope: str) -> str:
    if shard_scope == "pr":
        return f"pr-{task.pr_num}"
    if shard_scope == "task":
        return task.task_id
    return f"pr-{task.pr_num}:{task.path or 'top-level'}"


def parse_report(report: Path, limit: int, shard_scope: str = "pr", limit_prs: int = 0) -> list[ReviewTask]:
    markdown = report.read_text(encoding="utf-8")
    tasks: list[ReviewTask] = []
    selected_prs: set[int] = set()
    for idx, entry in enumerate(split_entries(markdown), start=1):
        pr_num, pr_title, pr_state = parse_pr_header(entry)
        if not pr_num:
            continue
        if limit_prs and pr_num not in selected_prs and len(selected_prs) >= limit_prs:
            break
        selected_prs.add(pr_num)
        path_line = field(entry, "文件")
        path = ""
        line = ""
        if path_line:
            path_match = re.match(r"`([^`]+)` \(Line (.*?)\)", path_line)
            if path_match:
                path = path_match.group(1)
                line = path_match.group(2)
        raw_id = field(entry, "评论链接") or f"report-entry-{idx}"
        task_id = f"pr-{pr_num}-review-{sanitize_slug(raw_id.split('#')[-1]) or idx}"
        task = ReviewTask(
            task_id=task_id,
            pr_num=pr_num,
            pr_title=pr_title,
            pr_state=pr_state,
            pr_url=field(entry, "PR"),
            reviewer=field(entry, "评论者"),
            review_type=field(entry, "类型"),
            review_time=field(entry, "时间"),
            reply_status=field(entry, "回复状态"),
            path=path,
            line=line,
            comment_url=field(entry, "评论链接"),
            body=parse_body(entry),
            diff_hunk=parse_diff_hunk(entry),
            decision="",
            decision_reason="",
            shard_key="",
            source_report=str(report),
        )
        task.decision, task.decision_reason = triage(task)
        task.shard_key = shard_key_for(task, shard_scope)
        tasks.append(task)
        if limit and len(tasks) >= limit:
            break
    return tasks


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path, default: object | None = None) -> object:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, rows: Iterable[object]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_tasks(run_dir: Path) -> list[ReviewTask]:
    tasks_path = run_dir / "tasks.jsonl"
    tasks: list[ReviewTask] = []
    with tasks_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                tasks.append(ReviewTask(**json.loads(line)))
    return tasks


def task_dir(run_dir: Path, task: ReviewTask) -> Path:
    return run_dir / "runs" / f"pr-{task.pr_num}" / sanitize_slug(task.task_id)


def resolve_worktree(args: argparse.Namespace, task: ReviewTask) -> Path | None:
    values = {"pr_num": task.pr_num, "task_id": task.task_id}
    if args.worktree_template:
        return Path(render_command(args.worktree_template, values))
    if args.worktree_root:
        return Path(args.worktree_root) / f"pr{task.pr_num}"
    return None


def resolve_external_worktree(args: argparse.Namespace, record: dict[str, object], status: dict[str, object]) -> Path | None:
    pr_num = int(record.get("pr_num", 0) or 0)
    task_id = str(record.get("task_id", ""))
    if args.worktree_template:
        return Path(render_command(args.worktree_template, {"pr_num": pr_num, "task_id": task_id}))
    if args.worktree_root:
        return Path(args.worktree_root) / f"pr{pr_num}"
    worktree_text = str(status.get("worktree") or "")
    return Path(worktree_text) if worktree_text else None


def default_task_status(task: ReviewTask) -> dict[str, object]:
    return {
        "task_id": task.task_id,
        "pr_num": task.pr_num,
        "decision": task.decision,
        "state": "pending" if task.decision in {"must_fix", "should_reply"} else "skipped",
        "round": 0,
        "fixer": {"state": "pending", "last_exit_code": None, "last_log_prefix": ""},
        "claude_review": {"state": "pending", "last_exit_code": None, "decision": "", "last_log_prefix": ""},
        "audit": {"state": "pending", "last_exit_code": None, "decision": "", "last_log_prefix": ""},
        "push": {"state": "pending", "last_exit_code": None, "last_log_prefix": ""},
        "reply": {"state": "pending", "last_exit_code": None, "last_log_prefix": ""},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def read_task_status(run_dir: Path, task: ReviewTask) -> dict[str, object]:
    status_path = task_dir(run_dir, task) / "status.json"
    return read_json(status_path, default_task_status(task))  # type: ignore[return-value]


def task_status_path(run_dir: Path, task: ReviewTask) -> Path:
    return task_dir(run_dir, task) / "status.json"


def write_task_status(run_dir: Path, task: ReviewTask, status: dict[str, object]) -> None:
    status["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(task_dir(run_dir, task) / "status.json", status)


def actionable_tasks(tasks: list[ReviewTask]) -> list[ReviewTask]:
    return [task for task in tasks if task.decision in {"must_fix", "should_reply"}]


def render_task_markdown(task: ReviewTask) -> str:
    diff = task.diff_hunk or "(no diff hunk in review report)"
    return f"""# PR #{task.pr_num} Review Task

## Review

- PR: {task.pr_url}
- Title: {task.pr_title}
- State: {task.pr_state}
- Reviewer: @{task.reviewer}
- Type: {task.review_type}
- Time: {task.review_time}
- File: `{task.path or 'N/A'}` line {task.line or 'N/A'}
- Comment: {task.comment_url or 'N/A'}

## Triage

- Decision: `{task.decision}`
- Reason: {task.decision_reason}

## Review Body

{task.body or '(empty)'}

## Diff Hunk

```diff
{diff}
```
"""


def render_fixer_handoff(task: ReviewTask) -> str:
    commit_message_only = any(
        token in f"{task.body}\n{task.decision_reason}".lower()
        for token in ["co-authored-by", "co-authored by", "commit message", "trailer"]
    )
    commit_message_note = ""
    if commit_message_only:
        commit_message_note = """
## Commit-Message-Only Task

This review is about commit metadata only. Do not change source, tests, config,
or generated files. Inspect and edit only the relevant commit message/history in
the PR worktree. If a source diff already exists from a previous attempt, revert
that unrelated source diff before finishing.
"""
    return f"""# DeepSeek/Claude Handoff: {task.task_id}

You are the fixer for exactly one review item. Do not redesign the task.

## Assigned Review

- PR: #{task.pr_num} {task.pr_title}
- PR URL: {task.pr_url}
- Reviewer: @{task.reviewer}
- Review type: {task.review_type}
- Review URL: {task.comment_url or 'N/A'}
- File: `{task.path or 'N/A'}` line {task.line or 'N/A'}
- Triage decision: `{task.decision}`
- Triage reason: {task.decision_reason}

## Review Body

{task.body or '(empty)'}

## Diff Hunk From Review

```diff
{task.diff_hunk or '(no diff hunk in review report)'}
```

{commit_message_note}

## Required Work

1. Inspect only the relevant PR/worktree context needed for this review.
2. If the triage decision is `must_fix`, make the smallest code change that addresses the review.
3. If the decision is `should_reply`, do not change code unless the code clearly needs it; write a concise reply draft.
4. If the decision is `ignore` or `need_human`, stop and explain why in `execution.md`.
5. Write `execution.md` with what changed, why, and validation.
6. Write `reply_draft.md` for the exact review comment.

## Hard Rules

- Do not modify unrelated files.
- Do not perform broad refactors.
- Do not force push or run destructive git commands.
- Do not post GitHub comments yourself.
- Do not mention AI tools, agents, model names, or internal workflow details in `reply_draft.md`.
- Do not add any `Co-authored-by`, `Co-authored by`, `Generated-by`, or AI attribution trailer anywhere.

## Suggested Reply Style

Keep it short, for example:

```text
Addressed by updating <specific thing>. I also verified <specific check>.
```
"""


def related_task_context(run_dir: Path, task: ReviewTask) -> str:
    tasks_path = run_dir / "tasks.jsonl"
    if not tasks_path.exists():
        return "(not available)"
    rows: list[dict[str, object]] = []
    with tasks_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if int(row.get("pr_num", 0) or 0) != task.pr_num:
                continue
            if row.get("decision") not in {"must_fix", "should_reply"}:
                continue
            rows.append(row)
    if not rows:
        return "(no related tasks)"
    lines: list[str] = []
    for row in rows:
        marker = " (this task)" if row.get("task_id") == task.task_id else ""
        body = str(row.get("body", "")).strip().replace("\n", " ")
        if len(body) > 500:
            body = body[:500] + "..."
        lines.extend(
            [
                f"- `{row.get('task_id')}`{marker}",
                f"  - File: `{row.get('path') or 'top-level'}` line {row.get('line') or 'N/A'}",
                f"  - Review URL: {row.get('comment_url') or 'N/A'}",
                f"  - Body: {body or '(empty)'}",
            ]
        )
    return "\n".join(lines)


def tail_text(path: Path, limit: int = 6000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-limit:]


def task_feedback_context(out_dir: Path) -> str:
    sections: list[str] = []
    validation = tail_text(out_dir / "local_validation.md", 7000)
    if validation:
        sections.extend(
            [
                "### Previous Local Validation",
                "",
                "```text",
                validation,
                "```",
                "",
            ]
        )
    audit_json = out_dir / "codex_audit.json"
    claude_review_json = out_dir / "claude_review.json"
    if claude_review_json.exists():
        try:
            review = json.loads(claude_review_json.read_text(encoding="utf-8"))
            sections.extend(
                [
                    "### Previous Claude Review Gate",
                    "",
                    f"- Decision: `{review.get('decision', '')}`",
                    f"- Summary: {review.get('summary', '')}",
                    "",
                ]
            )
            findings = review.get("findings", [])
            if findings:
                sections.append("Findings:")
                for item in findings:
                    if isinstance(item, dict):
                        location = item.get("file") or ""
                        line = item.get("line")
                        if line:
                            location = f"{location}:{line}" if location else str(line)
                        sections.append(f"- {location} {item.get('message', '')}".strip())
                    else:
                        sections.append(f"- {item}")
                sections.append("")
            required = review.get("required_changes", [])
            if required:
                sections.append("Required changes:")
                for item in required:
                    sections.append(f"- {item}")
                sections.append("")
        except json.JSONDecodeError:
            sections.extend(["### Previous Claude Review Gate", "", tail_text(claude_review_json, 4000), ""])

    if audit_json.exists():
        try:
            audit = json.loads(audit_json.read_text(encoding="utf-8"))
            sections.extend(
                [
                    "### Previous Codex Audit",
                    "",
                    f"- Decision: `{audit.get('decision', '')}`",
                    f"- Summary: {audit.get('summary', '')}",
                    "",
                ]
            )
            findings = audit.get("findings", [])
            if findings:
                sections.append("Findings:")
                for item in findings:
                    if isinstance(item, dict):
                        location = item.get("file") or ""
                        line = item.get("line")
                        if line:
                            location = f"{location}:{line}" if location else str(line)
                        sections.append(f"- {location} {item.get('message', '')}".strip())
                    else:
                        sections.append(f"- {item}")
                sections.append("")
            required = audit.get("required_changes", [])
            if required:
                sections.append("Required changes:")
                for item in required:
                    sections.append(f"- {item}")
                sections.append("")
        except json.JSONDecodeError:
            sections.extend(["### Previous Codex Audit", "", tail_text(audit_json, 4000), ""])
    execution = tail_text(out_dir / "execution.md", 3000)
    if execution:
        sections.extend(
            [
                "### Previous Execution Notes",
                "",
                "```text",
                execution,
                "```",
                "",
            ]
        )
    return "\n".join(sections).strip()


def render_audit_prompt(task: ReviewTask, run_dir: Path | None = None) -> str:
    related = related_task_context(run_dir, task) if run_dir else "(not available)"
    return f"""# Codex Audit: {task.task_id}

Review the fixer output for this PR review item.

## Original Review

- PR: #{task.pr_num} {task.pr_title}
- PR URL: {task.pr_url}
- Reviewer: @{task.reviewer}
- Review URL: {task.comment_url or 'N/A'}
- File: `{task.path or 'N/A'}` line {task.line or 'N/A'}
- Triage: `{task.decision}` - {task.decision_reason}

## Review Body

{task.body or '(empty)'}

## Same-PR Review Context

{related}

When multiple actionable reviews exist on the same PR, judge whether the combined
worktree diff reasonably addresses those same-PR reviews. Do not reject a fix as
unrelated merely because it addresses another review listed above. Still reject
changes outside the same PR review context.

## Audit Inputs To Read

- `task.json`
- `fixer_handoff.md`
- `execution.md` if present
- `reply_draft.md` if present
- current `git diff`
- validation logs if present

## Required Output

Write `codex_audit.json`:

```json
{{
  "decision": "approved | needs_revision | needs_human",
  "summary": "...",
  "findings": [
    {{
      "severity": "blocking | warning | note",
      "file": "...",
      "line": 123,
      "message": "..."
    }}
  ],
  "required_changes": [
    "..."
  ],
  "reply_to_reviewer": "..."
}}
```

Check that the fix addresses the review, avoids unrelated changes, has adequate validation, and does not add forbidden attribution trailers.
"""


def render_external_audit_prompt(record: dict[str, object]) -> str:
    task_type = str(record.get("task_type", "external_fix"))
    pr_num = record.get("pr_num", "")
    task_dir_path = Path(str(record["task_dir"]))
    summary_name = "ci_failure_summary.md" if task_type == "ci_fix" else "rebase_conflict_summary.md"
    return f"""# Codex Audit: {record.get('task_id', task_dir_path.name)}

Review the fixer output for this generated follow-up task.

## Task

- Type: `{task_type}`
- PR: #{pr_num}
- Task dir: `{task_dir_path}`

## Audit Inputs To Read

- `task.json`
- `fixer_handoff.md`
- `{summary_name}` if present
- `execution.md` if present
- `local_validation.md` if present
- current `git diff`

## Required Output

Write `codex_audit.json`:

```json
{{
  "decision": "approved | needs_revision | needs_human",
  "summary": "...",
  "findings": [
    {{
      "severity": "blocking | warning | note",
      "file": "...",
      "line": 123,
      "message": "..."
    }}
  ],
  "required_changes": [
    "..."
  ],
  "reply_to_reviewer": ""
}}
```

Check that the fix resolves the generated follow-up task, avoids unrelated changes, passes validation, and does not add forbidden attribution trailers.
"""


def ensure_external_audit_prompt(record: dict[str, object]) -> None:
    out_dir = Path(str(record["task_dir"]))
    prompt = out_dir / "codex_audit_prompt.md"
    if not prompt.exists():
        prompt.write_text(render_external_audit_prompt(record), encoding="utf-8")


def write_task_files(run_dir: Path, task: ReviewTask) -> None:
    out_dir = task_dir(run_dir, task)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "task.json", asdict(task))
    if not (out_dir / "status.json").exists():
        write_task_status(run_dir, task, default_task_status(task))
    (out_dir / "task.md").write_text(render_task_markdown(task), encoding="utf-8")
    (out_dir / "fixer_handoff.md").write_text(render_fixer_handoff(task), encoding="utf-8")
    (out_dir / "codex_audit_prompt.md").write_text(render_audit_prompt(task, run_dir), encoding="utf-8")
    if not (out_dir / "execution.md").exists():
        (out_dir / "execution.md").write_text("# Execution\n\nStatus: pending\n", encoding="utf-8")
    if not (out_dir / "reply_draft.md").exists():
        (out_dir / "reply_draft.md").write_text(
            "# Reply Draft\n\n"
            "Status: pending\n\n"
            "Write the final short reply here after the fix is verified.\n",
            encoding="utf-8",
        )
    if not (out_dir / "final_report.md").exists():
        (out_dir / "final_report.md").write_text(
            render_task_markdown(task)
            + "\n## Execution\n\nPending.\n\n"
            + "## Codex Audit\n\nPending.\n\n"
            + "## Review Line Reply Draft\n\nPending.\n",
            encoding="utf-8",
        )


def group_shards(tasks: list[ReviewTask], max_reviews_per_fixer: int, shard_scope: str = "pr") -> list[list[ReviewTask]]:
    actionable = [task for task in tasks if task.decision in {"must_fix", "should_reply"}]
    by_key: dict[str, list[ReviewTask]] = {}
    for task in actionable:
        by_key.setdefault(task.shard_key, []).append(task)

    shards: list[list[ReviewTask]] = []
    for items in by_key.values():
        if shard_scope == "pr":
            shards.append(items)
            continue
        for i in range(0, len(items), max_reviews_per_fixer):
            shards.append(items[i : i + max_reviews_per_fixer])
    return shards


def write_shards(run_dir: Path, shards: list[list[ReviewTask]]) -> None:
    shard_root = run_dir / "runs" / "shards"
    shard_root.mkdir(parents=True, exist_ok=True)
    for index, shard in enumerate(shards, start=1):
        shard_dir = shard_root / f"shard-{index:03d}"
        shard_dir.mkdir(parents=True, exist_ok=True)
        write_json(shard_dir / "shard.json", [asdict(task) for task in shard])
        body = [
            f"# Fix Shard {index:03d}",
            "",
            "Process these review tasks in this shard only.",
            "",
            "Hard rules:",
            "",
            "- Keep changes scoped to the assigned reviews.",
            "- Write one reply draft per review task.",
            "- Do not post comments or push.",
            "- Do not add Co-authored-by, Generated-by, or AI attribution.",
            "",
            "## Tasks",
            "",
        ]
        for task in shard:
            rel = task_dir(run_dir, task).relative_to(run_dir)
            feedback = task_feedback_context(task_dir(run_dir, task))
            body.extend(
                [
                    f"### {task.task_id}",
                    "",
                    f"- PR: #{task.pr_num}",
                    f"- File: `{task.path or 'N/A'}` line {task.line or 'N/A'}",
                    f"- Decision: `{task.decision}`",
                    f"- Task dir: `{rel}`",
                    "",
                    task.body or "(empty)",
                    "",
                ]
            )
            if feedback:
                body.extend(
                    [
                        "#### Feedback From Previous Attempt",
                        "",
                        feedback,
                        "",
                        "Use this feedback as the primary instruction for the next fix attempt. "
                        "Fix only the listed validation/audit issues, and revert unrelated changes.",
                        "",
                    ]
                )
        (shard_dir / "fixer_shard_handoff.md").write_text("\n".join(body), encoding="utf-8")


def external_task_records(run_dir: Path, include_terminal: bool = False) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    runs_root = run_dir / "runs"
    if not runs_root.exists():
        return records
    task_jsons: list[Path] = []
    for pattern in EXTERNAL_TASK_GLOBS:
        task_jsons.extend(sorted(runs_root.glob(pattern)))
    for task_json in task_jsons:
        task_dir_path = task_json.parent
        status = read_json(task_dir_path / "status.json", {})  # type: ignore[assignment]
        if not isinstance(status, dict):
            status = {}
        state = str(status.get("state", "pending"))
        if not include_terminal and state in EXTERNAL_TERMINAL_STATES:
            continue
        data = read_json(task_json, {})  # type: ignore[assignment]
        if not isinstance(data, dict):
            continue
        task_type = str(data.get("task_type") or ("ci_fix" if "ci-fix-" in str(task_dir_path) else "rebase_conflict_fix"))
        pr_num = int(data.get("pr_num", 0) or 0)
        task_id = f"external-{task_type}-pr-{pr_num}-{task_dir_path.name}"
        record = {
            "external": True,
            "task_id": task_id,
            "task_type": task_type,
            "pr_num": pr_num,
            "task_dir": str(task_dir_path),
            "status_path": str(task_dir_path / "status.json"),
            "handoff": str(task_dir_path / "fixer_handoff.md"),
            "summary": str(task_dir_path / ("ci_failure_summary.md" if task_type == "ci_fix" else "rebase_conflict_summary.md")),
            "shard_key": f"pr-{pr_num}:{task_type}",
            "state": state,
            "data": data,
            "status": status,
        }
        ensure_external_audit_prompt(record)
        records.append(record)
    return records


def discover_external_fix_tasks(run_dir: Path) -> list[dict[str, object]]:
    return [
        record
        for record in external_task_records(run_dir)
        if str(record.get("state", "pending")) in EXTERNAL_FIXER_STATES
    ]


def write_external_shards(run_dir: Path, tasks: list[dict[str, object]], max_reviews_per_fixer: int) -> list[Path]:
    if not tasks:
        return []
    shard_root = run_dir / "runs" / "shards"
    shard_root.mkdir(parents=True, exist_ok=True)
    by_key: dict[str, list[dict[str, object]]] = {}
    for task in tasks:
        by_key.setdefault(str(task.get("shard_key", "external")), []).append(task)

    written: list[Path] = []
    index = 1
    for items in by_key.values():
        for start in range(0, len(items), max_reviews_per_fixer):
            shard_items = items[start : start + max_reviews_per_fixer]
            shard_dir = shard_root / f"shard-ext-{index:03d}"
            index += 1
            shard_dir.mkdir(parents=True, exist_ok=True)
            write_json(shard_dir / "shard.json", shard_items)
            body = [
                f"# External Fix Shard {shard_dir.name}",
                "",
                "Process these generated fix tasks only.",
                "",
                "Hard rules:",
                "",
                "- Do not post GitHub comments.",
                "- Do not force push.",
                "- Do not add Co-authored-by, Generated-by, or AI attribution.",
                "- Keep unrelated files untouched.",
                "",
                "## Tasks",
                "",
            ]
            for task in shard_items:
                task_dir_path = Path(str(task["task_dir"]))
                summary_path = Path(str(task["summary"]))
                rel = task_dir_path.relative_to(run_dir) if task_dir_path.is_relative_to(run_dir) else task_dir_path
                body.extend(
                    [
                        f"### {task['task_id']}",
                        "",
                        f"- Type: `{task['task_type']}`",
                        f"- PR: #{task['pr_num']}",
                        f"- Task dir: `{rel}`",
                        f"- Handoff: `{task['handoff']}`",
                        f"- Summary: `{task['summary']}`",
                        "",
                    ]
                )
                if summary_path.exists():
                    body.extend([summary_path.read_text(encoding="utf-8")[:6000], ""])
                feedback = task_feedback_context(task_dir_path)
                if feedback:
                    body.extend(
                        [
                            "#### Feedback From Previous Attempt",
                            "",
                            feedback,
                            "",
                            "Use this feedback as the primary instruction for the next fix attempt. "
                            "Fix only the listed validation/audit/review issues, and revert unrelated changes.",
                            "",
                        ]
                    )
            (shard_dir / "fixer_shard_handoff.md").write_text("\n".join(body), encoding="utf-8")
            written.append(shard_dir)
    return written


def refresh_external_shards(run_dir: Path, args: argparse.Namespace) -> list[Path]:
    for old in (run_dir / "runs" / "shards").glob("shard-ext-*"):
        if old.is_dir():
            shutil.rmtree(old)
    return write_external_shards(run_dir, discover_external_fix_tasks(run_dir), args.max_reviews_per_fixer)


def refresh_review_shards(run_dir: Path, tasks: list[ReviewTask], args: argparse.Namespace) -> list[list[ReviewTask]]:
    shards = group_shards(tasks, args.max_reviews_per_fixer, args.shard_scope)
    write_shards(run_dir, shards)
    return shards


def shard_dirs(run_dir: Path) -> list[Path]:
    root = run_dir / "runs" / "shards"
    if not root.exists():
        return []
    return sorted(path for path in root.glob("shard-*") if path.is_dir())


def load_shard_tasks(shard_dir: Path) -> list[dict[str, object]]:
    shard_json = shard_dir / "shard.json"
    return read_json(shard_json, [])  # type: ignore[return-value]


def mark_shard_tasks(
    run_dir: Path,
    shard_tasks: list[dict[str, object]],
    state: str,
    round_number: int,
    max_fix_rounds: int,
    result: subprocess.CompletedProcess[str] | None,
    log_prefix: Path,
) -> None:
    for row in shard_tasks:
        if row.get("external"):
            task_dir_path = Path(str(row["task_dir"]))
            status_path = task_dir_path / "status.json"
            status = read_json(status_path, {})  # type: ignore[assignment]
            if not isinstance(status, dict):
                status = {}
            if status.get("state") in {"completed", "fixed", "needs_human"}:
                continue
            fixer_status = status.setdefault("fixer", {})
            if isinstance(fixer_status, dict):
                fixer_status["state"] = state
                fixer_status["last_exit_code"] = result.returncode if result else None
                fixer_status["last_log_prefix"] = str(log_prefix)
            status["round"] = round_number
            if state == "completed":
                status["state"] = "fixed"
            elif round_number >= max_fix_rounds:
                status["state"] = "needs_human"
            else:
                status["state"] = "fix_failed"
            status["updated_at"] = datetime.now(timezone.utc).isoformat()
            write_json(status_path, status)
            continue
        task = ReviewTask(**row)
        status = read_task_status(run_dir, task)
        if status.get("state") in {"approved", "local_approved", "ci_passed", "done", "needs_human", "skipped"}:
            continue
        fixer_status = status.setdefault("fixer", {})
        if isinstance(fixer_status, dict):
            fixer_status["state"] = state
            fixer_status["last_exit_code"] = result.returncode if result else None
            fixer_status["last_log_prefix"] = str(log_prefix)
        status["round"] = round_number
        if state == "completed":
            status["state"] = "fixed"
        elif round_number >= max_fix_rounds:
            status["state"] = "needs_human"
        else:
            status["state"] = "fix_failed"
        write_task_status(run_dir, task, status)


def shard_has_active_work(run_dir: Path, shard_dir: Path) -> bool:
    for row in load_shard_tasks(shard_dir):
        if row.get("external"):
            status = read_json(Path(str(row["task_dir"])) / "status.json", {})  # type: ignore[assignment]
            if not isinstance(status, dict):
                return True
            if status.get("state") in {"pending", "needs_revision", "fix_failed"}:
                return True
            continue
        task = ReviewTask(**row)
        if read_task_status(run_dir, task).get("state") in {"pending", "needs_revision", "fix_failed"}:
            return True
    return False


def shard_command_values(
    run_dir: Path,
    shard_dir: Path,
    shard_tasks: list[dict[str, object]],
    args: argparse.Namespace,
) -> dict[str, object]:
    values: dict[str, object] = {
        "run_dir": run_dir,
        "shard_dir": shard_dir,
        "handoff": shard_dir / "fixer_shard_handoff.md",
        "task_dir": shard_dir,
        "task_id": "",
        "pr_num": "",
        "path": "",
        "worktree": "",
    }
    pr_nums = sorted({int(row.get("pr_num", 0) or 0) for row in shard_tasks if int(row.get("pr_num", 0) or 0)})
    if len(pr_nums) == 1:
        values["pr_num"] = pr_nums[0]
        if args.worktree_root:
            values["worktree"] = Path(args.worktree_root) / f"pr{pr_nums[0]}"
        elif args.worktree_template:
            values["worktree"] = render_command(args.worktree_template, {"pr_num": pr_nums[0], "task_id": ""})
    if len(shard_tasks) != 1:
        return values

    row = shard_tasks[0]
    values["task_id"] = row.get("task_id", "")
    values["pr_num"] = row.get("pr_num", "")
    values["path"] = row.get("path", "")
    if row.get("external"):
        values["task_dir"] = row.get("task_dir", shard_dir)
        status = read_json(Path(str(row["task_dir"])) / "status.json", {})  # type: ignore[assignment]
        if isinstance(status, dict) and status.get("worktree"):
            values["worktree"] = status.get("worktree", "")
    else:
        task = ReviewTask(**row)
        values["task_dir"] = task_dir(run_dir, task)
    return values


def execute_fixers(run_dir: Path, args: argparse.Namespace, round_number: int) -> list[dict[str, object]]:
    if args.dry_run or not args.execute_fixers:
        return []
    if not args.fixer_command:
        raise ValueError("--execute-fixers requires --fixer-command")

    results: list[dict[str, object]] = []
    shards = shard_dirs(run_dir)
    if not shards:
        return results
    shards = [shard for shard in shards if shard_has_active_work(run_dir, shard)]
    if not shards:
        return results

    def run_one(shard_dir: Path) -> dict[str, object]:
        shard_tasks = load_shard_tasks(shard_dir)
        values = shard_command_values(run_dir, shard_dir, shard_tasks, args)
        values["round"] = round_number
        handoff = Path(str(values["handoff"]))
        log_prefix = shard_dir / f"round-{round_number:02d}-fixer"
        command = render_command(args.fixer_command, values)
        result = run_shell(command, shard_dir, log_prefix, args.command_timeout)
        state = "completed" if result.returncode == 0 else "failed"
        mark_shard_tasks(run_dir, shard_tasks, state, round_number, args.max_fix_rounds, result, log_prefix)
        return {
            "shard_dir": str(shard_dir),
            "round": round_number,
            "exit_code": result.returncode,
            "state": state,
            "log_prefix": str(log_prefix),
        }

    with ThreadPoolExecutor(max_workers=max(1, args.fixer_parallelism)) as executor:
        future_map = {executor.submit(run_one, shard): shard for shard in shards}
        for future in as_completed(future_map):
            results.append(future.result())
    write_json(run_dir / f"fixer_results_round_{round_number:02d}.json", results)
    return results


def normalize_audit_decision(value: str) -> str:
    decision = value.strip().lower().replace("-", "_").replace(" ", "_")
    approved = {"approved", "approve", "pass", "passed", "ok", "accepted", "accept"}
    needs_revision = {
        "needs_revision",
        "changes_requested",
        "change_requested",
        "request_changes",
        "requested_changes",
        "failed",
        "fail",
        "rejected",
        "needs_changes",
    }
    needs_human = {"needs_human", "human", "manual", "blocked", "unclear", "unknown"}
    if decision in approved:
        return "approved"
    if decision in needs_revision:
        return "needs_revision"
    if decision in needs_human:
        return "needs_human"
    return ""


def parse_audit_decision(task_out_dir: Path) -> str:
    audit_json = task_out_dir / "codex_audit.json"
    if audit_json.exists():
        try:
            data = json.loads(audit_json.read_text(encoding="utf-8"))
            decision = normalize_audit_decision(str(data.get("decision", "")))
            if decision:
                return decision
        except json.JSONDecodeError:
            return "needs_human"

    audit_md = task_out_dir / "codex_audit.md"
    if audit_md.exists():
        text = audit_md.read_text(encoding="utf-8").lower()
        for raw in ["needs_revision", "changes_requested", "needs_human", "approved", "approve", "pass"]:
            if raw in text:
                decision = normalize_audit_decision(raw)
                if decision:
                    return decision
    return "needs_human"


def parse_claude_review_decision(task_out_dir: Path) -> str:
    review_json = task_out_dir / "claude_review.json"
    if review_json.exists():
        try:
            data = json.loads(review_json.read_text(encoding="utf-8"))
            decision = normalize_audit_decision(str(data.get("decision", "")))
            if decision:
                return decision
            raw = str(data.get("decision", "")).strip().lower().replace("-", "_").replace(" ", "_")
            if raw in {"skip", "skipped", "ignore", "no_action"}:
                return "skip"
        except json.JSONDecodeError:
            return "needs_human"
    return "needs_human"


def execute_local_validation(
    run_dir: Path,
    tasks: list[ReviewTask],
    args: argparse.Namespace,
    round_number: int,
) -> list[dict[str, object]]:
    if args.dry_run or not args.execute_local_validation:
        return []

    results: list[dict[str, object]] = []
    for task in actionable_tasks(tasks):
        out_dir = task_dir(run_dir, task)
        status = read_task_status(run_dir, task)
        if status.get("state") in {"approved", "local_approved", "needs_human", "skipped", "fix_failed"}:
            continue
        if status.get("state") not in {"fixed", "needs_revision", "validation_failed"}:
            continue
        log_prefix = out_dir / f"round-{round_number:02d}-validation"
        values = {
            "run_dir": run_dir,
            "task_dir": out_dir,
            "round": round_number,
            "task_id": task.task_id,
            "pr_num": task.pr_num,
            "path": task.path,
            "worktree": resolve_worktree(args, task) or "",
        }
        if args.validation_command:
            command = render_command(args.validation_command, values)
        else:
            worktree = resolve_worktree(args, task)
            if not worktree:
                raise ValueError(
                    "--execute-local-validation requires --validation-command, "
                    "--worktree-template, or --worktree-root"
                )
            command = (
                f"{shlex.quote(sys.executable)} "
                f"{shlex.quote(str(ROOT / 'tools' / 'validate_changed_files.py'))} "
                f"--worktree {shlex.quote(str(worktree))} "
                f"--task-dir {shlex.quote(str(out_dir))}"
            )
        result = run_shell(command, out_dir, log_prefix, args.command_timeout)
        if args.validation_command:
            write_shell_validation_report(out_dir, command, result)
        validation_status = status.setdefault("local_validation", {})
        if isinstance(validation_status, dict):
            validation_status["state"] = "passed" if result.returncode == 0 else "failed"
            validation_status["last_exit_code"] = result.returncode
            validation_status["last_log_prefix"] = str(log_prefix)
        status["round"] = round_number
        if result.returncode == 0:
            status["state"] = "validated"
        elif round_number < args.max_fix_rounds:
            status["state"] = "needs_revision"
        else:
            status["state"] = "needs_human"
        write_task_status(run_dir, task, status)
        results.append(
            {
                "task_id": task.task_id,
                "round": round_number,
                "exit_code": result.returncode,
                "state": status["state"],
                "log_prefix": str(log_prefix),
            }
        )
    write_json(run_dir / f"validation_results_round_{round_number:02d}.json", results)
    return results


def write_shell_validation_report(task_dir: Path, command: str, result: subprocess.CompletedProcess[str]) -> None:
    summary = {
        "changed_files": [],
        "pytest_targets": [],
        "results": [
            {
                "cmd": command,
                "exit_code": result.returncode,
            }
        ],
    }
    write_json(task_dir / "local_validation.json", summary)
    lines = [
        "# Local Validation",
        "",
        "## Command",
        "",
        f"`{command}`",
        "",
        f"Exit code: `{result.returncode}`",
        "",
        "stdout:",
        "",
        "```text",
        (result.stdout or "")[-4000:],
        "```",
        "",
        "stderr:",
        "",
        "```text",
        (result.stderr or "")[-4000:],
        "```",
        "",
    ]
    (task_dir / "local_validation.md").write_text("\n".join(lines), encoding="utf-8")


def execute_external_local_validation(run_dir: Path, args: argparse.Namespace, round_number: int) -> list[dict[str, object]]:
    if args.dry_run or not args.execute_local_validation:
        return []

    results: list[dict[str, object]] = []
    for record in external_task_records(run_dir):
        out_dir = Path(str(record["task_dir"]))
        status = read_json(out_dir / "status.json", {})  # type: ignore[assignment]
        if not isinstance(status, dict):
            continue
        if status.get("state") not in {"fixed", "validation_failed"}:
            continue
        log_prefix = out_dir / f"round-{round_number:02d}-validation"
        values = {
            "run_dir": run_dir,
            "task_dir": out_dir,
            "round": round_number,
            "task_id": record.get("task_id", ""),
            "pr_num": record.get("pr_num", ""),
            "path": "",
            "worktree": resolve_external_worktree(args, record, status) or "",
        }
        if args.validation_command:
            command = render_command(args.validation_command, values)
        else:
            worktree = resolve_external_worktree(args, record, status)
            if not worktree:
                raise ValueError(
                    "external validation requires --validation-command, "
                    "--worktree-template, --worktree-root, or status.worktree"
                )
            command = (
                f"{shlex.quote(sys.executable)} "
                f"{shlex.quote(str(ROOT / 'tools' / 'validate_changed_files.py'))} "
                f"--worktree {shlex.quote(str(worktree))} "
                f"--task-dir {shlex.quote(str(out_dir))}"
            )
        result = run_shell(command, out_dir, log_prefix, args.command_timeout)
        if args.validation_command:
            write_shell_validation_report(out_dir, command, result)
        validation_status = status.setdefault("local_validation", {})
        if isinstance(validation_status, dict):
            validation_status["state"] = "passed" if result.returncode == 0 else "failed"
            validation_status["last_exit_code"] = result.returncode
            validation_status["last_log_prefix"] = str(log_prefix)
        status["round"] = round_number
        if result.returncode == 0:
            status["state"] = "validated"
        elif round_number < args.max_fix_rounds:
            status["state"] = "needs_revision"
        else:
            status["state"] = "needs_human"
        status["updated_at"] = datetime.now(timezone.utc).isoformat()
        write_json(out_dir / "status.json", status)
        results.append(
            {
                "task_id": record.get("task_id", ""),
                "task_type": record.get("task_type", ""),
                "pr_num": record.get("pr_num", ""),
                "round": round_number,
                "exit_code": result.returncode,
                "state": status["state"],
                "log_prefix": str(log_prefix),
            }
        )
    write_json(run_dir / f"external_validation_results_round_{round_number:02d}.json", results)
    return results


def execute_claude_reviews(
    run_dir: Path,
    tasks: list[ReviewTask],
    args: argparse.Namespace,
    round_number: int,
) -> list[dict[str, object]]:
    if args.dry_run or not args.execute_claude_review:
        return []
    if not args.claude_review_command:
        raise ValueError("--execute-claude-review requires --claude-review-command")

    results: list[dict[str, object]] = []
    for task in actionable_tasks(tasks):
        out_dir = task_dir(run_dir, task)
        status = read_task_status(run_dir, task)
        if status.get("state") in {
            "approved",
            "local_approved",
            "ci_passed",
            "done",
            "ci_failed",
            "needs_human",
            "skipped",
            "fix_failed",
        }:
            continue
        required_state = "validated" if args.execute_local_validation else "fixed"
        if status.get("state") != required_state:
            continue
        log_prefix = out_dir / f"round-{round_number:02d}-claude-review"
        command = render_command(
            args.claude_review_command,
            {
                "run_dir": run_dir,
                "task_dir": out_dir,
                "round": round_number,
                "task_id": task.task_id,
                "pr_num": task.pr_num,
                "path": task.path,
                "worktree": resolve_worktree(args, task) or "",
            },
        )
        result = run_shell(command, out_dir, log_prefix, args.command_timeout)
        decision = parse_claude_review_decision(out_dir) if result.returncode == 0 else "needs_revision"
        review_status = status.setdefault("claude_review", {})
        if isinstance(review_status, dict):
            review_status["state"] = "completed" if result.returncode == 0 else "failed"
            review_status["last_exit_code"] = result.returncode
            review_status["decision"] = decision
            review_status["last_log_prefix"] = str(log_prefix)
        status["round"] = round_number
        if decision == "approved":
            status["state"] = "reviewed"
        elif decision == "skip":
            status["state"] = "skipped"
        elif decision == "needs_revision" and round_number < args.max_fix_rounds:
            status["state"] = "needs_revision"
        else:
            status["state"] = "needs_human"
        write_task_status(run_dir, task, status)
        results.append(
            {
                "task_id": task.task_id,
                "round": round_number,
                "exit_code": result.returncode,
                "decision": decision,
                "state": status["state"],
                "log_prefix": str(log_prefix),
            }
        )
    write_json(run_dir / f"claude_review_results_round_{round_number:02d}.json", results)
    return results


def execute_external_claude_reviews(run_dir: Path, args: argparse.Namespace, round_number: int) -> list[dict[str, object]]:
    if args.dry_run or not args.execute_claude_review:
        return []
    if not args.claude_review_command:
        raise ValueError("--execute-claude-review requires --claude-review-command")

    results: list[dict[str, object]] = []
    for record in external_task_records(run_dir):
        out_dir = Path(str(record["task_dir"]))
        status = read_json(out_dir / "status.json", {})  # type: ignore[assignment]
        if not isinstance(status, dict):
            continue
        if status.get("state") in {"local_approved", "ci_passed", "done", "needs_human", "skipped", "fix_failed"}:
            continue
        required_state = "validated" if args.execute_local_validation else "fixed"
        if status.get("state") != required_state:
            continue
        log_prefix = out_dir / f"round-{round_number:02d}-claude-review"
        worktree = resolve_external_worktree(args, record, status)
        command = render_command(
            args.claude_review_command,
            {
                "run_dir": run_dir,
                "task_dir": out_dir,
                "round": round_number,
                "task_id": record.get("task_id", ""),
                "pr_num": record.get("pr_num", ""),
                "path": "",
                "worktree": worktree or "",
            },
        )
        result = run_shell(command, out_dir, log_prefix, args.command_timeout)
        decision = parse_claude_review_decision(out_dir) if result.returncode == 0 else "needs_revision"
        review_status = status.setdefault("claude_review", {})
        if isinstance(review_status, dict):
            review_status["state"] = "completed" if result.returncode == 0 else "failed"
            review_status["last_exit_code"] = result.returncode
            review_status["decision"] = decision
            review_status["last_log_prefix"] = str(log_prefix)
        status["round"] = round_number
        if decision == "approved":
            status["state"] = "reviewed"
        elif decision == "skip":
            status["state"] = "skipped"
        elif decision == "needs_revision" and round_number < args.max_fix_rounds:
            status["state"] = "needs_revision"
        else:
            status["state"] = "needs_human"
        status["updated_at"] = datetime.now(timezone.utc).isoformat()
        write_json(out_dir / "status.json", status)
        results.append(
            {
                "task_id": record.get("task_id", ""),
                "task_type": record.get("task_type", ""),
                "pr_num": record.get("pr_num", ""),
                "round": round_number,
                "exit_code": result.returncode,
                "decision": decision,
                "state": status["state"],
                "log_prefix": str(log_prefix),
            }
        )
    write_json(run_dir / f"external_claude_review_results_round_{round_number:02d}.json", results)
    return results


def execute_audits(run_dir: Path, tasks: list[ReviewTask], args: argparse.Namespace, round_number: int) -> list[dict[str, object]]:
    if args.dry_run or not args.execute_audit:
        return []
    if not args.audit_command:
        raise ValueError("--execute-audit requires --audit-command")

    results: list[dict[str, object]] = []
    for task in actionable_tasks(tasks):
        out_dir = task_dir(run_dir, task)
        status = read_task_status(run_dir, task)
        if status.get("state") in {
            "approved",
            "local_approved",
            "ci_passed",
            "done",
            "ci_failed",
            "needs_human",
            "skipped",
            "fix_failed",
        }:
            continue
        if args.execute_claude_review:
            if status.get("state") != "reviewed":
                continue
        elif args.execute_local_validation and status.get("state") != "validated":
            continue
        log_prefix = out_dir / f"round-{round_number:02d}-audit"
        command = render_command(
            args.audit_command,
            {
                "run_dir": run_dir,
                "task_dir": out_dir,
                "audit_prompt": out_dir / "codex_audit_prompt.md",
                "round": round_number,
                "task_id": task.task_id,
                "pr_num": task.pr_num,
                "path": task.path,
                "worktree": resolve_worktree(args, task) or "",
            },
        )
        result = run_shell(command, out_dir, log_prefix, args.command_timeout)
        decision = parse_audit_decision(out_dir) if result.returncode == 0 else "needs_revision"
        audit_status = status.setdefault("audit", {})
        if isinstance(audit_status, dict):
            audit_status["state"] = "completed" if result.returncode == 0 else "failed"
            audit_status["last_exit_code"] = result.returncode
            audit_status["decision"] = decision
            audit_status["last_log_prefix"] = str(log_prefix)
        status["round"] = round_number
        if decision == "approved":
            status["state"] = "local_approved"
        elif decision == "needs_revision" and round_number < args.max_fix_rounds:
            status["state"] = "needs_revision"
        elif decision == "needs_revision":
            status["state"] = "needs_human"
        else:
            status["state"] = "needs_human"
        write_task_status(run_dir, task, status)
        results.append(
            {
                "task_id": task.task_id,
                "round": round_number,
                "exit_code": result.returncode,
                "decision": decision,
                "state": status["state"],
                "log_prefix": str(log_prefix),
            }
        )
    write_json(run_dir / f"audit_results_round_{round_number:02d}.json", results)
    return results


def execute_external_audits(run_dir: Path, args: argparse.Namespace, round_number: int) -> list[dict[str, object]]:
    if args.dry_run or not args.execute_audit:
        return []
    if not args.audit_command:
        raise ValueError("--execute-audit requires --audit-command")

    results: list[dict[str, object]] = []
    for record in external_task_records(run_dir):
        out_dir = Path(str(record["task_dir"]))
        status = read_json(out_dir / "status.json", {})  # type: ignore[assignment]
        if not isinstance(status, dict):
            continue
        if status.get("state") in {"local_approved", "ci_passed", "done", "needs_human", "skipped", "fix_failed"}:
            continue
        if args.execute_claude_review:
            if status.get("state") != "reviewed":
                continue
        elif args.execute_local_validation:
            if status.get("state") != "validated":
                continue
        elif status.get("state") not in {"fixed"}:
            continue
        log_prefix = out_dir / f"round-{round_number:02d}-audit"
        worktree = resolve_external_worktree(args, record, status)
        command = render_command(
            args.audit_command,
            {
                "run_dir": run_dir,
                "task_dir": out_dir,
                "audit_prompt": out_dir / "codex_audit_prompt.md",
                "round": round_number,
                "task_id": record.get("task_id", ""),
                "pr_num": record.get("pr_num", ""),
                "path": "",
                "worktree": worktree or "",
            },
        )
        result = run_shell(command, out_dir, log_prefix, args.command_timeout)
        decision = parse_audit_decision(out_dir) if result.returncode == 0 else "needs_revision"
        audit_status = status.setdefault("audit", {})
        if isinstance(audit_status, dict):
            audit_status["state"] = "completed" if result.returncode == 0 else "failed"
            audit_status["last_exit_code"] = result.returncode
            audit_status["decision"] = decision
            audit_status["last_log_prefix"] = str(log_prefix)
        status["round"] = round_number
        if decision == "approved":
            status["state"] = "local_approved"
        elif decision == "needs_revision" and round_number < args.max_fix_rounds:
            status["state"] = "needs_revision"
        elif decision == "needs_revision":
            status["state"] = "needs_human"
        else:
            status["state"] = "needs_human"
        status["updated_at"] = datetime.now(timezone.utc).isoformat()
        write_json(out_dir / "status.json", status)
        results.append(
            {
                "task_id": record.get("task_id", ""),
                "task_type": record.get("task_type", ""),
                "pr_num": record.get("pr_num", ""),
                "round": round_number,
                "exit_code": result.returncode,
                "decision": decision,
                "state": status["state"],
                "log_prefix": str(log_prefix),
            }
        )
    write_json(run_dir / f"external_audit_results_round_{round_number:02d}.json", results)
    return results


def all_actionable_approved(run_dir: Path, tasks: list[ReviewTask]) -> bool:
    actions = actionable_tasks(tasks)
    normal_ok = not actions or all(
        read_task_status(run_dir, task).get("state") in {"approved", "local_approved", "ci_passed", "done"}
        for task in actions
    )
    external = external_task_records(run_dir)
    external_ok = all(str(record.get("state", "pending")) in APPROVED_STATES for record in external)
    return (bool(actions) or bool(external)) and normal_ok and external_ok


def all_actionable_ci_passed(run_dir: Path, tasks: list[ReviewTask]) -> bool:
    actions = actionable_tasks(tasks)
    normal_ok = not actions or all(read_task_status(run_dir, task).get("state") in {"ci_passed", "done"} for task in actions)
    external = external_task_records(run_dir)
    external_ok = all(str(record.get("state", "pending")) in {"ci_passed", "done"} for record in external)
    return (bool(actions) or bool(external)) and normal_ok and external_ok


def has_revision_requests(run_dir: Path, tasks: list[ReviewTask]) -> bool:
    return any(read_task_status(run_dir, task).get("state") == "needs_revision" for task in actionable_tasks(tasks)) or any(
        str(record.get("state", "")) == "needs_revision" for record in external_task_records(run_dir)
    )


def has_active_work(run_dir: Path, tasks: list[ReviewTask]) -> bool:
    review_active = any(
        read_task_status(run_dir, task).get("state")
        in {"pending", "needs_revision", "fix_failed", "fixed", "validation_failed", "validated", "reviewed"}
        for task in actionable_tasks(tasks)
    )
    if review_active:
        return True
    return any(
        str(record.get("state", "pending"))
        in {"pending", "needs_revision", "fix_failed", "fixed", "validation_failed", "validated", "reviewed"}
        for record in external_task_records(run_dir)
    )


def active_prs_for_push(run_dir: Path, tasks: list[ReviewTask]) -> set[int]:
    prs: set[int] = set()
    for task in actionable_tasks(tasks):
        if read_task_status(run_dir, task).get("state") in {"approved", "local_approved"}:
            prs.add(task.pr_num)
    for record in external_task_records(run_dir):
        if str(record.get("state", "")) in {"approved", "local_approved"}:
            prs.add(int(record.get("pr_num", 0) or 0))
    return {pr for pr in prs if pr}


def active_prs_for_commit(run_dir: Path, tasks: list[ReviewTask]) -> set[int]:
    return active_prs_for_push(run_dir, tasks)


def actionable_tasks_by_pr(tasks: list[ReviewTask]) -> dict[int, list[ReviewTask]]:
    by_pr: dict[int, list[ReviewTask]] = {}
    for task in actionable_tasks(tasks):
        by_pr.setdefault(task.pr_num, []).append(task)
    return by_pr


def external_records_for_pr(run_dir: Path, pr_num: int, include_terminal: bool = False) -> list[dict[str, object]]:
    return [
        record
        for record in external_task_records(run_dir, include_terminal=include_terminal)
        if int(record.get("pr_num", 0) or 0) == pr_num
    ]


def pr_fully_approved(run_dir: Path, tasks: list[ReviewTask], pr_num: int) -> bool:
    pr_tasks = actionable_tasks_by_pr(tasks).get(pr_num, [])
    external = external_records_for_pr(run_dir, pr_num)
    if not pr_tasks and not external:
        return False
    normal_ok = all(
        read_task_status(run_dir, task).get("state") in {"approved", "local_approved", "ci_passed", "done"}
        for task in pr_tasks
    )
    external_ok = all(str(record.get("state", "pending")) in APPROVED_STATES for record in external)
    return normal_ok and external_ok


def task_pr_state(run_dir: Path, task: ReviewTask) -> str:
    return str(read_task_status(run_dir, task).get("state", ""))


def pr_has_state(run_dir: Path, tasks: list[ReviewTask], pr_num: int, states: set[str]) -> bool:
    for task in actionable_tasks_by_pr(tasks).get(pr_num, []):
        if task_pr_state(run_dir, task) in states:
            return True
    for record in external_records_for_pr(run_dir, pr_num, include_terminal=True):
        if str(record.get("state", "")) in states:
            return True
    return False


def pr_state_paths(run_dir: Path, tasks: list[ReviewTask], pr_num: int) -> list[Path]:
    paths: list[Path] = []
    for task in actionable_tasks_by_pr(tasks).get(pr_num, []):
        paths.append(task_status_path(run_dir, task))
    for record in external_records_for_pr(run_dir, pr_num, include_terminal=True):
        paths.append(Path(str(record["status_path"])))
    return paths


def parse_report_comment_urls(report: Path) -> set[str]:
    if not report.exists():
        return set()
    urls: set[str] = set()
    for entry in split_entries(report.read_text(encoding="utf-8")):
        url = field(entry, "评论链接")
        if url:
            urls.add(url)
    return urls


def fetch_fresh_review_urls(run_dir: Path, args: argparse.Namespace) -> tuple[dict[str, object], set[str]]:
    result: dict[str, object] = {
        "state": "skipped",
        "reason": "disabled",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    if not args.require_fresh_before_push:
        return result, set()
    output = run_dir / "fresh_reviews_before_push.md"
    fetch = fetch_report_to(args, run_dir, output)
    (run_dir / "fresh_reviews_before_push.stdout.log").write_text(fetch.stdout, encoding="utf-8")
    (run_dir / "fresh_reviews_before_push.stderr.log").write_text(fetch.stderr, encoding="utf-8")
    if fetch.returncode != 0:
        return {
            "state": "failed",
            "reason": "fresh_fetch_failed",
            "exit_code": fetch.returncode,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }, set()

    return {
        "state": "passed",
        "fresh_report": str(output),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }, parse_report_comment_urls(output)


def freshness_gate(
    run_dir: Path,
    args: argparse.Namespace,
    tasks: list[ReviewTask],
    push_prs: set[int],
    fresh_result: dict[str, object] | None = None,
    fresh_urls: set[str] | None = None,
) -> dict[str, object]:
    if fresh_result is None or fresh_urls is None:
        fresh_result, fresh_urls = fetch_fresh_review_urls(run_dir, args)
    if fresh_result.get("state") not in {"passed", "skipped"}:
        result = dict(fresh_result)
        result["checked_prs"] = sorted(push_prs)
        write_json(run_dir / "freshness_result.json", result)
        return result
    stale: list[dict[str, object]] = []
    blocked_prs: set[int] = set()
    for task in actionable_tasks(tasks):
        if task.pr_num not in push_prs:
            continue
        if not pr_fully_approved(run_dir, tasks, task.pr_num):
            blocked_prs.add(task.pr_num)
            continue
        if task.comment_url and task.comment_url not in fresh_urls:
            stale.append(
                {
                    "task_id": task.task_id,
                    "pr_num": task.pr_num,
                    "comment_url": task.comment_url,
                    "reason": "review_not_in_fresh_unreplied_report",
                }
            )
            blocked_prs.add(task.pr_num)
    if blocked_prs or stale:
        for task in actionable_tasks(tasks):
            if task.pr_num not in blocked_prs:
                continue
            status = read_task_status(run_dir, task)
            if status.get("state") in {"approved", "local_approved"}:
                status["state"] = "needs_human"
                status["freshness"] = {
                    "state": "failed",
                    "reason": "stale_or_pr_not_fully_approved",
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
                write_task_status(run_dir, task, status)
        result = {
            "state": "failed",
            "reason": "stale_or_pr_not_fully_approved",
            "blocked_prs": sorted(blocked_prs),
            "stale_tasks": stale,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        write_json(run_dir / "freshness_result.json", result)
        return result

    result = {
        "state": "passed",
        "fresh_report": str(fresh_result.get("fresh_report", "")),
        "checked_prs": sorted(push_prs),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(run_dir / "freshness_result.json", result)
    return result


def external_records_by_pr(run_dir: Path, states: set[str]) -> dict[int, list[dict[str, object]]]:
    by_pr: dict[int, list[dict[str, object]]] = {}
    for record in external_task_records(run_dir):
        if str(record.get("state", "")) in states:
            pr_num = int(record.get("pr_num", 0) or 0)
            if pr_num:
                by_pr.setdefault(pr_num, []).append(record)
    return by_pr


def target_ci_head_for_pr(run_dir: Path, tasks: list[ReviewTask], pr_num: int, external_records: list[dict[str, object]]) -> str:
    heads: list[str] = []
    for task in actionable_tasks(tasks):
        if task.pr_num != pr_num:
            continue
        status = read_task_status(run_dir, task)
        push_status = status.get("push", {})
        if isinstance(push_status, dict) and push_status.get("new_head"):
            heads.append(str(push_status["new_head"]))
    for record in external_records:
        status = record.get("status", {})
        if isinstance(status, dict):
            push_status = status.get("push", {})
            if isinstance(push_status, dict) and push_status.get("new_head"):
                heads.append(str(push_status["new_head"]))
    unique = sorted(set(heads))
    return unique[-1] if len(unique) == 1 else ""


def execute_commit(run_dir: Path, args: argparse.Namespace, tasks: list[ReviewTask]) -> dict[str, object] | None:
    if args.dry_run or not args.auto_commit:
        return None
    if not args.commit_command:
        raise ValueError("--auto-commit requires --commit-command")
    commit_prs = active_prs_for_commit(run_dir, tasks)
    commit_prs = {pr for pr in commit_prs if pr_fully_approved(run_dir, tasks, pr)}
    commit_prs = {pr for pr in commit_prs if not pr_has_state(run_dir, tasks, pr, {"pushed", "ci_pending", "ci_passed", "done"})}
    if not commit_prs:
        return {"state": "skipped", "reason": "no_fully_approved_prs_to_commit"}

    results: list[dict[str, object]] = []
    ok = True
    for pr_num in sorted(commit_prs):
        log_prefix = run_dir / f"commit-pr-{pr_num}"
        command = render_command(args.commit_command, {"run_dir": run_dir, "pr_num": pr_num})
        result = run_shell(command, run_dir, log_prefix, args.command_timeout)
        state = "completed" if result.returncode == 0 else "failed"
        results.append({"pr_num": pr_num, "state": state, "exit_code": result.returncode, "log_prefix": str(log_prefix)})
        if result.returncode != 0:
            ok = False
            for status_path in pr_state_paths(run_dir, tasks, pr_num):
                status = read_json(status_path, {})  # type: ignore[assignment]
                if isinstance(status, dict) and status.get("state") in {"approved", "local_approved"}:
                    commit_status = status.setdefault("commit", {})
                    if isinstance(commit_status, dict):
                        commit_status["state"] = "failed"
                        commit_status["last_exit_code"] = result.returncode
                        commit_status["last_log_prefix"] = str(log_prefix)
                    write_json(status_path, status)
    output = {"state": "completed" if ok else "failed", "results": results}
    write_json(run_dir / "commit_step_result.json", output)
    return output


def execute_push(run_dir: Path, args: argparse.Namespace, tasks: list[ReviewTask]) -> dict[str, object] | None:
    if args.dry_run or not args.auto_push:
        return None
    if not args.push_command:
        raise ValueError("--auto-push requires --push-command")
    push_prs = active_prs_for_push(run_dir, tasks)
    push_prs = {pr for pr in push_prs if pr_fully_approved(run_dir, tasks, pr)}
    push_prs = {pr for pr in push_prs if not pr_has_state(run_dir, tasks, pr, {"pushed", "ci_pending", "ci_passed", "done"})}
    if not push_prs:
        return {"state": "skipped", "reason": "no_fully_approved_prs_to_push"}

    fresh_result, fresh_urls = fetch_fresh_review_urls(run_dir, args)
    results: list[dict[str, object]] = []
    ok = True
    for pr_num in sorted(push_prs):
        freshness = freshness_gate(run_dir, args, tasks, {pr_num}, fresh_result, fresh_urls)
        if freshness.get("state") not in {"passed", "skipped"}:
            results.append(
                {
                    "pr_num": pr_num,
                    "state": "skipped",
                    "reason": "freshness_gate_failed",
                    "freshness": freshness,
                }
            )
            ok = False
            continue
        log_prefix = run_dir / f"push-pr-{pr_num}"
        command = render_command(args.push_command, {"run_dir": run_dir, "pr_num": pr_num})
        result = run_shell(command, run_dir, log_prefix, args.command_timeout)
        state = "completed" if result.returncode == 0 else "failed"
        results.append({"pr_num": pr_num, "state": state, "exit_code": result.returncode, "log_prefix": str(log_prefix)})
        if result.returncode != 0:
            ok = False
            continue
        for task in actionable_tasks(tasks):
            if task.pr_num != pr_num:
                continue
            status = read_task_status(run_dir, task)
            if status.get("state") not in {"approved", "local_approved"}:
                continue
            push_status = status.setdefault("push", {})
            if isinstance(push_status, dict):
                push_status["state"] = state
                push_status["last_exit_code"] = result.returncode
                push_status["last_log_prefix"] = str(log_prefix)
            status["state"] = "pushed"
            write_task_status(run_dir, task, status)
        for record in external_records_for_pr(run_dir, pr_num, include_terminal=True):
            out_dir = Path(str(record["task_dir"]))
            status = read_json(out_dir / "status.json", {})  # type: ignore[assignment]
            if not isinstance(status, dict) or status.get("state") not in {"approved", "local_approved"}:
                continue
            push_status = status.setdefault("push", {})
            if isinstance(push_status, dict):
                push_status["state"] = state
                push_status["last_exit_code"] = result.returncode
                push_status["last_log_prefix"] = str(log_prefix)
            status["state"] = "pushed"
            status["updated_at"] = datetime.now(timezone.utc).isoformat()
            write_json(out_dir / "status.json", status)
    output = {"state": "completed" if ok else "failed", "results": results}
    write_json(run_dir / "push_result.json", output)
    return output


def gh_json(args: list[str], cwd: Path, log_prefix: Path | None = None) -> tuple[int, object | None, str]:
    result = run_shell(" ".join(shlex.quote(part) for part in ["gh", *args]), cwd, log_prefix or cwd / "gh", 300)
    if result.returncode != 0:
        return result.returncode, None, result.stderr
    try:
        return 0, json.loads(result.stdout), ""
    except json.JSONDecodeError as exc:
        return 1, None, str(exc)


def check_name(row: dict[str, object]) -> str:
    return str(row.get("name") or row.get("context") or "")


def check_status(row: dict[str, object]) -> str:
    return str(row.get("status") or row.get("state") or "").lower()


def check_conclusion(row: dict[str, object]) -> str:
    return str(row.get("conclusion") or "").lower()


def checks_terminal(checks: list[dict[str, object]]) -> bool:
    if not checks:
        return False
    active = {"queued", "in_progress", "pending", "requested", "waiting"}
    return not any(check_status(row) in active for row in checks)


def failed_checks(checks: list[dict[str, object]]) -> list[dict[str, object]]:
    failures = {"failure", "failed", "timed_out", "cancelled", "action_required", "error"}
    return [row for row in checks if check_conclusion(row) in failures or check_status(row) in failures]


def classify_ci_failure(checks: list[dict[str, object]]) -> str:
    names = " ".join(check_name(row).lower() for row in failed_checks(checks))
    if any(token in names for token in ["code-style", "lint", "linter", "black", "ruff", "isort", "pre-commit"]):
        return "style"
    if any(token in names for token in ["python-op", "unit", "pytest", "backend", "test"]):
        return "test"
    if any(token in names for token in ["cla", "permission", "secret", "approval"]):
        return "permission"
    return "unknown"


def parse_actions_job_url(url: object) -> tuple[str, str] | None:
    text = str(url or "")
    match = re.search(r"/actions/runs/(\d+)/job/(\d+)", text)
    if not match:
        return None
    return match.group(1), match.group(2)


def fetch_failed_job_log(repo: str, row: dict[str, object], cwd: Path, log_prefix: Path) -> str:
    details = row.get("detailsUrl") or row.get("targetUrl") or row.get("url")
    parsed = parse_actions_job_url(details)
    if not parsed:
        return ""
    run_id, job_id = parsed
    result = run_shell(
        (
            f"gh run view {shlex.quote(run_id)} "
            f"--repo {shlex.quote(repo)} "
            f"--job {shlex.quote(job_id)} "
            "--log-failed"
        ),
        cwd,
        log_prefix,
        300,
    )
    return (result.stdout or result.stderr)[-8000:]


def ci_fix_dir(run_dir: Path, pr_num: int, head_sha: str, classification: str) -> Path:
    return run_dir / "runs" / f"pr-{pr_num}" / f"ci-fix-{classification}-{head_sha[:9]}"


def write_ci_fix_task(
    run_dir: Path,
    args: argparse.Namespace,
    task: ReviewTask,
    head_sha: str,
    checks: list[dict[str, object]],
    classification: str,
) -> None:
    out_dir = ci_fix_dir(run_dir, task.pr_num, head_sha, classification)
    out_dir.mkdir(parents=True, exist_ok=True)
    failures = failed_checks(checks)
    write_json(
        out_dir / "task.json",
        {
            "task_type": "ci_fix",
            "source_task_id": task.task_id,
            "pr_num": task.pr_num,
            "pr_url": task.pr_url,
            "head_sha": head_sha,
            "classification": classification,
            "failed_checks": failures,
        },
    )
    summary_lines = [
        f"# CI Failure Summary: PR #{task.pr_num}",
        "",
        f"- PR: {task.pr_url}",
        f"- Head SHA: `{head_sha}`",
        f"- Classification: `{classification}`",
        "",
        "## Failed Checks",
        "",
    ]
    for row in failures:
        summary_lines.append(f"- {check_name(row)}: status={check_status(row)} conclusion={check_conclusion(row)}")
        details = row.get("detailsUrl") or row.get("targetUrl") or row.get("url")
        if details:
            summary_lines.append(f"  - URL: {details}")
    summary_lines.extend(["", "## Failed Log Excerpts", ""])
    for index, row in enumerate(failures, start=1):
        log_text = fetch_failed_job_log(
            args.repo,
            row,
            run_dir,
            out_dir / f"failed-check-{index:02d}",
        )
        if not log_text:
            continue
        summary_lines.extend(
            [
                f"### {check_name(row)}",
                "",
                "```text",
                log_text,
                "```",
                "",
            ]
        )
    (out_dir / "ci_failure_summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    (out_dir / "fixer_handoff.md").write_text(
        "\n".join(
            [
                f"# Claude/DeepSeek CI Fix Handoff: PR #{task.pr_num}",
                "",
                "You are the fixer for a CI failure after review fixes were pushed.",
                "Make the smallest change needed to address the failed CI check.",
                "",
                f"- PR: {task.pr_url}",
                f"- Head SHA: `{head_sha}`",
                f"- Failure classification: `{classification}`",
                "",
                "Read `ci_failure_summary.md` in this directory first.",
                "",
                "Hard rules:",
                "",
                "- Do not post GitHub comments.",
                "- Do not force push.",
                "- Do not add Co-authored-by, Generated-by, or AI attribution.",
                "- Write `execution.md` and update `reply_draft.md` if the reviewer-facing explanation changes.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    write_json(
        out_dir / "status.json",
        {
            "task_type": "ci_fix",
            "source_task_id": task.task_id,
            "pr_num": task.pr_num,
            "state": "pending",
            "head_sha": head_sha,
            "classification": classification,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def write_generic_ci_fix_task(
    run_dir: Path,
    args: argparse.Namespace,
    pr_num: int,
    pr_url: str,
    head_sha: str,
    checks: list[dict[str, object]],
    classification: str,
) -> None:
    out_dir = ci_fix_dir(run_dir, pr_num, head_sha, classification)
    out_dir.mkdir(parents=True, exist_ok=True)
    failures = failed_checks(checks)
    write_json(
        out_dir / "task.json",
        {
            "task_type": "ci_fix",
            "source_task_id": "external-ci-watch",
            "pr_num": pr_num,
            "pr_url": pr_url,
            "head_sha": head_sha,
            "classification": classification,
            "failed_checks": failures,
        },
    )
    summary_lines = [
        f"# CI Failure Summary: PR #{pr_num}",
        "",
        f"- PR: {pr_url or 'N/A'}",
        f"- Head SHA: `{head_sha}`",
        f"- Classification: `{classification}`",
        "",
        "## Failed Checks",
        "",
    ]
    for row in failures:
        summary_lines.append(f"- {check_name(row)}: status={check_status(row)} conclusion={check_conclusion(row)}")
        details = row.get("detailsUrl") or row.get("targetUrl") or row.get("url")
        if details:
            summary_lines.append(f"  - URL: {details}")
    summary_lines.extend(["", "## Failed Log Excerpts", ""])
    for index, row in enumerate(failures, start=1):
        log_text = fetch_failed_job_log(args.repo, row, run_dir, out_dir / f"failed-check-{index:02d}")
        if not log_text:
            continue
        summary_lines.extend([f"### {check_name(row)}", "", "```text", log_text, "```", ""])
    (out_dir / "ci_failure_summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    (out_dir / "fixer_handoff.md").write_text(
        "\n".join(
            [
                f"# Claude/DeepSeek CI Fix Handoff: PR #{pr_num}",
                "",
                "You are the fixer for a CI failure after follow-up fixes were pushed.",
                "Make the smallest change needed to address the failed CI check.",
                "",
                f"- PR: {pr_url or 'N/A'}",
                f"- Head SHA: `{head_sha}`",
                f"- Failure classification: `{classification}`",
                "",
                "Read `ci_failure_summary.md` in this directory first.",
                "",
                "Hard rules:",
                "",
                "- Do not post GitHub comments.",
                "- Do not force push.",
                "- Do not add Co-authored-by, Generated-by, or AI attribution.",
                "- Write `execution.md` and update `reply_draft.md` if the reviewer-facing explanation changes.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    write_json(
        out_dir / "status.json",
        {
            "task_type": "ci_fix",
            "source_task_id": "external-ci-watch",
            "pr_num": pr_num,
            "state": "pending",
            "head_sha": head_sha,
            "classification": classification,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def execute_ci_watch(run_dir: Path, args: argparse.Namespace, tasks: list[ReviewTask]) -> list[dict[str, object]]:
    if args.dry_run or not args.wait_ci:
        return []
    results: list[dict[str, object]] = []
    by_pr: dict[int, list[ReviewTask]] = {}
    for task in actionable_tasks(tasks):
        status = read_task_status(run_dir, task)
        if status.get("state") in {"pushed", "ci_pending", "ci_failed"}:
            by_pr.setdefault(task.pr_num, []).append(task)
    external_by_pr = external_records_by_pr(run_dir, {"pushed", "ci_pending", "ci_failed"})
    for pr_num in external_by_pr:
        by_pr.setdefault(pr_num, [])
    deadline = time.monotonic() + max(1, args.ci_timeout)
    for pr_num, pr_tasks in by_pr.items():
        target_head = target_ci_head_for_pr(run_dir, tasks, pr_num, external_by_pr.get(pr_num, []))
        pr_result: dict[str, object] = {"pr_num": pr_num, "state": "ci_pending", "checks": []}
        while True:
            log_prefix = run_dir / "ci" / f"pr-{pr_num}-{int(time.time())}"
            code, data, error = gh_json(
                [
                    "pr",
                    "view",
                    str(pr_num),
                    "--repo",
                    args.repo,
                    "--json",
                    "headRefOid,statusCheckRollup,url",
                ],
                run_dir,
                log_prefix,
            )
            if code != 0 or not isinstance(data, dict):
                pr_result = {"pr_num": pr_num, "state": "needs_human", "error": error}
                break
            checks = data.get("statusCheckRollup") or []
            if not isinstance(checks, list):
                checks = []
            pr_result = {
                "pr_num": pr_num,
                "state": "ci_pending",
                "head_sha": data.get("headRefOid", ""),
                "target_head": target_head,
                "url": data.get("url", ""),
                "checks": checks,
            }
            if target_head and data.get("headRefOid") != target_head:
                pr_result["state"] = "ci_pending"
                pr_result["reason"] = "waiting_for_pushed_head"
                if time.monotonic() >= deadline:
                    pr_result["state"] = "ci_timeout"
                    break
                time.sleep(max(1, args.ci_poll_interval))
                continue
            if checks_terminal(checks):
                failures = failed_checks(checks)
                if failures:
                    classification = classify_ci_failure(checks)
                    pr_result["state"] = "ci_failed"
                    pr_result["classification"] = classification
                    pr_result["failed_checks"] = failures
                    if args.generate_ci_fix_tasks:
                        if pr_tasks:
                            for task in pr_tasks:
                                write_ci_fix_task(run_dir, args, task, str(data.get("headRefOid", "")), checks, classification)
                        elif external_by_pr.get(pr_num):
                            write_generic_ci_fix_task(
                                run_dir,
                                args,
                                pr_num,
                                str(data.get("url", "")),
                                str(data.get("headRefOid", "")),
                                checks,
                                classification,
                            )
                else:
                    pr_result["state"] = "ci_passed"
                break
            if time.monotonic() >= deadline:
                pr_result["state"] = "ci_timeout"
                break
            time.sleep(max(1, args.ci_poll_interval))
        results.append(pr_result)
        for task in pr_tasks:
            status = read_task_status(run_dir, task)
            ci_status = status.setdefault("ci", {})
            if isinstance(ci_status, dict):
                ci_status.update(pr_result)
            if pr_result.get("state") == "ci_passed":
                status["state"] = "ci_passed"
            elif pr_result.get("state") == "ci_failed":
                status["state"] = "ci_failed"
            elif pr_result.get("state") == "ci_timeout":
                status["state"] = "ci_pending"
            else:
                status["state"] = "needs_human"
            write_task_status(run_dir, task, status)
        for record in external_by_pr.get(pr_num, []):
            out_dir = Path(str(record["task_dir"]))
            status = read_json(out_dir / "status.json", {})  # type: ignore[assignment]
            if not isinstance(status, dict):
                continue
            ci_status = status.setdefault("ci", {})
            if isinstance(ci_status, dict):
                ci_status.update(pr_result)
            if pr_result.get("state") == "ci_passed":
                status["state"] = "ci_passed"
            elif pr_result.get("state") == "ci_failed":
                status["state"] = "ci_failed"
            elif pr_result.get("state") == "ci_timeout":
                status["state"] = "ci_pending"
            else:
                status["state"] = "needs_human"
            status["updated_at"] = datetime.now(timezone.utc).isoformat()
            write_json(out_dir / "status.json", status)
    write_json(run_dir / "ci_results.json", results)
    return results


def extract_comment_id(comment_url: str) -> str:
    match = re.search(r"#(?:discussion_r|issuecomment-)?(\d+)$", comment_url or "")
    return match.group(1) if match else ""


def extract_reply_text(reply_path: Path) -> str:
    if not reply_path.exists():
        return ""
    text = reply_path.read_text(encoding="utf-8").strip()
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
        and not line.strip().startswith("#")
        and not line.lower().startswith("status:")
        and "write the final short reply" not in line.lower()
    ]
    return "\n".join(lines).strip()


def execute_replies(run_dir: Path, args: argparse.Namespace, tasks: list[ReviewTask]) -> list[dict[str, object]]:
    if args.dry_run or not args.auto_reply:
        return []

    results: list[dict[str, object]] = []
    for task in actionable_tasks(tasks):
        out_dir = task_dir(run_dir, task)
        status = read_task_status(run_dir, task)
        if args.wait_ci:
            if status.get("state") not in {"ci_passed", "done"}:
                results.append(
                    {
                        "task_id": task.task_id,
                        "state": "skipped",
                        "reason": f"task_state_not_ci_passed:{status.get('state')}",
                    }
                )
                continue
        elif status.get("state") not in {"approved", "local_approved", "ci_passed", "done"}:
            results.append(
                {
                    "task_id": task.task_id,
                    "state": "skipped",
                    "reason": f"task_state_not_approved:{status.get('state')}",
                }
            )
            continue
        comment_id = extract_comment_id(task.comment_url)
        reply_text = extract_reply_text(out_dir / "reply_draft.md")
        log_prefix = out_dir / "github-reply"
        if not comment_id or not reply_text:
            result_row = {
                "task_id": task.task_id,
                "state": "skipped",
                "reason": "missing_comment_id_or_reply_text",
            }
            results.append(result_row)
            continue
        if "discussion_r" in (task.comment_url or ""):
            command = (
                "gh api "
                f"repos/{args.repo}/pulls/{task.pr_num}/comments/{comment_id}/replies "
                "-X POST "
                f"-f body={shlex.quote(reply_text)}"
            )
        else:
            command = (
                "gh api "
                f"repos/{args.repo}/issues/{task.pr_num}/comments "
                "-X POST "
                f"-f body={shlex.quote(reply_text)}"
            )
        result = run_shell(command, out_dir, log_prefix, args.command_timeout)
        state = "completed" if result.returncode == 0 else "failed"
        reply_status = status.setdefault("reply", {})
        if isinstance(reply_status, dict):
            reply_status["state"] = state
            reply_status["last_exit_code"] = result.returncode
            reply_status["last_log_prefix"] = str(log_prefix)
        write_task_status(run_dir, task, status)
        results.append(
            {
                "task_id": task.task_id,
                "state": state,
                "exit_code": result.returncode,
                "log_prefix": str(log_prefix),
            }
        )
    write_json(run_dir / "reply_results.json", results)
    return results


def run_execution_loop(run_dir: Path, tasks: list[ReviewTask], args: argparse.Namespace) -> None:
    if args.dry_run or not (
        args.execute_fixers
        or args.execute_audit
        or args.execute_claude_review
        or args.execute_local_validation
        or args.auto_commit
        or args.wait_ci
        or args.auto_push
        or args.auto_reply
    ):
        return
    refresh_external_shards(run_dir, args)
    if not has_active_work(run_dir, tasks):
        execute_commit(run_dir, args, tasks)
        execute_push(run_dir, args, tasks)
        execute_ci_watch(run_dir, args, tasks)
        execute_replies(run_dir, args, tasks)
        return

    loop_events: list[dict[str, object]] = read_json(run_dir / "loop_events.json", [])  # type: ignore[assignment]
    for round_number in range(1, args.max_fix_rounds + 1):
        refresh_review_shards(run_dir, tasks, args)
        refresh_external_shards(run_dir, args)
        round_event: dict[str, object] = {"round": round_number}
        if args.execute_fixers:
            round_event["fixers"] = execute_fixers(run_dir, args, round_number)
        if args.execute_local_validation:
            round_event["validations"] = execute_local_validation(run_dir, tasks, args, round_number)
            round_event["external_validations"] = execute_external_local_validation(run_dir, args, round_number)
        if args.execute_claude_review:
            round_event["claude_reviews"] = execute_claude_reviews(run_dir, tasks, args, round_number)
            round_event["external_claude_reviews"] = execute_external_claude_reviews(run_dir, args, round_number)
        if args.execute_audit:
            round_event["audits"] = execute_audits(run_dir, tasks, args, round_number)
            round_event["external_audits"] = execute_external_audits(run_dir, args, round_number)
        if args.auto_commit:
            round_event["commit"] = execute_commit(run_dir, args, tasks)
        if args.auto_push:
            round_event["push"] = execute_push(run_dir, args, tasks)
        if args.wait_ci:
            round_event["ci"] = execute_ci_watch(run_dir, args, tasks)
        if args.auto_reply:
            round_event["replies"] = execute_replies(run_dir, args, tasks)
        if (
            not round_event.get("fixers")
            and not round_event.get("validations")
            and not round_event.get("external_validations")
            and not round_event.get("claude_reviews")
            and not round_event.get("external_claude_reviews")
            and not round_event.get("audits")
            and not round_event.get("external_audits")
            and not round_event.get("commit")
            and not round_event.get("push")
            and not round_event.get("ci")
            and not round_event.get("replies")
        ):
            break
        loop_events.append(round_event)
        write_json(run_dir / "loop_events.json", loop_events)
        if all_actionable_approved(run_dir, tasks):
            break
        if not has_active_work(run_dir, tasks):
            break

    execute_commit(run_dir, args, tasks)
    execute_push(run_dir, args, tasks)
    execute_ci_watch(run_dir, args, tasks)
    execute_replies(run_dir, args, tasks)


def safe_copytree(src: Path, dst: Path, ignore_names: set[str]) -> None:
    if not src.exists():
        return
    def ignore(_dir: str, names: list[str]) -> set[str]:
        ignored = {name for name in names if name in ignore_names}
        ignored.update({name for name in names if name.endswith(".pyc")})
        return ignored
    shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)


def make_package(args: argparse.Namespace, run_dir: Path) -> None:
    package = run_dir / "package"
    package.mkdir(parents=True, exist_ok=True)
    for name in ["README.md", "config.yaml"]:
        shutil.copy2(ROOT / name, package / name)
    shutil.copytree(ROOT / "prompts", package / "prompts", dirs_exist_ok=True)
    safe_copytree(
        Path(args.github_reviews_dir),
        package / "github_reviews",
        {".git", "__pycache__", "results"},
    )
    safe_copytree(
        Path(args.deepseek_workflow_dir),
        package / "deepseek-workflow",
        {".git", "__pycache__", "tmp", "tasks"},
    )
    safe_copytree(
        ROOT,
        package / "pr_review_loop",
        {".git", "__pycache__", "records", "github_reviews", "deepseek-workflow"},
    )


def read_text_or(path: Path, default: str) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else default


def refresh_final_reports(run_dir: Path, tasks: list[ReviewTask]) -> None:
    for task in tasks:
        out_dir = task_dir(run_dir, task)
        if not (out_dir / "task.json").exists():
            continue
        status = read_task_status(run_dir, task)
        audit_json = out_dir / "codex_audit.json"
        audit_text = read_text_or(out_dir / "codex_audit.md", "Pending.")
        if audit_json.exists():
            audit_text = "```json\n" + audit_json.read_text(encoding="utf-8").strip() + "\n```"
        body = (
            render_task_markdown(task)
            + "\n## Current Status\n\n"
            + "```json\n"
            + json.dumps(status, ensure_ascii=False, indent=2)
            + "\n```\n\n"
            + "## Execution\n\n"
            + read_text_or(out_dir / "execution.md", "Pending.").strip()
            + "\n\n## Codex Audit\n\n"
            + audit_text.strip()
            + "\n\n## Review Line Reply Draft\n\n"
            + read_text_or(out_dir / "reply_draft.md", "Pending.").strip()
            + "\n"
        )
        (out_dir / "final_report.md").write_text(body, encoding="utf-8")


def refresh_audit_prompts(run_dir: Path, tasks: list[ReviewTask]) -> None:
    for task in tasks:
        out_dir = task_dir(run_dir, task)
        if out_dir.exists():
            (out_dir / "codex_audit_prompt.md").write_text(render_audit_prompt(task, run_dir), encoding="utf-8")


def write_summary(run_dir: Path, tasks: list[ReviewTask], shards: list[list[ReviewTask]], args: argparse.Namespace) -> None:
    counts: dict[str, int] = {}
    state_counts: dict[str, int] = {}
    for task in tasks:
        counts[task.decision] = counts.get(task.decision, 0) + 1
        state = str(read_task_status(run_dir, task).get("state", "unknown"))
        state_counts[state] = state_counts.get(state, 0) + 1
    lines = [
        "# PR Review Loop Run Summary",
        "",
        f"- Run dir: `{run_dir}`",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Dry run: {args.dry_run}",
        f"- Execute fixers: {args.execute_fixers}",
        f"- Execute Claude review: {args.execute_claude_review}",
        f"- Execute audit: {args.execute_audit}",
        f"- Auto commit: {args.auto_commit}",
        f"- Auto push: {args.auto_push}",
        f"- Auto reply: {args.auto_reply}",
        f"- Total parsed tasks: {len(tasks)}",
        f"- Shards prepared: {len(shards)}",
        f"- External shards prepared: {len(list((run_dir / 'runs' / 'shards').glob('shard-ext-*')))}",
        "",
        "## Triage Counts",
        "",
    ]
    for key in sorted(counts):
        lines.append(f"- `{key}`: {counts[key]}")
    lines.extend(["", "## State Counts", ""])
    for key in sorted(state_counts):
        lines.append(f"- `{key}`: {state_counts[key]}")
    lines.extend(["", "## Tasks", ""])
    for task in tasks:
        rel = task_dir(run_dir, task).relative_to(run_dir)
        status = read_task_status(run_dir, task)
        state = status.get("state", "unknown")
        audit = status.get("audit", {})
        audit_decision = audit.get("decision", "") if isinstance(audit, dict) else ""
        lines.append(
            f"- PR #{task.pr_num} `{task.decision}` state `{state}` audit `{audit_decision or 'N/A'}` @{task.reviewer} "
            f"`{task.path or 'top-level'}`: [{task.task_id}]({rel}/task.md)"
        )
    external = discover_external_fix_tasks(run_dir)
    external_all = sorted((run_dir / "runs").glob("pr-*/ci-fix-*")) + sorted(
        (run_dir / "runs").glob("pr-*/rebase-conflict-*")
    )
    if external_all:
        lines.extend(["", "## External Fix Tasks", ""])
        for out_dir in external_all:
            status = read_json(out_dir / "status.json", {})  # type: ignore[assignment]
            state = status.get("state", "unknown") if isinstance(status, dict) else "unknown"
            task_type = status.get("task_type", out_dir.name) if isinstance(status, dict) else out_dir.name
            rel = out_dir.relative_to(run_dir)
            active = " active" if any(str(item.get("task_dir")) == str(out_dir) for item in external) else ""
            lines.append(f"- `{task_type}` state `{state}`{active}: [{out_dir.name}]({rel}/fixer_handoff.md)")
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    run_dir = Path(args.resume) if args.resume else Path(args.records_root) / utc_stamp()
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        if args.resume:
            tasks = load_tasks(run_dir)
            shards = []
            for shard in shard_dirs(run_dir):
                rows = [row for row in load_shard_tasks(shard) if not row.get("external")]
                if rows:
                    shards.append([ReviewTask(**row) for row in rows])
        else:
            if args.fetch:
                report = fetch_report(args, run_dir)
            elif args.report:
                report = Path(args.report)
            else:
                report = latest_report(Path(args.github_reviews_dir))

            if not report.exists():
                raise FileNotFoundError(f"Report not found: {report}")

            source_report = run_dir / "source_reviews.md"
            if report.resolve() != source_report.resolve():
                shutil.copy2(report, source_report)
            tasks = parse_report(report, args.limit, args.shard_scope, args.limit_prs)
            for task in tasks:
                write_task_files(run_dir, task)

            shards = group_shards(tasks, args.max_reviews_per_fixer, args.shard_scope)
            write_shards(run_dir, shards)
            write_jsonl(run_dir / "tasks.jsonl", (asdict(task) for task in tasks))
            refresh_audit_prompts(run_dir, tasks)
        write_json(
            run_dir / "run_config.json",
            {
                "args": vars(args),
                "source_report": str(run_dir / "source_reviews.md"),
                "fixer_parallelism": args.fixer_parallelism,
                "execute_claude_review": args.execute_claude_review,
                "auto_commit": args.auto_commit,
                "auto_push": args.auto_push,
                "auto_reply": args.auto_reply,
            },
        )
        if not args.resume and not args.no_package_copy:
            make_package(args, run_dir)
        if args.resume:
            refresh_audit_prompts(run_dir, tasks)
        run_execution_loop(run_dir, tasks, args)
        refresh_final_reports(run_dir, tasks)
        write_summary(run_dir, tasks, shards, args)
    except Exception as exc:
        (run_dir / "error.log").write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        print(f"ERROR: {exc}", file=sys.stderr)
        print(f"Run dir: {run_dir}", file=sys.stderr)
        return 1

    print(run_dir)
    print(f"Parsed tasks: {len(tasks)}")
    print(f"Prepared shards: {len(shards)}")
    print(f"Summary: {run_dir / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
