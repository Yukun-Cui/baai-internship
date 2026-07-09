#!/usr/bin/env python3
"""Test Claude-review gate used by PR review loop smoke tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: stub_claude_review.py TASK_DIR", file=sys.stderr)
        return 2

    task_dir = Path(sys.argv[1])
    task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    task_id = task.get("task_id") or task_dir.name
    reply_path = task_dir / "reply_draft.md"
    reply = reply_path.read_text(encoding="utf-8").strip() if reply_path.exists() else ""
    output = {
        "decision": "approved",
        "summary": f"Smoke Claude review approved {task_id}.",
        "findings": [],
        "required_changes": [],
        "reply_to_reviewer": reply,
    }
    (task_dir / "claude_review.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
