#!/usr/bin/env python3
"""Prepare PR worktrees for review-loop fixer runs."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare PR worktrees.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--repo-dir", default="/root/FlagGems")
    parser.add_argument("--repo", default="flagos-ai/FlagGems")
    parser.add_argument("--remote", default="fork")
    parser.add_argument("--upstream-remote", default="upstream")
    parser.add_argument("--upstream-branch", default="master")
    parser.add_argument("--worktree-root", default="/root/pr_worktrees")
    parser.add_argument("--rebase", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--force-reset", action=argparse.BooleanOptionalAction, default=False)
    return parser.parse_args()


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sanitize_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-")
    return slug[:80] or "item"


def load_prs(run_dir: Path) -> list[int]:
    prs: set[int] = set()
    with (run_dir / "tasks.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                prs.add(int(json.loads(line)["pr_num"]))
    return sorted(prs)


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
            "headRefName,headRefOid,headRepositoryOwner,headRepository,url,state",
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)
    return json.loads(result.stdout)


def ensure_clean(worktree: Path) -> None:
    result = run(["git", "status", "--porcelain"], worktree)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    if result.stdout.strip():
        raise RuntimeError(f"worktree has uncommitted changes: {worktree}")


def worktree_exists(repo_dir: Path, worktree: Path) -> bool:
    result = run(["git", "worktree", "list", "--porcelain"], repo_dir)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return str(worktree) in result.stdout


def git_text(worktree: Path, args: list[str]) -> str:
    result = run(["git", *args], worktree)
    return result.stdout if result.returncode == 0 else result.stderr


def conflicted_files(worktree: Path) -> list[str]:
    result = run(["git", "diff", "--name-only", "--diff-filter=U"], worktree)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def conflict_excerpt(path: Path, limit: int = 12000) -> str:
    if not path.exists() or not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    markers = ["<<<<<<<", "=======", ">>>>>>>"]
    if not any(marker in text for marker in markers):
        return text[:limit]
    lines = text.splitlines()
    chunks: list[str] = []
    for index, line in enumerate(lines):
        if line.startswith("<<<<<<<"):
            start = max(0, index - 5)
            end = min(len(lines), index + 80)
            chunks.extend(lines[start:end])
            chunks.append("")
    return "\n".join(chunks)[:limit]


def write_rebase_conflict_handoff(
    run_dir: Path,
    pr_num: int,
    worktree: Path,
    branch: str,
    remote_ref: str,
    upstream_ref: str,
    rebase_result: subprocess.CompletedProcess[str],
) -> Path:
    out_dir = run_dir / "runs" / f"pr-{pr_num}" / f"rebase-conflict-{sanitize_slug(branch)}"
    out_dir.mkdir(parents=True, exist_ok=True)
    conflicts = conflicted_files(worktree)
    status_text = git_text(worktree, ["status", "--short"])
    conflict_data = []
    for name in conflicts:
        conflict_data.append(
            {
                "path": name,
                "excerpt": conflict_excerpt(worktree / name),
            }
        )
    data = {
        "task_type": "rebase_conflict_fix",
        "pr_num": pr_num,
        "worktree": str(worktree),
        "branch": branch,
        "remote_ref": remote_ref,
        "upstream_ref": upstream_ref,
        "status": status_text,
        "conflicted_files": conflicts,
        "rebase_stdout": rebase_result.stdout,
        "rebase_stderr": rebase_result.stderr,
    }
    write_json(out_dir / "task.json", data)
    write_json(
        out_dir / "status.json",
        {
            "task_type": "rebase_conflict_fix",
            "pr_num": pr_num,
            "state": "pending",
            "worktree": str(worktree),
            "branch": branch,
            "upstream_ref": upstream_ref,
        },
    )

    lines = [
        f"# Rebase Conflict Summary: PR #{pr_num}",
        "",
        f"- Worktree: `{worktree}`",
        f"- PR branch: `{branch}`",
        f"- Remote ref: `{remote_ref}`",
        f"- Upstream ref: `{upstream_ref}`",
        "",
        "## Rebase Output",
        "",
        "```text",
        (rebase_result.stdout + "\n" + rebase_result.stderr).strip(),
        "```",
        "",
        "## Git Status During Conflict",
        "",
        "```text",
        status_text.strip(),
        "```",
        "",
        "## Conflicted Files",
        "",
    ]
    if conflicts:
        lines.extend(f"- `{name}`" for name in conflicts)
    else:
        lines.append("- none detected by `git diff --name-only --diff-filter=U`")
    for row in conflict_data:
        lines.extend(
            [
                "",
                f"### `{row['path']}`",
                "",
                "```text",
                row["excerpt"],
                "```",
            ]
        )
    (out_dir / "rebase_conflict_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "fixer_handoff.md").write_text(
        "\n".join(
            [
                f"# Claude/DeepSeek Rebase Conflict Handoff: PR #{pr_num}",
                "",
                "You are the fixer for a rebase conflict. Resolve the conflict with the smallest change.",
                "",
                f"- Worktree: `{worktree}`",
                f"- PR branch: `{branch}`",
                f"- Upstream ref: `{upstream_ref}`",
                "",
                "Read `rebase_conflict_summary.md` first.",
                "",
                "Required work:",
                "",
                "1. Reproduce or inspect the conflict context in the worktree.",
                "2. Resolve only the conflicted files.",
                "3. Run the relevant local validation.",
                "4. Write `execution.md` with the conflict resolution rationale and validation.",
                "5. Do not push or post GitHub comments.",
                "",
                "Hard rules:",
                "",
                "- Do not force push.",
                "- Do not add Co-authored-by, Generated-by, or AI attribution.",
                "- Keep unrelated files untouched.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return out_dir


def prepare_one(args: argparse.Namespace, pr_num: int) -> dict[str, object]:
    repo_dir = Path(args.repo_dir).resolve()
    run_dir = Path(args.run_dir).resolve()
    worktree = Path(args.worktree_root).resolve() / f"pr{pr_num}"
    info = gh_pr_info(args.repo, pr_num)
    branch = str(info["headRefName"])
    remote_ref = f"{args.remote}/{branch}"

    fetch = run(["git", "fetch", args.remote, branch], repo_dir)
    if fetch.returncode != 0:
        raise RuntimeError(fetch.stderr or fetch.stdout)

    worktree.parent.mkdir(parents=True, exist_ok=True)
    if worktree.exists() or worktree_exists(repo_dir, worktree):
        if args.force_reset:
            reset = run(["git", "reset", "--hard", remote_ref], worktree)
            if reset.returncode != 0:
                raise RuntimeError(reset.stderr or reset.stdout)
            clean = run(["git", "clean", "-fd"], worktree)
            if clean.returncode != 0:
                raise RuntimeError(clean.stderr or clean.stdout)
        else:
            ensure_clean(worktree)
            checkout = run(["git", "checkout", "--detach", remote_ref], worktree)
            if checkout.returncode != 0:
                raise RuntimeError(checkout.stderr or checkout.stdout)
    else:
        add = run(["git", "worktree", "add", "--detach", str(worktree), remote_ref], repo_dir)
        if add.returncode != 0:
            raise RuntimeError(add.stderr or add.stdout)

    rebased = False
    if args.rebase:
        fetch_upstream = run(["git", "fetch", args.upstream_remote, args.upstream_branch], worktree)
        if fetch_upstream.returncode != 0:
            raise RuntimeError(fetch_upstream.stderr or fetch_upstream.stdout)
        rebase = run(["git", "rebase", f"{args.upstream_remote}/{args.upstream_branch}"], worktree)
        if rebase.returncode != 0:
            conflict_dir = write_rebase_conflict_handoff(
                run_dir,
                pr_num,
                worktree,
                branch,
                remote_ref,
                f"{args.upstream_remote}/{args.upstream_branch}",
                rebase,
            )
            run(["git", "rebase", "--abort"], worktree)
            return {
                "pr_num": pr_num,
                "state": "rebase_conflict",
                "worktree": str(worktree),
                "branch": branch,
                "remote_ref": remote_ref,
                "upstream_ref": f"{args.upstream_remote}/{args.upstream_branch}",
                "handoff_dir": str(conflict_dir),
                "error": (rebase.stderr or rebase.stdout)[-4000:],
            }
        rebased = True

    head = run(["git", "rev-parse", "HEAD"], worktree)
    if head.returncode != 0:
        raise RuntimeError(head.stderr)
    return {
        "pr_num": pr_num,
        "state": "prepared",
        "worktree": str(worktree),
        "branch": branch,
        "remote_ref": remote_ref,
        "head": head.stdout.strip(),
        "remote_head": info.get("headRefOid", ""),
        "rebased": rebased,
    }


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir).resolve()
    results = []
    ok = True
    for pr_num in load_prs(run_dir):
        try:
            row = prepare_one(args, pr_num)
        except Exception as exc:
            ok = False
            row = {
                "pr_num": pr_num,
                "state": "failed",
                "error": f"{type(exc).__name__}: {exc}",
            }
        if row.get("state") != "prepared":
            ok = False
        results.append(row)
    write_json(run_dir / "worktrees.json", results)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
