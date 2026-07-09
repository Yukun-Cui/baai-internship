#!/usr/bin/env python3
"""Test fixer used by the PR review loop smoke tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: stub_fixer.py RUN_DIR SHARD_DIR", file=sys.stderr)
        return 2

    run_dir = Path(sys.argv[1])
    shard_dir = Path(sys.argv[2])
    tasks = json.loads((shard_dir / "shard.json").read_text(encoding="utf-8"))
    for task in tasks:
        if task.get("external") and task.get("task_dir"):
            task_dir = Path(task["task_dir"])
        else:
            pr_dir = run_dir / "runs" / f"pr-{task['pr_num']}"
            matches = [
                path.parent
                for path in pr_dir.glob("*/task.json")
                if json.loads(path.read_text(encoding="utf-8")).get("task_id") == task["task_id"]
            ]
            task_dir = matches[0] if matches else pr_dir / task["task_id"]
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "execution.md").write_text(
            "# Execution\n\n"
            f"Addressed `{task['task_id']}` in the smoke-test fixer.\n\n"
            "Validation: stub fixer completed.\n",
            encoding="utf-8",
        )
        (task_dir / "reply_draft.md").write_text(
            "Addressed this by applying the requested focused update. "
            "Validated with the local smoke test.\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
