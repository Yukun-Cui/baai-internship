#!/usr/bin/env python3
"""Run Claude Code as a fixer with a prompt passed through stdin.

This avoids CLI parsing pitfalls where options such as --add-dir consume a
following prompt argument.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Claude fixer wrapper.")
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--handoff", required=True)
    parser.add_argument("--task-dir", required=True)
    parser.add_argument(
        "--cwd",
        default="",
        help="Directory where Claude is launched. Defaults to --worktree.",
    )
    parser.add_argument("--bare", action="store_true", help="Use Claude Code bare mode.")
    parser.add_argument(
        "--no-add-dir",
        action="store_true",
        help="Do not pass --add-dir. Useful when provider gateways fail in multi-directory tool mode.",
    )
    parser.add_argument("--timeout", type=int, default=600)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    worktree = Path(args.worktree).resolve()
    handoff = Path(args.handoff).resolve()
    task_dir = Path(args.task_dir).resolve()
    cwd = Path(args.cwd).resolve() if args.cwd else worktree
    prompt = (
        handoff.read_text(encoding="utf-8")
        + "\n\n"
        + "Execute this handoff in the worktree below.\n"
        + f"Worktree: {worktree}\n"
        + f"Task dir for execution.md and reply_draft.md: {task_dir}\n"
        + "Use absolute paths when reading or editing files outside the current directory.\n"
        + "Make the smallest code change only. Do not commit, push, or post comments.\n"
    )
    cmd = ["claude", "-p"]
    if args.bare:
        cmd.append("--bare")
    cmd.extend(["--permission-mode", "acceptEdits"])
    if not args.no_add_dir:
        cmd.extend(["--add-dir", str(worktree), "--add-dir", str(task_dir)])
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=args.timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        (task_dir / "claude_fixer.stdout.log").write_text(stdout, encoding="utf-8")
        (task_dir / "claude_fixer.stderr.log").write_text(stderr, encoding="utf-8")
        message = (stderr or stdout or f"Claude fixer timed out after {args.timeout} seconds.")[-4000:]
        (task_dir / "execution.md").write_text(
            "# Execution\n\n"
            "Status: fixer_timeout\n\n"
            f"Time: {datetime.now(timezone.utc).isoformat()}\n\n"
            f"Timeout: {args.timeout} seconds\n\n"
            "Claude fixer output tail:\n\n"
            "```text\n"
            f"{message}\n"
            "```\n",
            encoding="utf-8",
        )
        print(message, file=sys.stderr)
        return 124
    (task_dir / "claude_fixer.stdout.log").write_text(result.stdout, encoding="utf-8")
    (task_dir / "claude_fixer.stderr.log").write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "Claude fixer failed without output.")[-4000:]
        execution = task_dir / "execution.md"
        execution.write_text(
            "# Execution\n\n"
            "Status: fixer_failed\n\n"
            f"Time: {datetime.now(timezone.utc).isoformat()}\n\n"
            f"Command exit code: {result.returncode}\n\n"
            "Claude fixer output tail:\n\n"
            "```text\n"
            f"{message}\n"
            "```\n",
            encoding="utf-8",
        )
        print(message, file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
