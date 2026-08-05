#!/usr/bin/env python3
"""Parallel Claude-agent FlagGems PR submitter.

This is the agent-based companion to ``batch_submit.sh``.  It creates one
isolated git worktree per operator, then starts one Claude Code non-interactive
agent in each worktree.  The agent prompt requires the official
flaggems-pr-submit skill flow and the final PR must be created by
``submit_operator.py``.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import queue
import re
import selectors
import shutil
import signal
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


PR_URL_RE = re.compile(r"https://github\.com/flagos-ai/FlagGems-Experimental/pull/\d+")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
LOCAL_NO_PROXY_HOSTS = ("localhost", "127.0.0.1", "::1")
MANUAL_PR_RE = re.compile(r"\bgh\s+pr\s+(?:create|edit|merge|ready|reopen|close)\b")

shutdown_event = threading.Event()


@dataclass
class Result:
    operator: str
    status: str
    gpu: int | None
    worktree: str | None
    branch: str | None
    log_file: str
    start_time: str
    end_time: str
    duration_seconds: int
    pr_url: str | None = None
    conversation_file: str | None = None
    conversation_stream_file: str | None = None
    summary_log_file: str | None = None
    error_summary: str | None = None


@dataclass
class GpuStats:
    index: int
    memory_used_mb: int
    memory_free_mb: int
    memory_total_mb: int
    utilization: int


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_cmd(
    cmd: list[str],
    cwd: Path,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def extend_no_proxy(env: dict[str, str], hosts: tuple[str, ...] = LOCAL_NO_PROXY_HOSTS) -> None:
    existing: list[str] = []
    for key in ("NO_PROXY", "no_proxy"):
        existing.extend(part.strip() for part in env.get(key, "").split(",") if part.strip())
    merged: list[str] = []
    for host in [*existing, *hosts]:
        if host not in merged:
            merged.append(host)
    value = ",".join(merged)
    env["NO_PROXY"] = value
    env["no_proxy"] = value


def query_gpu_stats() -> dict[int, GpuStats]:
    """Return GPU stats from nvidia-smi, keyed by physical GPU index."""
    if shutil.which("nvidia-smi") is None:
        return {}
    result = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,memory.used,memory.free,memory.total,utilization.gpu",
            "--format=csv,noheader,nounits",
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return {}

    stats: dict[int, GpuStats] = {}
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 5:
            continue
        try:
            index, used, free, total, util = [int(part) for part in parts]
        except ValueError:
            continue
        stats[index] = GpuStats(
            index=index,
            memory_used_mb=used,
            memory_free_mb=free,
            memory_total_mb=total,
            utilization=util,
        )
    return stats


def discover_gpu_ids() -> list[int]:
    return sorted(query_gpu_stats())


def parse_gpu_ids(raw: str) -> list[int]:
    value = raw.strip().lower()
    if value in {"auto", "all"}:
        gpu_ids = discover_gpu_ids()
        if not gpu_ids:
            raise RuntimeError("No GPUs discovered by nvidia-smi; pass --gpus 0,1,... explicitly to bypass auto discovery")
        return gpu_ids
    gpu_ids = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not gpu_ids:
        raise RuntimeError("No GPU IDs provided")
    return gpu_ids


class GpuPool:
    """Reserve GPUs within this batch run and across cooperating processes."""

    def __init__(
        self,
        gpu_ids: list[int],
        *,
        auto_check: bool,
        min_free_mb: int,
        max_utilization: int,
        poll_interval: float,
        lock_dir: Path,
    ) -> None:
        self.gpu_ids = gpu_ids
        self.auto_check = auto_check
        self.min_free_mb = min_free_mb
        self.max_utilization = max_utilization
        self.poll_interval = poll_interval
        self.lock_dir = lock_dir
        self.in_use: set[int] = set()
        self.lock_files = {}
        self.lock = threading.Lock()
        self.queue: queue.Queue[int] = queue.Queue()
        if not auto_check:
            for gpu_id in gpu_ids:
                self.queue.put(gpu_id)

    def _try_process_lock(self, gpu_id: int):
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.lock_dir / f"gpu_{gpu_id}.lock"
        lock_file = lock_path.open("w")
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock_file.close()
            return None
        lock_file.write(f"pid={os.getpid()} gpu={gpu_id} time={utc_now()}\n")
        lock_file.flush()
        return lock_file

    def acquire(self, op_name: str) -> int | None:
        if not self.auto_check:
            while not shutdown_event.is_set():
                try:
                    gpu_id = self.queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                lock_file = self._try_process_lock(gpu_id)
                if lock_file is not None:
                    with self.lock:
                        self.in_use.add(gpu_id)
                        self.lock_files[gpu_id] = lock_file
                    print(f"[GPU] {op_name} acquired GPU {gpu_id} (locked)")
                    return gpu_id
                self.queue.put(gpu_id)
                print(f"[WAIT] {op_name} waiting for GPU {gpu_id} lock")
                time.sleep(self.poll_interval)
            return None

        while not shutdown_event.is_set():
            stats = query_gpu_stats()
            if not stats:
                raise RuntimeError("GPU auto-check is enabled, but nvidia-smi did not return GPU stats")

            candidates: list[GpuStats] = []
            for gpu_id in self.gpu_ids:
                item = stats.get(gpu_id)
                if not item:
                    continue
                if item.memory_free_mb >= self.min_free_mb and item.utilization <= self.max_utilization:
                    candidates.append(item)
            candidates.sort(key=lambda item: (item.utilization, -item.memory_free_mb, item.index))

            with self.lock:
                for item in candidates:
                    if item.index not in self.in_use:
                        lock_file = self._try_process_lock(item.index)
                        if lock_file is None:
                            continue
                        self.in_use.add(item.index)
                        self.lock_files[item.index] = lock_file
                        print(
                            f"[GPU] {op_name} acquired GPU {item.index} "
                            f"(free={item.memory_free_mb}MiB, util={item.utilization}%, locked)"
                        )
                        return item.index

            print(
                f"[WAIT] {op_name} waiting for free GPU "
                f"(need free>={self.min_free_mb}MiB util<={self.max_utilization}%; "
                f"candidates={','.join(map(str, self.gpu_ids))})"
            )
            time.sleep(self.poll_interval)
        return None

    def release(self, gpu_id: int | None) -> None:
        if gpu_id is None:
            return
        if self.auto_check:
            with self.lock:
                self.in_use.discard(gpu_id)
                lock_file = self.lock_files.pop(gpu_id, None)
            if lock_file is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
            return
        with self.lock:
            self.in_use.discard(gpu_id)
            lock_file = self.lock_files.pop(gpu_id, None)
        if lock_file is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
        self.queue.put(gpu_id)


def run_streaming_cmd(
    cmd: list[str],
    cwd: Path,
    timeout: int,
    env: dict[str, str],
    log_file: Path,
    conversation_stream_file: Path,
    *,
    op_name: str,
    worktree_dir: Path,
    branch: str | None,
    gpu_id: int,
    prompt: str,
    start_time: str,
) -> tuple[int, str, str]:
    """Run Claude and stream stdout/stderr to log + JSONL in real time."""
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    deadline = time.monotonic() + timeout

    with log_file.open("w") as log, conversation_stream_file.open("w") as stream:
        meta = {
            "type": "meta",
            "operator": op_name,
            "worktree": str(worktree_dir),
            "branch": branch,
            "gpu": gpu_id,
            "cwd": str(cwd),
            "start_time": start_time,
            "command": cmd[:-1] + ["<prompt>"],
            "prompt": prompt,
        }
        stream.write(json.dumps(meta, ensure_ascii=False) + "\n")
        stream.flush()

        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
        )

        sel = selectors.DefaultSelector()
        assert proc.stdout is not None
        assert proc.stderr is not None
        sel.register(proc.stdout, selectors.EVENT_READ, "stdout")
        sel.register(proc.stderr, selectors.EVENT_READ, "stderr")

        try:
            while sel.get_map():
                if time.monotonic() > deadline:
                    proc.kill()
                    raise subprocess.TimeoutExpired(cmd, timeout)

                for key, _ in sel.select(timeout=1.0):
                    line = key.fileobj.readline()
                    stream_name = key.data
                    if line == "":
                        sel.unregister(key.fileobj)
                        continue

                    if stream_name == "stdout":
                        stdout_chunks.append(line)
                    else:
                        stderr_chunks.append(line)

                    log.write(line)
                    log.flush()

                    event_record = {
                        "type": "stream",
                        "time": utc_now(),
                        "stream": stream_name,
                        "raw": line.rstrip("\n"),
                    }
                    try:
                        parsed = json.loads(line)
                    except json.JSONDecodeError:
                        parsed = None
                    if isinstance(parsed, dict):
                        event_record["event"] = parsed
                    stream.write(json.dumps(event_record, ensure_ascii=False) + "\n")
                    stream.flush()

            returncode = proc.wait(timeout=5)
        finally:
            sel.close()

        end_record = {
            "type": "result",
            "time": utc_now(),
            "returncode": returncode,
            "stdout_bytes": sum(len(chunk.encode()) for chunk in stdout_chunks),
            "stderr_bytes": sum(len(chunk.encode()) for chunk in stderr_chunks),
        }
        stream.write(json.dumps(end_record, ensure_ascii=False) + "\n")
        stream.flush()

    return returncode, "".join(stdout_chunks), "".join(stderr_chunks)


def load_ops(path: Path) -> list[str]:
    ops: list[str] = []
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            ops.append(line)
    return ops


def load_status(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_status(path: Path, status: dict[str, dict], lock: threading.Lock) -> None:
    with lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n")


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.+-]+", "_", name)


def branch_name(prefix: str, op_name: str) -> str:
    cleaned = safe_name(op_name).strip("._-") or "operator"
    return f"{prefix.rstrip('/')}/{cleaned}"


def require_path(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def git_fetch_upstream(repo_dir: Path, retries: int, remote: str, base: str) -> None:
    last = ""
    for attempt in range(1, retries + 1):
        result = run_cmd(["git", "fetch", remote, base, "--quiet"], repo_dir)
        if result.returncode == 0:
            return
        last = (result.stderr or result.stdout).strip()
        print(f"[WARN] git fetch {remote} {base} failed ({attempt}/{retries}); retrying...")
        time.sleep(attempt * 5)
    raise RuntimeError(f"git fetch {remote} {base} failed: {last}")


def create_worktree(
    repo_dir: Path,
    worktree_base: Path,
    op_name: str,
    branch_prefix: str,
    git_lock_path: Path,
    upstream_ref: str,
) -> tuple[Path, str]:
    worktree_base.mkdir(parents=True, exist_ok=True)
    pid = os.getpid()
    suffix = f"{pid}-{int(time.time())}"
    worktree_dir = worktree_base / f"agent_{safe_name(op_name)}_{suffix}"
    branch = branch_name(branch_prefix, f"{op_name}-{suffix}")

    with git_lock_path.open("w") as lock_file:
        if os.name != "nt":
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            run_cmd(["git", "worktree", "remove", "--force", str(worktree_dir)], repo_dir)
            run_cmd(["git", "branch", "-D", branch], repo_dir)
            result = run_cmd(
                ["git", "worktree", "add", "-b", branch, str(worktree_dir), upstream_ref],
                repo_dir,
            )
            if result.returncode != 0:
                raise RuntimeError((result.stderr or result.stdout).strip())
        finally:
            if os.name != "nt":
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    source_worktrees = repo_dir / ".worktrees"
    if source_worktrees.exists():
        link_path = worktree_dir / ".worktrees"
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()
        link_path.symlink_to(source_worktrees)

    return worktree_dir, branch


def cleanup_worktree(repo_dir: Path, worktree_dir: Path, branch: str, git_lock_path: Path) -> None:
    with git_lock_path.open("w") as lock_file:
        if os.name != "nt":
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            run_cmd(["git", "worktree", "remove", "--force", str(worktree_dir)], repo_dir)
            run_cmd(["git", "branch", "-D", branch], repo_dir)
        finally:
            if os.name != "nt":
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def build_prompt(
    op_name: str,
    gpu_id: int,
    worktree_dir: Path,
    skill_dir: Path,
    scripts_dir: Path,
    dry_run: bool,
    timeout_min: int,
    base: str,
) -> str:
    submit_cmd = (
        f'CUDA_VISIBLE_DEVICES={gpu_id} python "{scripts_dir / "submit_operator.py"}" '
        f'"{op_name}" --repo-dir "{worktree_dir}" --gpu "{gpu_id}" --base "{base}" --token "$GH_TOKEN"'
    )
    if dry_run:
        submit_cmd += " --dry-run"

    return f"""
