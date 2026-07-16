#!/usr/bin/env python3
"""Push locally approved PR worktrees to their GitHub PR head branches."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Push approved PR worktrees.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--repo", default="flagos-ai/FlagGems-Experimental")
    parser.add_argument("--remote", default="fork")
    parser.add_argument("--worktree-root", default="/root/pr_worktrees")
    parser.add_argument("--worktree-template", default="")
    parser.add_argument("--pr", type=int, action="append", default=[], help="Only consider this PR number. Repeatable.")
    parser.add_argument(
        "--force-with-lease",
        action="store_true",
        help="Allow non-fast-forward pushes using --force-with-lease against the current PR head.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def task_status_path(run_dir: Path, task: dict[str, object]) -> Path:
    task_id = str(task["task_id"])
    pr_num = int(task["pr_num"])
    pr_dir = run_dir / "runs" / f"pr-{pr_num}"
    for candidate in pr_dir.glob("*/task.json"):
        data = load_json(candidate)
        if isinstance(data, dict) and data.get("task_id") == task_id:
            return candidate.parent / "status.json"
    raise FileNotFoundError(f"status not found for {task_id}")


def load_tasks(run_dir: Path) -> list[dict[str, object]]:
    tasks = []
    with (run_dir / "tasks.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                tasks.append(json.loads(line))
    return tasks


def external_status_paths(run_dir: Path) -> list[Path]:
    paths: list[Path] = []
    runs_root = run_dir / "runs"
    for pattern in ["pr-*/ci-fix-*/status.json", "pr-*/rebase-conflict-*/status.json"]:
        paths.extend(sorted(runs_root.glob(pattern)))
    return paths


def worktree_for(args: argparse.Namespace, pr_num: int) -> Path:
    if args.worktree_template:
        return Path(args.worktree_template.format(pr_num=pr_num))
    return Path(args.worktree_root) / f"pr{pr_num}"


def gh_pr_info(repo: str, pr_num: int) -> dict[str, object]:
    result = run(
        [
            "gh",
            "pr",
            "view",
            str(pr_num),
            "--repo",
            repo,
            "--json",
            "headRefName,headRepositoryOwner,headRepository,headRefOid,url,state",
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)
    return json.loads(result.stdout)


def ensure_fast_forward_base(worktree: Path, remote: str, branch: str, old_head: str) -> bool:
    exists = run(["git", "cat-file", "-e", f"{old_head}^{{commit}}"], worktree)
    if exists.returncode != 0:
        fetch = run(["git", "fetch", remote, branch], worktree)
        if fetch.returncode != 0:
            raise RuntimeError(fetch.stderr or fetch.stdout)
    ancestor = run(["git", "merge-base", "--is-ancestor", old_head, "HEAD"], worktree)
    return ancestor.returncode == 0


def push_one(args: argparse.Namespace, pr_num: int) -> dict[str, object]:
    worktree = worktree_for(args, pr_num)
    if not worktree.exists():
        raise FileNotFoundError(f"missing worktree for PR #{pr_num}: {worktree}")
    info = gh_pr_info(args.repo, pr_num)
    branch = str(info["headRefName"])
    old_head = str(info["headRefOid"])
    local_head = run(["git", "rev-parse", "HEAD"], worktree)
    if local_head.returncode != 0:
        raise RuntimeError(local_head.stderr)
    new_head = local_head.stdout.strip()
    status = run(["git", "status", "--porcelain"], worktree)
    if status.returncode != 0:
        raise RuntimeError(status.stderr)
    if status.stdout.strip():
        raise RuntimeError(f"worktree has uncommitted changes: {worktree}")
    is_fast_forward = ensure_fast_forward_base(worktree, args.remote, branch, old_head)
    if not is_fast_forward and not args.force_with_lease:
        raise RuntimeError(
            f"local HEAD is not a descendant of PR head {old_head}; "
            f"refusing to push {worktree} to {branch}. "
            "Pass --force-with-lease for an intentional rebase push."
        )
    if args.dry_run:
        return {
            "pr_num": pr_num,
            "state": "dry_run",
            "worktree": str(worktree),
            "branch": branch,
            "old_head": old_head,
            "new_head": new_head,
            "fast_forward": is_fast_forward,
            "force_with_lease": args.force_with_lease,
        }
    cmd = ["git", "push", args.remote, f"HEAD:refs/heads/{branch}"]
    if not is_fast_forward:
        cmd = [
            "git",
            "push",
            f"--force-with-lease=refs/heads/{branch}:{old_head}",
            args.remote,
            f"HEAD:refs/heads/{branch}",
        ]
    result = run(cmd, worktree)
    return {
        "pr_num": pr_num,
        "state": "completed" if result.returncode == 0 else "failed",
        "exit_code": result.returncode,
        "worktree": str(worktree),
        "branch": branch,
        "old_head": old_head,
        "new_head": new_head,
        "fast_forward": is_fast_forward,
        "force_with_lease": not is_fast_forward,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir).resolve()
    tasks = load_tasks(run_dir)
    prs: set[int] = set()
    status_paths: dict[int, list[Path]] = {}
    tasks_by_pr: dict[int, list[dict[str, object]]] = {}
    for task in tasks:
        if task.get("decision") not in {"must_fix", "should_reply"}:
            continue
        tasks_by_pr.setdefault(int(task["pr_num"]), []).append(task)
    for pr_num, pr_tasks in tasks_by_pr.items():
        paths: list[Path] = []
        all_approved = True
        for task in pr_tasks:
            status_path = task_status_path(run_dir, task)
            paths.append(status_path)
            status = load_json(status_path)
            if not isinstance(status, dict) or status.get("state") not in {"approved", "local_approved"}:
                all_approved = False
        if all_approved and paths:
            prs.add(pr_num)
            status_paths.setdefault(pr_num, []).extend(paths)
    for status_path in external_status_paths(run_dir):
        status = load_json(status_path)
        if not isinstance(status, dict):
            continue
        if status.get("state") not in {"approved", "local_approved"}:
            continue
        pr_num = int(status.get("pr_num", 0) or 0)
        if not pr_num:
            continue
        prs.add(pr_num)
        status_paths.setdefault(pr_num, []).append(status_path)
    if args.pr:
        allowed = set(args.pr)
        prs = {pr_num for pr_num in prs if pr_num in allowed}
        status_paths = {pr_num: paths for pr_num, paths in status_paths.items() if pr_num in allowed}

    results = []
    ok = True
    for pr_num in sorted(prs):
        try:
            row = push_one(args, pr_num)
        except Exception as exc:
            row = {
                "pr_num": pr_num,
                "state": "failed",
                "exit_code": 1,
                "error": f"{type(exc).__name__}: {exc}",
            }
        results.append(row)
        if row["state"] != "completed" and row["state"] != "dry_run":
            ok = False
        for status_path in status_paths.get(pr_num, []):
            status = load_json(status_path)
            if not isinstance(status, dict):
                continue
            push_status = status.setdefault("push", {})
            if isinstance(push_status, dict):
                push_status["state"] = row["state"]
                push_status["last_exit_code"] = row.get("exit_code")
                push_status["remote"] = args.remote
                if "branch" in row:
                    push_status["branch"] = row["branch"]
                if "old_head" in row:
                    push_status["old_head"] = row["old_head"]
                if "new_head" in row:
                    push_status["new_head"] = row["new_head"]
                if "error" in row:
                    push_status["error"] = row["error"]
                elif "error" in push_status:
                    push_status.pop("error", None)
            if row["state"] == "completed":
                status["state"] = "pushed"
            write_json(status_path, status)

    write_json(run_dir / "push_result.json", results)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
