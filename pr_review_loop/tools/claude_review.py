#!/usr/bin/env python3
"""Run an independent Claude review gate for one task."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
import subprocess
from pathlib import Path


SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["approved", "needs_revision", "needs_human", "skip"]},
        "summary": {"type": "string"},
        "findings": {"type": "array"},
        "required_changes": {"type": "array"},
        "reply_to_reviewer": {"type": "string"},
    },
    "required": ["decision", "summary", "findings", "required_changes", "reply_to_reviewer"],
    "additionalProperties": True,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Claude review gate.")
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--cwd", default="/root/FlagGems")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument(
        "--allow-read-tools",
        action="store_true",
        help="Allow Claude read-only tools. Default is no tools because this wrapper preloads review context.",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Optional Claude model alias/name for the reviewer agent.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def run(
    cmd: list[str],
    cwd: Path,
    *,
    input_text: str | None = None,
    timeout: int = 900,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, input=input_text, text=True, capture_output=True, timeout=timeout)


def read(path: Path, default: str = "") -> str:
    return path.read_text(encoding="utf-8") if path.exists() else default


def git_output(worktree: Path, args: list[str], timeout: int = 120) -> str:
    result = run(["git", *args], worktree, timeout=timeout)
    return result.stdout if result.returncode == 0 else result.stderr


def extract_json(text: str) -> dict[str, object]:
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("No JSON object found")


def normalize_decision(value: object) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if raw in {"approved", "approve", "pass", "passed", "ok"}:
        return "approved"
    if raw in {"skip", "skipped", "ignore", "no_action"}:
        return "skip"
    if raw in {"needs_revision", "changes_requested", "request_changes", "failed", "fail"}:
        return "needs_revision"
    if raw in {"needs_human", "manual", "blocked", "unknown"}:
        return "needs_human"
    return "needs_human"


def build_prompt(task_dir: Path, worktree: Path) -> str:
    return "\n\n".join(
        [
            "You are an independent review gate. You did not make the fix. Do not modify files, commit, push, or comment.",
            "Your job is to catch bad automation before expensive final review.",
            "Return only JSON matching this schema:",
            json.dumps(SCHEMA, indent=2),
            "Review policy:",
            "- Approve only if the work directly addresses the review and has no unrelated diff.",
            "- If the original comment is only a positive checklist with no requested change, return skip.",
            "- If the comment is a question or asks to confirm something, do not require code changes; return skip or approved with an English reply.",
            "- Replies must be English.",
            "- Commit-message-only tasks must not leave source/test/config diffs.",
            "- Reject if any commit message in the PR range still contains Co-Authored-By, Generated-by, Claude, model, or AI attribution.",
            "- Reject duplicated or non-English reply drafts.",
            "Task JSON:",
            read(task_dir / "task.json"),
            "Fixer handoff:",
            read(task_dir / "fixer_handoff.md", "missing"),
            "Execution log:",
            read(task_dir / "execution.md", "missing"),
            "Reply draft:",
            read(task_dir / "reply_draft.md", "missing"),
            "Local validation:",
            read(task_dir / "local_validation.md", "missing"),
            "Previous Codex audit:",
            read(task_dir / "codex_audit.json", "missing"),
            "Git status:",
            git_output(worktree, ["status", "--short"]),
            "Git diff:",
            git_output(worktree, ["diff", "--stat"]) + "\n\n" + git_output(worktree, ["diff"]),
            "Recent commit messages:",
            git_output(worktree, ["log", "--pretty=format:%h%n%B%n---END---", "-20"]),
        ]
    )


def fallback_checks(task_dir: Path, worktree: Path) -> dict[str, object] | None:
    reply = read(task_dir / "reply_draft.md")
    if re.search(r"[\u4e00-\u9fff]", reply):
        return {
            "decision": "needs_revision",
            "summary": "Reply draft contains non-English text.",
            "findings": [{"severity": "blocking", "message": "Reply draft must be English."}],
            "required_changes": ["Rewrite reply_draft.md in English."],
            "reply_to_reviewer": "",
        }
    log_text = git_output(worktree, ["log", "--pretty=%B", "-30"])
    if re.search(r"co-authored|generated-by|claude|anthropic|ai attribution", log_text, flags=re.I):
        return {
            "decision": "needs_revision",
            "summary": "Forbidden attribution text appears in recent commit history.",
            "findings": [{"severity": "blocking", "message": "PR commit history contains forbidden attribution text."}],
            "required_changes": ["Rewrite the PR commit history so no Co-Authored-By, Generated-by, Claude, Anthropic, or AI attribution remains."],
            "reply_to_reviewer": "",
        }
    return None


def main() -> int:
    args = parse_args()
    task_dir = Path(args.task_dir).resolve()
    worktree = Path(args.worktree).resolve()
    fallback = fallback_checks(task_dir, worktree)
    if fallback:
        output = fallback
        (task_dir / "claude_review.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
        return 0
    if args.dry_run:
        output = {
            "decision": "needs_human",
            "summary": "Dry run: Claude review was not executed.",
            "findings": [],
            "required_changes": [],
            "reply_to_reviewer": "",
        }
        (task_dir / "claude_review.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
        return 0

    prompt = build_prompt(task_dir, worktree)
    (task_dir / "claude_review_input.md").write_text(prompt, encoding="utf-8")
    last_message = task_dir / "claude_review.last_message.txt"
    cmd = [
        "claude",
        "-p",
        "--bare",
        "--no-session-persistence",
        "--disable-slash-commands",
        "--permission-mode",
        "plan",
        "--json-schema",
        json.dumps(SCHEMA),
    ]
    if args.model:
        cmd.extend(["--model", args.model])
    if args.allow_read_tools:
        cmd.extend(
            [
                "--tools",
                "Read,Grep,Glob,Bash",
                "--disallowedTools",
                "Edit,Write,MultiEdit,NotebookEdit,WebFetch,WebSearch,Bash(git commit*),Bash(git push*),Bash(gh pr comment*),Bash(gh api*)",
            ]
        )
    else:
        cmd.extend(["--tools", ""])
    try:
        result = run(cmd, Path(args.cwd).resolve(), input_text=prompt, timeout=args.timeout)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        (task_dir / "claude_review.stdout.log").write_text(stdout, encoding="utf-8")
        (task_dir / "claude_review.stderr.log").write_text(stderr, encoding="utf-8")
        output = {
            "decision": "needs_human",
            "summary": f"Claude review timed out after {args.timeout} seconds.",
            "findings": [{"severity": "blocking", "message": "Claude review timeout"}],
            "required_changes": ["Inspect review logs before proceeding."],
            "reply_to_reviewer": "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        (task_dir / "claude_review.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
        return 124
    (task_dir / "claude_review.stdout.log").write_text(result.stdout, encoding="utf-8")
    (task_dir / "claude_review.stderr.log").write_text(result.stderr, encoding="utf-8")
    last_message.write_text(result.stdout or result.stderr, encoding="utf-8")
    try:
        output = extract_json(result.stdout or result.stderr)
    except Exception as exc:
        output = {
            "decision": "needs_human",
            "summary": f"Claude review output was not parseable JSON: {type(exc).__name__}: {exc}",
            "findings": [{"severity": "blocking", "message": "Review output parse failure"}],
            "required_changes": ["Inspect claude_review.stdout.log and claude_review.stderr.log."],
            "reply_to_reviewer": "",
        }
    output["decision"] = normalize_decision(output.get("decision"))
    (task_dir / "claude_review.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    return 0 if result.returncode == 0 else result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