You are a Claude Code agent working on exactly one FlagGems operator PR.

Operator: {op_name}
Worktree repo: {worktree_dir}
GPU: {gpu_id}
Skill: {skill_dir / "SKILL.md"}
Skill scripts: {scripts_dir}
Timeout budget for this outer job: {timeout_min} minutes.

Hard requirements:
- First read and follow the skill at {skill_dir / "SKILL.md"}.
- The skill's Environment table may contain historical defaults. For this run, the authoritative repo is the worktree repo above, and the authoritative token is the GH_TOKEN environment variable passed to this process. Do not use any hardcoded token or repo path from the skill text.
- Work only inside this worktree repo: {worktree_dir}.
- Submit or validate exactly one operator: {op_name}.
- Do not modify /root/baai-internship/batch_pr_submit or the source repo except through normal git worktree metadata.
- Do not cherry-pick, rebase, force push, or use destructive git reset/checkout commands.
- Do not manually create the PR or manually write the PR body. Final PR creation must go through submit_operator.py.
- Do not run gh pr create/edit/merge/ready/reopen/close yourself. Those are policy violations in this batch runner.
- Do not use skip flags for tests or benchmarks.
- If generated code fails extraction or strict checks, repair the code in the worktree while preserving the skill rules.
- If the operator is structurally impossible to submit as a standalone PR, stop and report BLOCKED with the concrete reason.
- If submitting this operator would require deleting or renaming files that already exist on upstream/{base}, or modifying existing upstream tests/benchmarks, report BLOCKED instead of restructuring the repo.
- Kernel headers must contain only the FlagOS Contributors Apache license block followed immediately by the KernelGen line; remove any extra personal or institution copyright lines if extraction brings them in.

