#!/usr/bin/env python3
"""Run Codex as the audit gate for one review-loop task."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["approved", "needs_revision", "needs_human"]},
        "summary": {"type": "string"},
        "findings": {"type": "array"},
        "required_changes": {"type": "array"},
        "reply_to_reviewer": {"type": "string"},
    },
    "required": ["decision", "summary", "findings", "required_changes", "reply_to_reviewer"],
    "additionalProperties": True,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Codex audit wrapper.")
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--model", default="")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def run(cmd: list[str], cwd: Path, *, input_text: str | None = None, timeout: int = 900) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, input=input_text, text=True, capture_output=True, timeout=timeout)


def read(path: Path, default: str = "") -> str:
    return path.read_text(encoding="utf-8") if path.exists() else default


def git_output(worktree: Path, args: list[str]) -> str:
    result = run(["git", *args], worktree, timeout=120)
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
    raise ValueError("No JSON object found in Codex output")


def normalize_decision(value: object) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if raw in {"approved", "approve", "pass", "passed", "ok"}:
        return "approved"
    if raw in {"needs_revision", "changes_requested", "request_changes", "failed", "fail"}:
        return "needs_revision"
    if raw in {"needs_human", "manual", "blocked", "unknown"}:
        return "needs_human"
    return "needs_human"


def build_prompt(task_dir: Path, worktree: Path) -> str:
    return "\n\n".join(
        [
            "You are the audit gate. Do not modify files. Do not commit, push, or comment on GitHub.",
            "Review whether the fixer work fully addresses the review task and passes validation.",
            "Return only JSON matching this schema:",
            json.dumps(SCHEMA, indent=2),
            "Original audit prompt:",
            read(task_dir / "codex_audit_prompt.md"),
            "Task JSON:",
            read(task_dir / "task.json"),
            "Execution log:",
            read(task_dir / "execution.md", "missing"),
            "Reply draft:",
            read(task_dir / "reply_draft.md", "missing"),
            "Local validation:",
            read(task_dir / "local_validation.md", "missing"),
            "Git status:",
            git_output(worktree, ["status", "--short"]),
            "Git diff:",
            git_output(worktree, ["diff", "--stat"]) + "\n\n" + git_output(worktree, ["diff"]),
            "Commit diff if worktree is clean:",
            git_output(worktree, ["show", "--stat", "--oneline", "--no-renames", "HEAD"]),
        ]
    )


def main() -> int:
    args = parse_args()
    task_dir = Path(args.task_dir).resolve()
    worktree = Path(args.worktree).resolve()
    prompt = build_prompt(task_dir, worktree)
    (task_dir / "codex_audit_input.md").write_text(prompt, encoding="utf-8")
    if args.dry_run:
        output = {
            "decision": "needs_human",
            "summary": "Dry run: Codex audit was not executed.",
            "findings": [],
            "required_changes": [],
            "reply_to_reviewer": read(task_dir / "reply_draft.md").strip(),
        }
        (task_dir / "codex_audit.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
        return 0

    last_message = task_dir / "codex_audit.last_message.txt"
    cmd = [
        "codex",
        "exec",
        "--cd",
        str(worktree),
        "--sandbox",
        "read-only",
        "--dangerously-bypass-approvals-and-sandbox",
        "--output-last-message",
        str(last_message),
    ]
    if args.model:
        cmd.extend(["--model", args.model])
    cmd.append("-")
    result = run(cmd, worktree, input_text=prompt, timeout=args.timeout)
    (task_dir / "codex_audit.stdout.log").write_text(result.stdout, encoding="utf-8")
    (task_dir / "codex_audit.stderr.log").write_text(result.stderr, encoding="utf-8")
    output_text = read(last_message, result.stdout or result.stderr)
    try:
        output = extract_json(output_text)
    except Exception as exc:
        output = {
            "decision": "needs_human",
            "summary": f"Codex audit output was not parseable JSON: {type(exc).__name__}: {exc}",
            "findings": [{"severity": "blocking", "message": "Audit output parse failure"}],
            "required_changes": ["Inspect codex_audit.stdout.log and codex_audit.stderr.log."],
            "reply_to_reviewer": "",
        }
    output["decision"] = normalize_decision(output.get("decision"))
    (task_dir / "codex_audit.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    return 0 if result.returncode == 0 else result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
