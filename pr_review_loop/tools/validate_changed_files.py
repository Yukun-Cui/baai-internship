#!/usr/bin/env python3
"""Validate changed files for one PR review task.

This is intentionally conservative and project-agnostic enough for FlagGems:
it runs formatting/static checks on changed Python files and selects likely
pytest targets from changed tests or touched operator files.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate changed files.")
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--base-ref", default="")
    parser.add_argument(
        "--include-committed-diff",
        action="store_true",
        help="Also validate base-ref..HEAD when there are no working tree changes.",
    )
    parser.add_argument("--pytest", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--format", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def run(cmd: list[str], cwd: Path) -> dict[str, object]:
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    return {
        "cmd": cmd,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def changed_files(worktree: Path, base_ref: str, include_committed_diff: bool) -> list[str]:
    staged = run(["git", "diff", "--name-only", "--cached"], worktree)
    unstaged = run(["git", "diff", "--name-only"], worktree)
    names: list[str] = []
    for result in [staged, unstaged]:
        if result["exit_code"] == 0:
            names.extend(str(result["stdout"]).splitlines())
    if names:
        return sorted(set(name for name in names if name))

    if not include_committed_diff or not base_ref:
        return []

    diff = run(["git", "diff", "--name-only", f"{base_ref}..HEAD"], worktree)
    if diff["exit_code"] == 0:
        names.extend(str(diff["stdout"]).splitlines())
    return sorted(set(name for name in names if name))


def py_files(files: list[str], worktree: Path) -> list[str]:
    return [name for name in files if name.endswith(".py") and (worktree / name).exists()]


def pytest_targets(files: list[str], worktree: Path) -> list[str]:
    targets: set[str] = set()
    for name in files:
        path = Path(name)
        if name.startswith("tests/") and name.endswith(".py") and (worktree / name).exists():
            targets.add(name)
        if name.startswith("src/flag_gems/ops/") and name.endswith(".py"):
            op_name = path.stem
            test_path = Path("tests") / f"test_{op_name}.py"
            if (worktree / test_path).exists():
                targets.add(str(test_path))
    return sorted(targets)


def write_report(task_dir: Path, results: list[dict[str, object]], files: list[str], targets: list[str]) -> None:
    task_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "changed_files": files,
        "pytest_targets": targets,
        "results": [
            {
                "cmd": row["cmd"],
                "exit_code": row["exit_code"],
            }
            for row in results
        ],
    }
    (task_dir / "local_validation.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")

    lines = ["# Local Validation", "", "## Changed Files", ""]
    lines.extend(f"- `{name}`" for name in files)
    lines.extend(["", "## Pytest Targets", ""])
    if targets:
        lines.extend(f"- `{name}`" for name in targets)
    else:
        lines.append("- none selected")
    lines.extend(["", "## Commands", ""])
    for row in results:
        cmd = " ".join(str(part) for part in row["cmd"])
        lines.extend(
            [
                f"### `{cmd}`",
                "",
                f"Exit code: `{row['exit_code']}`",
                "",
                "stdout:",
                "",
                "```text",
                str(row["stdout"])[-4000:],
                "```",
                "",
                "stderr:",
                "",
                "```text",
                str(row["stderr"])[-4000:],
                "```",
                "",
            ]
        )
    (task_dir / "local_validation.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    worktree = Path(args.worktree).resolve()
    task_dir = Path(args.task_dir).resolve()
    files = changed_files(worktree, args.base_ref, args.include_committed_diff)
    python_files = py_files(files, worktree)
    targets = pytest_targets(files, worktree)

    results: list[dict[str, object]] = []
    results.append(run(["git", "diff", "--check"], worktree))
    if python_files and args.format:
        results.append(run([sys.executable, "-m", "black", "--check", *python_files], worktree))
        results.append(run([sys.executable, "-m", "ruff", "check", *python_files], worktree))
        results.append(run([sys.executable, "-m", "isort", "--check-only", *python_files], worktree))
    if python_files:
        results.append(run([sys.executable, "-m", "py_compile", *python_files], worktree))
    if targets and args.pytest:
        results.append(run([sys.executable, "-m", "pytest", "-q", *targets, "--tb=short"], worktree))

    write_report(task_dir, results, files, targets)
    return 0 if all(row["exit_code"] == 0 for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