Required flow:
1. cd "{worktree_dir}"
2. Run:
   python "{scripts_dir / "operator_registry.py"}" lookup "{op_name}"
3. Run extraction, using explicit source/impl/canonical args only if needed by the skill naming rules:
   python "{scripts_dir / "extract_from_worktree.py"}" "{op_name}" --repo-dir "{worktree_dir}"
4. Repair any extraction, naming, dtype, mark, benchmark, yaml, formatting, or strict-check failures.
5. Before final submission, run:
   python "{scripts_dir / "check_operator.py"}" "{op_name}" --repo-dir "{worktree_dir}" --strict
   pre-commit run --files <all changed files>
6. Final command must be:
   {submit_cmd}

Dry-run mode: {"ON - do not push or create a PR; submit_operator.py --dry-run is required." if dry_run else "OFF - create the PR if all gates pass."}

Final response format:
- Status: SUCCESS | BLOCKED | FAILED
- PR URL: <url or none>
- Branch: <current branch>
- Changed files: <short list>
- Validation: <commands run and pass/fail>
- Benchmark: <summary or reason unavailable>
- Blocker: <only if blocked/failed>
""".strip()


def parse_agent_output(output: str, dry_run: bool) -> tuple[str, str | None, str | None]:
    clean = ANSI_RE.sub("", output)
    result_texts: list[str] = []
    assistant_texts: list[str] = []
    manual_pr_commands: list[str] = []
    for line in clean.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if isinstance(event.get("result"), str):
            result_texts.append(event["result"])
        message = event.get("message")
        if isinstance(message, dict):
            for item in message.get("content", []):
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text")
                    if isinstance(text, str):
                        assistant_texts.append(text)
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    tool_input = item.get("input")
                    if isinstance(tool_input, dict):
                        command = tool_input.get("command")
                        if isinstance(command, str) and MANUAL_PR_RE.search(command):
                            manual_pr_commands.append(command)
        for denial in event.get("permission_denials", []) if isinstance(event.get("permission_denials"), list) else []:
            if isinstance(denial, dict):
                tool_input = denial.get("tool_input")
                command = tool_input.get("command") if isinstance(tool_input, dict) else None
                if isinstance(command, str) and MANUAL_PR_RE.search(command):
                    manual_pr_commands.append(command)

    if manual_pr_commands:
        matches = sorted(set(match for command in manual_pr_commands for match in MANUAL_PR_RE.findall(command)))
        return (
            "failed",
            None,
            "Policy violation: agent ran manual GitHub PR command(s) "
            f"{', '.join(matches)}. PR creation/editing must go through submit_operator.py.",
        )

    final_text = result_texts[-1] if result_texts else "\n".join(assistant_texts[-3:]) or clean

    def error_tail() -> str:
        lowered = final_text.lower()
        if "failed to authenticate" in lowered and "err_access_denied" in lowered:
            return "Failed to authenticate: API 403 ERR_ACCESS_DENIED while calling model endpoint; check proxy/no_proxy/base URL."
        if "failed to authenticate" in lowered:
            first_line = final_text.strip().splitlines()[0] if final_text.strip() else "Failed to authenticate"
            return first_line[:500]
        return final_text[-1200:].strip()

    pr_urls = PR_URL_RE.findall(final_text)
    status_matches = re.findall(
        r"(?im)^\s*-?\s*(?:\*\*)?status(?:\*\*)?\s*:\s*(success|blocked|failed)\b",
        final_text,
    )
    if status_matches:
        status = status_matches[-1].lower()
        pr_url = pr_urls[-1] if status == "success" and pr_urls else None
        error = None if status == "success" else error_tail()
        return status, pr_url, error

    lower = final_text.lower()
    if dry_run and (
        "status: success" in lower
        or "dry-run" in lower
        and ("check_operator" in lower or "pre-commit" in lower)
        and ("pass" in lower or "通过" in final_text)
    ):
        return "success", None, None

    if "status: blocked" in lower:
        return "blocked", None, error_tail()

    if pr_urls:
        return "success", pr_urls[-1], None

    return "failed", None, error_tail()


def parse_json_lines(raw: str) -> tuple[list[dict], list[str]]:
    events: list[dict] = []
    non_json_lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError:
            non_json_lines.append(line)
            continue
        if isinstance(value, dict):
            events.append(value)
        else:
            non_json_lines.append(line)
    return events, non_json_lines


def collect_event_text(value) -> list[str]:
    chunks: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"text", "content"} and isinstance(item, str):
                chunks.append(item)
            else:
                chunks.extend(collect_event_text(item))
    elif isinstance(value, list):
        for item in value:
            chunks.extend(collect_event_text(item))
    return chunks


def write_conversation_json(
    path: Path,
    *,
    op_name: str,
    worktree_dir: Path | None,
    branch: str | None,
    gpu_id: int,
    command: list[str],
    prompt: str,
    returncode: int | None,
    stdout: str,
    stderr: str,
    start_time: str,
    end_time: str,
) -> list[dict]:
    events, stdout_non_json = parse_json_lines(stdout)
    stderr_events, stderr_non_json = parse_json_lines(stderr)
    payload = {
        "operator": op_name,
        "worktree": str(worktree_dir) if worktree_dir else None,
        "branch": branch,
        "gpu": gpu_id,
        "start_time": start_time,
        "end_time": end_time,
        "returncode": returncode,
        "command": command[:-1] + ["<prompt>"],
        "prompt": prompt,
        "stdout_events": events,
        "stderr_events": stderr_events,
        "stdout_non_json": stdout_non_json,
        "stderr_non_json": stderr_non_json,
        "stdout_raw": stdout,
        "stderr_raw": stderr,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return events + stderr_events


def last_agent_text(events: list[dict], raw_output: str) -> str:
    chunks: list[str] = []
    for event in events:
        chunks.extend(collect_event_text(event))
    text = "\n".join(chunk.strip() for chunk in chunks if chunk.strip())
    if text:
        return text[-4000:]
    return ANSI_RE.sub("", raw_output)[-4000:]


def write_operator_summary_log(path: Path, result: Result, agent_text: str) -> None:
    lines = [
        f"Operator: {result.operator}",
        f"Status: {result.status}",
        f"PR URL: {result.pr_url or ''}",
        f"GPU: {result.gpu if result.gpu is not None else ''}",
        f"Branch: {result.branch or ''}",
        f"Worktree: {result.worktree or ''}",
        f"Duration seconds: {result.duration_seconds}",
        f"Raw log: {result.log_file}",
        f"Conversation JSONL: {result.conversation_stream_file or ''}",
        f"Conversation JSON: {result.conversation_file or ''}",
        f"Error: {result.error_summary or ''}",
        "",
        "Agent final/context text:",
        agent_text,
    ]
    path.write_text("\n".join(lines).rstrip() + "\n")


def run_one_operator(
    op_name: str,
    gpu_pool: GpuPool,
    args: argparse.Namespace,
    status: dict[str, dict],
    status_lock: threading.Lock,
    run_log_dir: Path,
    index: int,
) -> Result:
    if shutdown_event.is_set():
        now = utc_now()
        return Result(op_name, "skipped", None, None, None, "", now, now, 0, error_summary="shutdown")

    if args.stagger > 0:
        time.sleep(index * args.stagger)

    start = utc_now()
    start_epoch = time.time()
    worktree_dir: Path | None = None
    branch: str | None = None
    log_file = run_log_dir / f"{safe_name(op_name)}.log"
    conversation_file = run_log_dir / f"{safe_name(op_name)}_conversation.json"
    conversation_stream_file = run_log_dir / f"{safe_name(op_name)}_conversation.jsonl"
    summary_log_file = run_log_dir / f"{safe_name(op_name)}_summary.log"

    waiting = Result(
        operator=op_name,
        status="waiting_gpu",
        gpu=None,
        worktree=None,
        branch=None,
        log_file=str(log_file),
        start_time=start,
        end_time="",
        duration_seconds=0,
        conversation_file=str(conversation_file),
        conversation_stream_file=str(conversation_stream_file),
        summary_log_file=str(summary_log_file),
        error_summary="waiting for an available GPU",
    )
    write_operator_summary_log(summary_log_file, waiting, "Waiting for an available GPU.")
    status[op_name] = asdict(waiting)
    save_status(args.status_file, status, status_lock)

    gpu_id = gpu_pool.acquire(op_name)
    if gpu_id is None:
        now = utc_now()
        return Result(op_name, "skipped", None, None, None, str(log_file), start, now, 0, error_summary="shutdown")

    print(f"[START] {op_name} | GPU {gpu_id} | log {log_file}")

    try:
        worktree_dir, branch = create_worktree(
            args.repo_dir,
            args.worktree_base,
            op_name,
            args.branch_prefix,
            args.repo_dir / ".git" / "batch_agent.lock",
            f"{args.upstream_remote}/{args.base}",
        )

        running = Result(
            operator=op_name,
            status="running",
            gpu=gpu_id,
            worktree=str(worktree_dir),
            branch=branch,
            log_file=str(log_file),
            start_time=start,
            end_time="",
            duration_seconds=0,
            conversation_file=str(conversation_file),
            conversation_stream_file=str(conversation_stream_file),
            summary_log_file=str(summary_log_file),
            error_summary="agent running; raw log and JSONL stream update in real time",
        )
        write_operator_summary_log(summary_log_file, running, "Agent started.")
        status[op_name] = asdict(running)
        save_status(args.status_file, status, status_lock)

        env = os.environ.copy()
        extend_no_proxy(env)
        env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
        if args.anthropic_base_url:
            env["ANTHROPIC_BASE_URL"] = args.anthropic_base_url
        if args.anthropic_model:
            env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = args.anthropic_model
        if args.anthropic_auth_token:
            env["ANTHROPIC_AUTH_TOKEN"] = args.anthropic_auth_token

        prompt = build_prompt(
            op_name,
            gpu_id,
            worktree_dir,
            args.skill_dir,
            args.scripts_dir,
            args.dry_run,
            args.timeout,
            args.base,
        )

        cmd = [
            args.claude_bin,
            "-p",
            "--verbose",
            "--output-format",
            "stream-json",
            "--permission-mode",
            args.permission_mode,
            "--add-dir",
            str(worktree_dir),
            "--add-dir",
            str(args.skill_dir),
        ]
        if args.model:
            cmd.extend(["--model", args.model])
        if args.settings_file:
            cmd.extend(["--settings", str(args.settings_file)])
        if args.max_budget_usd is not None:
            cmd.extend(["--max-budget-usd", str(args.max_budget_usd)])
        cmd.append(prompt)

        returncode, stdout, stderr = run_streaming_cmd(
            cmd,
            worktree_dir,
            timeout=args.timeout * 60,
            env=env,
            log_file=log_file,
            conversation_stream_file=conversation_stream_file,
            op_name=op_name,
            worktree_dir=worktree_dir,
            branch=branch,
            gpu_id=gpu_id,
            prompt=prompt,
            start_time=start,
        )
        output = stdout + "\n--- STDERR ---\n" + stderr
        end = utc_now()
        conversation_events = write_conversation_json(
            conversation_file,
            op_name=op_name,
            worktree_dir=worktree_dir,
            branch=branch,
            gpu_id=gpu_id,
            command=cmd,
            prompt=prompt,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            start_time=start,
            end_time=end,
        )

        parsed_status, pr_url, error = parse_agent_output(output, args.dry_run)
        agent_text = last_agent_text(conversation_events, output)
        if not error and agent_text:
            error = agent_text
        if returncode != 0 and parsed_status == "success":
            parsed_status = "failed"
            error = f"Claude exited {returncode}"
        elif returncode != 0 and not error:
            error = f"Claude exited {returncode}"

        duration = int(time.time() - start_epoch)
        final = Result(
            operator=op_name,
            status=parsed_status,
            gpu=gpu_id,
            worktree=str(worktree_dir),
            branch=branch,
            log_file=str(log_file),
            start_time=start,
            end_time=end,
            duration_seconds=duration,
            pr_url=pr_url,
            conversation_file=str(conversation_file),
            conversation_stream_file=str(conversation_stream_file),
            summary_log_file=str(summary_log_file),
            error_summary=error[:500] if error else None,
        )
        write_operator_summary_log(summary_log_file, final, agent_text)

        status[op_name] = asdict(final)
        save_status(args.status_file, status, status_lock)

        tag = parsed_status.upper()
        suffix = f" | PR {pr_url}" if pr_url else ""
        print(f"[{tag}] {op_name}{suffix}")

        if args.cleanup_success_worktrees and parsed_status == "success" and worktree_dir:
            cleanup_worktree(args.repo_dir, worktree_dir, branch, args.repo_dir / ".git" / "batch_agent.lock")

        return final

    except subprocess.TimeoutExpired:
        end = utc_now()
        final = Result(
            operator=op_name,
            status="failed",
            gpu=gpu_id,
            worktree=str(worktree_dir) if worktree_dir else None,
            branch=branch,
            log_file=str(log_file),
            start_time=start,
            end_time=end,
            duration_seconds=int(time.time() - start_epoch),
            conversation_file=str(conversation_file),
            conversation_stream_file=str(conversation_stream_file),
            summary_log_file=str(summary_log_file),
            error_summary=f"timeout after {args.timeout} minutes",
        )
        write_conversation_json(
            conversation_file,
            op_name=op_name,
            worktree_dir=worktree_dir,
            branch=branch,
            gpu_id=gpu_id,
            command=[],
            prompt="",
            returncode=None,
            stdout="",
            stderr=f"timeout after {args.timeout} minutes",
            start_time=start,
            end_time=end,
        )
        write_operator_summary_log(summary_log_file, final, final.error_summary or "")
        status[op_name] = asdict(final)
        save_status(args.status_file, status, status_lock)
        print(f"[TIMEOUT] {op_name}")
        return final

    except Exception as exc:
        end = utc_now()
        final = Result(
            operator=op_name,
            status="failed",
            gpu=gpu_id,
            worktree=str(worktree_dir) if worktree_dir else None,
            branch=branch,
            log_file=str(log_file),
            start_time=start,
            end_time=end,
            duration_seconds=int(time.time() - start_epoch),
            conversation_file=str(conversation_file),
            conversation_stream_file=str(conversation_stream_file),
            summary_log_file=str(summary_log_file),
            error_summary=str(exc)[:500],
        )
        write_conversation_json(
            conversation_file,
            op_name=op_name,
            worktree_dir=worktree_dir,
            branch=branch,
            gpu_id=gpu_id,
            command=[],
            prompt="",
            returncode=None,
            stdout="",
            stderr=str(exc),
            start_time=start,
            end_time=end,
        )
        write_operator_summary_log(summary_log_file, final, final.error_summary or "")
        status[op_name] = asdict(final)
        save_status(args.status_file, status, status_lock)
        print(f"[ERROR] {op_name}: {exc}")
        return final

    finally:
        gpu_pool.release(gpu_id)


def write_summary(run_log_dir: Path, run_id: str, results: list[Result], args: argparse.Namespace) -> tuple[Path, Path]:
    summary = run_log_dir / "summary.md"
    summary_json = run_log_dir / f"summary_{run_id}.json"
    success = sum(1 for r in results if r.status == "success")
    blocked = sum(1 for r in results if r.status == "blocked")
    failed = sum(1 for r in results if r.status == "failed")
    lines = [
        "# Claude Agent Batch PR Submit Summary",
        "",
        f"- Time: {utc_now()}",
        f"- Total: {len(results)}",
        f"- Success: {success}",
        f"- Blocked: {blocked}",
        f"- Failed: {failed}",
        "",
        "| Operator | Status | GPU | Duration(s) | PR | Worktree | Error |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for r in sorted(results, key=lambda item: item.operator):
        err = (r.error_summary or "").replace("\n", " ")[:180]
        lines.append(
            f"| {r.operator} | {r.status} | {r.gpu if r.gpu is not None else ''} | "
            f"{r.duration_seconds} | {r.pr_url or ''} | {r.worktree or ''} | {err} |"
        )
    summary.write_text("\n".join(lines) + "\n")
    payload = {
        "run_id": run_id,
        "time": utc_now(),
        "repo_dir": str(args.repo_dir),
        "ops_file": str(args.ops_file),
        "skill_dir": str(args.skill_dir),
        "scripts_dir": str(args.scripts_dir),
        "log_dir": str(run_log_dir),
        "dry_run": args.dry_run,
        "max_workers": args.max_workers,
        "gpus": args.gpus,
        "gpu_ids": getattr(args, "gpu_ids", None),
        "auto_gpu_check": not args.no_auto_gpu_check,
        "gpu_min_free_mb": args.gpu_min_free_mb,
        "gpu_max_util": args.gpu_max_util,
        "gpu_poll_interval": args.gpu_poll_interval,
        "gpu_lock_dir": str(args.gpu_lock_dir),
        "counts": {
            "total": len(results),
            "success": success,
            "blocked": blocked,
            "failed": failed,
            "skipped": sum(1 for r in results if r.status == "skipped"),
        },
        "results": [asdict(r) for r in sorted(results, key=lambda item: item.operator)],
    }
    summary_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return summary, summary_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parallel Claude-agent FlagGems PR submitter")
    parser.add_argument("--ops-file", required=True, help="Operator list file (one operator per line)")
    parser.add_argument("--repo-dir", default="/root/FlagGems", type=Path)
    parser.add_argument("--skill-dir", default="/root/baai-internship/skills/flaggems-pr-submit", type=Path)
    parser.add_argument("--scripts-dir", default=None, type=Path)
    parser.add_argument("--worktree-base", default="/tmp/flaggems_agent_worktrees", type=Path)
    parser.add_argument("--log-dir", default="/root/baai-internship/batch_pr_submit/logs/agent", type=Path)
    parser.add_argument("--status-file", default="/root/baai-internship/batch_pr_submit/agent_status.json", type=Path)
    parser.add_argument("--branch-prefix", default="agent-pr")
    parser.add_argument("--upstream-remote", default="upstream", help="Local upstream remote name")
    parser.add_argument("--base", default="infra-ci", help="Upstream base branch (experimental=infra-ci, mainline=master)")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--gpus", default="auto", help="'auto'/'all' or comma-separated physical GPU IDs")
    parser.add_argument("--no-auto-gpu-check", action="store_true", help="Do not wait for free GPUs; just round-robin the --gpus list")
    parser.add_argument("--gpu-min-free-mb", type=int, default=8000, help="GPU is considered free when memory.free is at least this value")
    parser.add_argument("--gpu-max-util", type=int, default=10, help="GPU is considered free when utilization.gpu is at most this percent")
    parser.add_argument("--gpu-poll-interval", type=float, default=30.0, help="Seconds between GPU availability checks")
    parser.add_argument("--gpu-lock-dir", default="/tmp/flaggems_gpu_locks", type=Path, help="Directory for cooperative per-GPU flock files")
    parser.add_argument("--timeout", type=int, default=60, help="Per-operator Claude timeout in minutes")
    parser.add_argument("--stagger", type=float, default=10.0, help="Seconds between worker starts")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Rerun operators already marked success")
    parser.add_argument("--fetch-retries", type=int, default=3)
    parser.add_argument("--cleanup-success-worktrees", action="store_true")
    parser.add_argument("--claude-bin", default="claude")
    parser.add_argument("--model", default=None)
    parser.add_argument("--settings-file", default=None, type=Path, help="Optional claude CLI --settings file")
    parser.add_argument("--permission-mode", default="acceptEdits")
    parser.add_argument("--max-budget-usd", type=float, default=None)
    parser.add_argument("--anthropic-base-url", default=os.environ.get("ANTHROPIC_BASE_URL"))
    parser.add_argument("--anthropic-model", default=os.environ.get("ANTHROPIC_DEFAULT_OPUS_MODEL"))
    parser.add_argument("--anthropic-auth-token", default=os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.repo_dir = args.repo_dir.resolve()
    args.skill_dir = args.skill_dir.resolve()
    args.scripts_dir = (args.scripts_dir or args.skill_dir / "scripts").resolve()
    args.worktree_base = args.worktree_base.resolve()
    args.log_dir = args.log_dir.resolve()
    args.status_file = args.status_file.resolve()
    args.gpu_lock_dir = args.gpu_lock_dir.resolve()
    if args.settings_file:
        args.settings_file = args.settings_file.resolve()

    require_path(args.repo_dir, "repo-dir")
    require_path(args.skill_dir / "SKILL.md", "skill")
    require_path(args.scripts_dir / "submit_operator.py", "submit_operator.py")
    require_path(args.scripts_dir / "extract_from_worktree.py", "extract_from_worktree.py")
    require_path(args.scripts_dir / "check_operator.py", "check_operator.py")
    require_path(Path(args.ops_file), "ops-file")
    if shutil.which(args.claude_bin) is None:
        raise FileNotFoundError(f"Claude binary not found: {args.claude_bin}")
    if args.settings_file:
        require_path(args.settings_file, "settings-file")
    if not args.dry_run and not os.environ.get("GH_TOKEN"):
        raise RuntimeError("GH_TOKEN is not set; export it before non-dry-run submission")

    ops = load_ops(Path(args.ops_file))
    status = load_status(args.status_file)
    todo_ops = [
        op for op in ops if args.force or status.get(op, {}).get("status") != "success"
    ]
    if not todo_ops:
        print("All operators are already marked success. Use --force to rerun.")
        return 0

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_log_dir = args.log_dir / run_id
    run_log_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("Claude Agent Batch PR Submit")
    print(f"Ops file:    {args.ops_file}")
    print(f"Repo:        {args.repo_dir}")
    print(f"Skill:       {args.skill_dir / 'SKILL.md'}")
    print(f"Operators:   {len(todo_ops)} / {len(ops)}")
    gpu_ids = parse_gpu_ids(args.gpus)
    args.gpu_ids = gpu_ids
    auto_gpu_check = not args.no_auto_gpu_check

    print(f"Workers:     {args.max_workers}")
    print(f"GPUs:        {args.gpus} -> {','.join(map(str, gpu_ids))}")
    print(
        "GPU check:   "
        + (
            f"auto free>= {args.gpu_min_free_mb}MiB util<= {args.gpu_max_util}%"
            if auto_gpu_check
            else "disabled"
        )
    )
    print(f"GPU locks:   {args.gpu_lock_dir}")
    print(f"Dry-run:     {args.dry_run}")
    print(f"Log dir:     {run_log_dir}")
    print("=" * 72)

    print(f"[PREP] Fetching {args.upstream_remote}/{args.base}...")
    git_fetch_upstream(args.repo_dir, args.fetch_retries, args.upstream_remote, args.base)
    print("[PREP] Fetch done.")

    gpu_pool = GpuPool(
        gpu_ids,
        auto_check=auto_gpu_check,
        min_free_mb=args.gpu_min_free_mb,
        max_utilization=args.gpu_max_util,
        poll_interval=args.gpu_poll_interval,
        lock_dir=args.gpu_lock_dir,
    )

    original_sigint = signal.getsignal(signal.SIGINT)

    def handle_sigint(signum, frame):
        print("\n[CTRL+C] stopping new jobs; waiting for active agents...")
        shutdown_event.set()
        signal.signal(signal.SIGINT, original_sigint)

    signal.signal(signal.SIGINT, handle_sigint)

    status_lock = threading.Lock()
    results: list[Result] = []
    max_workers = min(args.max_workers, len(todo_ops))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                run_one_operator,
                op,
                gpu_pool,
                args,
                status,
                status_lock,
                run_log_dir,
                index,
            ): op
            for index, op in enumerate(todo_ops)
        }
        for future in as_completed(futures):
            results.append(future.result())

    summary, summary_json = write_summary(run_log_dir, run_id, results, args)
    print("")
    print("=" * 72)
    print("COMPLETE")
    print(f"Summary markdown: {summary}")
    print(f"Summary JSON:     {summary_json}")
    print(f"Status:  {args.status_file}")
    print("=" * 72)
    return 0 if all(r.status == "success" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
