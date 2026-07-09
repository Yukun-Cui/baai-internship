#!/usr/bin/env python3
"""Claude-review smoke stub that rejects once, then approves."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: stub_claude_review_retry.py TASK_DIR", file=sys.stderr)
        return 2

    task_dir = Path(sys.argv[1])
    marker = task_dir / ".stub_claude_review_seen"
    if not marker.exists():
        marker.write_text("seen\n", encoding="utf-8")
        output = {
            "decision": "needs_revision",
            "summary": "Smoke Claude review requested one more fixer pass.",
            "findings": [{"severity": "blocking", "message": "Retry fixture requested a revision."}],
            "required_changes": ["Apply the retry fixture feedback in the next fixer pass."],
            "reply_to_reviewer": "",
        }
    else:
        reply_path = task_dir / "reply_draft.md"
        output = {
            "decision": "approved",
            "summary": "Smoke Claude review approved after retry.",
            "findings": [],
            "required_changes": [],
            "reply_to_reviewer": reply_path.read_text(encoding="utf-8").strip() if reply_path.exists() else "",
        }
    (task_dir / "claude_review.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
