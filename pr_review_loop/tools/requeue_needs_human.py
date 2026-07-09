#!/usr/bin/env python3
"""Requeue selected needs_human tasks for another fixer pass."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Requeue needs_human tasks.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--pr", type=int, action="append", default=[])
    parser.add_argument(
        "--all",
        action="store_true",
        help="Requeue all needs_human tasks except obvious positive-only review summaries.",
    )
    parser.add_argument(
        "--skip-positive-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Leave positive-only automated review summaries as skipped.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def is_positive_only(task: dict[str, object]) -> bool:
    body = str(task.get("body", "")).lower()
    positive = ["代码审查结果", "通过的检查", "✅", "无冲突", "ci 工作流状态"]
    negative = ["需要修改", "建议修改", "待修复", "未通过", "不通过", "失败", "报错", "failed", "fix", "please"]
    return any(token in body for token in positive) and not any(token in body for token in negative)


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir).resolve()
    allowed_prs = set(args.pr)
    changed: list[dict[str, object]] = []
    for task_path in sorted((run_dir / "runs").glob("pr-*/*/task.json")):
        task = load_json(task_path)
        pr_num = int(task.get("pr_num", 0) or 0)
        if allowed_prs and pr_num not in allowed_prs:
            continue
        status_path = task_path.parent / "status.json"
        if not status_path.exists():
            continue
        status = load_json(status_path)
        if status.get("state") != "needs_human":
            continue
        if args.skip_positive_only and is_positive_only(task):
            status["state"] = "skipped"
            status["requeue_reason"] = "positive_only_review_summary"
            write_json(status_path, status)
            changed.append({"task_id": task.get("task_id"), "pr_num": pr_num, "state": "skipped"})
            continue
        if not args.all and not allowed_prs:
            continue
        status["state"] = "needs_revision"
        status["requeue_reason"] = "manual_requeue_for_additional_fixer_round"
        write_json(status_path, status)
        changed.append({"task_id": task.get("task_id"), "pr_num": pr_num, "state": "needs_revision"})
    print(json.dumps(changed, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
