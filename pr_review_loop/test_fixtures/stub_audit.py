#!/usr/bin/env python3
"""Test audit used by the PR review loop smoke tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: stub_audit.py TASK_DIR", file=sys.stderr)
        return 2

    task_dir = Path(sys.argv[1])
    task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    task_id = task.get("task_id") or task_dir.name
    reply_path = task_dir / "reply_draft.md"
    output = {
        "decision": "approved",
        "summary": f"Smoke audit approved {task_id}.",
        "findings": [],
        "required_changes": [],
        "reply_to_reviewer": reply_path.read_text(encoding="utf-8").strip() if reply_path.exists() else "",
    }
    (task_dir / "codex_audit.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
