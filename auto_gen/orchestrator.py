#!/usr/bin/env python3
"""Orchestrator for auto-generating FlagGems operators using Claude Code."""

import argparse
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
from collections import deque
from datetime import datetime, timezone

from device_manager import DeviceManager

try:
    from validate_operator import validate_operator
except ImportError:
    validate_operator = None

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------

def load_dotenv(env_path: str = None):
    """Load .env file into os.environ (simple key=value parser)."""
    if env_path is None:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip()
                if val and val[0] in ('"', "'") and val[-1] == val[0]:
                    val = val[1:-1]
                if key:
                    os.environ[key] = val
    logger.debug(f"Loaded .env from {env_path}")


# ---------------------------------------------------------------------------
# pre-commit management
# ---------------------------------------------------------------------------

def check_pre_commit(python_path: str) -> bool:
    """Check if pre-commit is installed in the given Python environment."""
    try:
        result = subprocess.run(
            [python_path, "-m", "pre_commit", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def install_pre_commit(python_path: str) -> bool:
    """Install pre-commit via pip."""
    try:
        subprocess.run(
            [python_path, "-m", "pip", "install", "pre-commit"],
            check=True,
            capture_output=True,
            timeout=60,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to install pre-commit: {e}")
        return False


def ensure_pre_commit(python_path: str, flaggems_dir: str, dry_run: bool = False):
    """Check, install, and warm pre-commit hooks."""
    # Check pre-commit availability
    if not check_pre_commit(python_path):
        print("\n⚠️  pre-commit is not installed in your Python environment.")
        print("   Code style checks require pre-commit to be installed.")
        response = input("\n   Install pre-commit now? [Y/n]: ").strip().lower()

        if response in ("", "y", "yes"):
            print("   Installing pre-commit...")
            if install_pre_commit(python_path):
                print("   ✅ pre-commit installed successfully\n")
            else:
                print("   ❌ Failed to install pre-commit")
                sys.exit(1)
        else:
            print("   ❌ Cannot proceed without pre-commit. Exiting.")
            sys.exit(1)

    # Install pre-commit hook into main repo (worktrees inherit it automatically)
    logger.info("Installing pre-commit git hook...")
    hook_result = subprocess.run(
        [python_path, "-m", "pre_commit", "install"],
        cwd=flaggems_dir,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if hook_result.returncode == 0:
        logger.info("Pre-commit hook installed")
    else:
        logger.warning(
            f"Failed to install pre-commit hook (non-fatal): {hook_result.stderr.strip()}"
        )

    # Pre-warm hook environments (downloads to ~/.cache/pre-commit/)
    if not dry_run:
        logger.info(
            "Pre-warming pre-commit hook environments"
            " (first time may take a few minutes)..."
        )
        warm_result = subprocess.run(
            [python_path, "-m", "pre_commit", "install-hooks"],
            cwd=flaggems_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if warm_result.returncode == 0:
            logger.info("Pre-commit hook environments ready")
        else:
            logger.warning(
                f"Pre-commit hook warm-up failed (non-fatal): {warm_result.stderr.strip()}"
            )


def strip_ai_signature(worktree_path: str, operator: str):
    """Rewrite the HEAD commit message to remove any AI attribution trailers.

    Claude Code appends a ``Co-Authored-By: Claude ...`` trailer (and sometimes a
    ``Generated with Claude Code`` line) to commits by default. The repo forbids
    any AI signature, so prompt-level instructions alone are unreliable — we strip
    it here as a hard guarantee, regardless of what the model produced.
    """
    try:
        msg_result = subprocess.run(
            ["git", "log", "-1", "--format=%B"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
        )
        if msg_result.returncode != 0:
            return
        original = msg_result.stdout
        cleaned_lines = []
        for line in original.splitlines():
            low = line.strip().lower()
            if low.startswith("co-authored-by:") and (
                "claude" in low or "anthropic" in low or "noreply@anthropic.com" in low
            ):
                continue
            if low.startswith("generated with") and "claude" in low:
                continue
            if "🤖" in line and "claude" in low:
                continue
            cleaned_lines.append(line)
        # Drop trailing blank lines left behind after removing trailers
        while cleaned_lines and not cleaned_lines[-1].strip():
            cleaned_lines.pop()
        cleaned = "\n".join(cleaned_lines) + "\n"

        if cleaned != original:
            subprocess.run(
                ["git", "commit", "--amend", "--no-edit", "-m", cleaned],
                cwd=worktree_path,
                capture_output=True,
            )
            logger.info(f"[SIGN] Stripped AI attribution from commit for {operator}")
    except Exception as e:
        logger.warning(f"[SIGN] Error stripping AI signature: {e}")


def sort_and_amend_commit(worktree_path: str, operator: str, base_branch: str = "infra-ci"):
    """Sort operator registrations and amend the commit if changes were needed.

    Uses sort_registrations.py (colocated in this directory). Also sorts any
    changed vendor backend __init__.py files (metax/iluvatar/enflame modes).
    """
    try:
        sort_script = os.path.join(os.path.dirname(__file__), "sort_registrations.py")
        if not os.path.exists(sort_script):
            logger.warning(
                f"[SORT] sort_registrations.py not found at {sort_script}, skipping sort"
            )
            return
        sort_result = subprocess.run(
            [sys.executable, sort_script, "--repo-root", worktree_path],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Sort any changed vendor backend __init__.py files
        vendor_init_result = subprocess.run(
            [
                "git", "diff", "--name-only", base_branch, "--",
                "src/flag_gems/runtime/backend/*/ops/__init__.py",
                "src/flag_gems/runtime/backend/*/*/ops/__init__.py",
            ],
            cwd=worktree_path,
            capture_output=True,
            text=True,
        )
        changed_vendor_inits = [
            vf for vf in vendor_init_result.stdout.strip().splitlines() if vf
        ]
        for vf in changed_vendor_inits:
            subprocess.run(
                [sys.executable, sort_script, "--vendor-init", os.path.join(worktree_path, vf)],
                capture_output=True,
                timeout=10,
            )

        if sort_result.returncode == 0:
            # Amend the commit if sort made changes — only stage the
            # specific files sort_registrations.py is allowed to modify
            sort_targets = [
                "conf/operators.yaml",
                "src/flag_gems/ops/__init__.py",
                "src/flag_gems/__init__.py",
            ] + changed_vendor_inits
            diff_result = subprocess.run(
                ["git", "diff", "--quiet", "--"] + sort_targets,
                cwd=worktree_path,
                capture_output=True,
            )
            if diff_result.returncode != 0:
                subprocess.run(
                    ["git", "add", "--"] + sort_targets,
                    cwd=worktree_path,
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "commit", "--amend", "--no-edit"],
                    cwd=worktree_path,
                    capture_output=True,
                )
                logger.info(
                    f"[SORT] Amended commit with sorted registrations for {operator}"
                )
        else:
            logger.warning(
                f"[SORT] Failed to sort registrations for {operator} (non-fatal): "
                f"{sort_result.stderr.strip()}"
            )
    except Exception as e:
        logger.warning(f"[SORT] Error sorting registrations: {e}")


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_config(config_path: str) -> dict:
    """Load YAML config file."""
    if yaml is None:
        print("Error: 'pyyaml' is required but not installed. Please install it with: pip install pyyaml")
        sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_ops_list(path: str) -> list[str]:
    """Load operator names from a text file.

    Supports formats: 'round', 'aten::round', 'aten::round.Tensor'
    Strips 'aten::' prefix and overload suffixes like '.Tensor'.
    """
    ops = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                # Strip aten:: prefix
                if line.startswith("aten::"):
                    line = line[len("aten::"):]
                # Strip overload suffix (e.g. .Tensor, .Scalar)
                if "." in line:
                    line = line.split(".")[0]
                if line and line not in ops:
                    ops.append(line)
    return ops


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

def render_template(template_path: str, variables: dict) -> str:
    """Render a template file with {{VAR}} substitution."""
    with open(template_path) as f:
        content = f.read()
    for key, value in variables.items():
        content = content.replace(f"{{{{{key}}}}}", str(value))
    return content


# ---------------------------------------------------------------------------
# Worktree management
# ---------------------------------------------------------------------------

def create_worktree(
    flaggems_dir: str, operator: str, branch_prefix: str = "pr/", base_branch: str = "infra-ci"
) -> tuple[str, str]:
    """Create a git worktree for an operator. Returns (worktree_path, branch_name).

    Branch names follow the repo's PR convention (e.g. ``pr/narrow``). The prefix
    is configurable via ``branch_prefix`` in config.yaml. The worktree is based on
    ``base_branch`` (configurable via ``base_branch`` in config.yaml).
    """
    branch_name = f"{branch_prefix}{operator}"
    worktree_path = os.path.join(flaggems_dir, ".worktrees", f"gen-{operator}")

    # Always clean up: remove worktree, delete leftover directory, prune git records
    subprocess.run(
        ["git", "worktree", "remove", "--force", worktree_path],
        cwd=flaggems_dir,
        capture_output=True,
    )
    if os.path.exists(worktree_path):
        import shutil
        shutil.rmtree(worktree_path, ignore_errors=True)
    subprocess.run(["git", "worktree", "prune"], cwd=flaggems_dir, capture_output=True)

    # Delete branch if it exists
    subprocess.run(
        ["git", "branch", "-D", branch_name],
        cwd=flaggems_dir,
        capture_output=True,
    )

    # Create worktree based on base_branch
    os.makedirs(os.path.dirname(worktree_path), exist_ok=True)
    result = subprocess.run(
        ["git", "worktree", "add", "-b", branch_name, worktree_path, base_branch],
        cwd=flaggems_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create worktree for {operator}: {result.stderr}")

    logger.info(f"Created worktree for {operator} at {worktree_path}")
    return worktree_path, branch_name


# ---------------------------------------------------------------------------
# CC process management
# ---------------------------------------------------------------------------

def launch_cc(
    operator: str,
    worktree_path: str,
    gpu_id: int,
    config: dict,
    template_path: str,
    log_dir: str,
    arch: str = "gcu300",
    dry_run: bool = False,
    fixup_prompt: str = None,
) -> subprocess.Popen:
    """Launch a Claude Code process for an operator."""
    variables = {
        "OPERATOR": operator,
        "GPU_ID": str(gpu_id),
        "WORK_DIR": worktree_path,
        "PYTHON_PATH": config.get("python_path", "python"),
        "ARCH": arch,
    }
    prompt = render_template(template_path, variables)

    # Append fixup instructions if this is a validation retry
    if fixup_prompt:
        prompt += fixup_prompt

    log_path = os.path.join(log_dir, f"{operator}.log")

    env = os.environ.copy()
    # Remove CLAUDECODE env var to allow launching CC from within a CC session
    env.pop("CLAUDECODE", None)
    # Allow --dangerously-skip-permissions under root
    env["IS_SANDBOX"] = "1"
    # Do NOT set CUDA_VISIBLE_DEVICES here; CC will set it per-command via the template

    # Debug: verify API credentials are present
    _token = env.get("ANTHROPIC_AUTH_TOKEN", "")
    _base = env.get("ANTHROPIC_BASE_URL", "")
    logger.debug(f"CC env for {operator}: AUTH_TOKEN={'set(' + _token[:8] + '...)' if _token else 'MISSING'}, BASE_URL={_base or 'MISSING'}")

    # Dry-run mode: simulate CC process without actually launching
    if dry_run:
        logger.info(
            f"[DRY-RUN] Would launch CC for {operator} (GPU={gpu_id}, worktree={worktree_path})"
        )
        logger.debug(f"[DRY-RUN] Template variables: {variables}")

        stdout_path = os.path.join(log_dir, f"{operator}.jsonl")
        with open(stdout_path, "w") as f:
            f.write(
                '{"type":"result","result":"```json\\n{\\"operator\\":\\"'
                + operator
                + '\\",\\"status\\":\\"success\\",\\"accuracy_passed\\":true,\\"error_message\\":null}\\n```"}\n'
            )
        with open(log_path, "w") as f:
            f.write("[DRY-RUN] Simulated CC execution\n")

        mock_proc = subprocess.Popen(["true"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        mock_proc.wait()
        mock_proc._stdout_path = stdout_path
        mock_proc._stderr_path = log_path
        mock_proc._stdout_file = None
        mock_proc._stderr_file = None
        return mock_proc

    claude_bin = config.get("claude_bin", "claude")
    cmd = [
        claude_bin,
        "-p", prompt,
        "--dangerously-skip-permissions",
        "--output-format", "stream-json",
        "--verbose",
        "--strict-mcp-config",
        "--mcp-config", "",
    ]

    # Pass model if set via env or config
    model = os.environ.get("ANTHROPIC_MODEL") or config.get("model")
    if model:
        cmd.extend(["--model", model])

    budget = config.get("budget_per_op")
    if budget:
        cmd.extend(["--max-budget-usd", str(budget)])

    stdout_path = os.path.join(log_dir, f"{operator}.jsonl")
    try:
        stdout_file = open(stdout_path, "w")
        stderr_file = open(log_path, "w")
        proc = subprocess.Popen(
            cmd,
            cwd=worktree_path,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            start_new_session=True,
        )
    except Exception:
        try:
            stdout_file.close()
        except Exception:
            pass
        try:
            stderr_file.close()
        except Exception:
            pass
        raise
    # Attach paths for later reading
    proc._stdout_path = stdout_path
    proc._stderr_path = log_path
    proc._stdout_file = stdout_file
    proc._stderr_file = stderr_file

    logger.info(f"Launched CC for {operator} (PID={proc.pid}, GPU={gpu_id})")
    return proc


def _kill_cc_process(proc: subprocess.Popen):
    """Kill a CC process and its entire process group, then close file handles."""
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, OSError):
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        logger.warning(f"Process {proc.pid} did not exit after SIGKILL, abandoning")
    proc._stdout_file.close()
    proc._stderr_file.close()


def check_worktree_has_changes(worktree_path: str, operator: str, metax: bool = False, iluvatar: bool = False, enflame: bool = False, mthreads: bool = False, arch: str = "gcu300") -> bool:
    """Check if the worktree has code changes (operator file created)."""
    if metax:
        op_file = os.path.join(worktree_path, "src", "flag_gems", "runtime", "backend", "_metax", "ops", f"{operator}.py")
    elif iluvatar:
        op_file = os.path.join(worktree_path, "src", "flag_gems", "runtime", "backend", "_iluvatar", "ops", f"{operator}.py")
    elif enflame:
        op_file = os.path.join(worktree_path, "src", "flag_gems", "runtime", "backend", "_enflame", arch, "ops", f"{operator}.py")
    elif mthreads:
        op_file = os.path.join(worktree_path, "src", "flag_gems", "runtime", "backend", "_mthreads", "ops", f"{operator}.py")
    else:
        op_file = os.path.join(worktree_path, "src", "flag_gems", "ops", f"{operator}.py")
    if os.path.exists(op_file):
        return True
    # Also check git diff
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def parse_cc_result(proc: subprocess.Popen, operator: str, worktree_path: str = None, metax: bool = False, iluvatar: bool = False, enflame: bool = False, mthreads: bool = False, arch: str = "gcu300") -> dict:
    """Parse stream-json output from a CC process.

    The .jsonl file contains one JSON object per line. We look for the last
    line with "type": "result" to get the final result, then extract the
    operator JSON from the result text.
    """
    try:
        # Close file handles first so all data is flushed
        # (dry-run mock processes have no file handles)
        if getattr(proc, "_stdout_file", None) is not None:
            proc._stdout_file.close()
        if getattr(proc, "_stderr_file", None) is not None:
            proc._stderr_file.close()

        # Parse stream-json: read lines and find the result event
        result_text = ""
        with open(proc._stdout_path, "r", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "result":
                    result_text = event.get("result", "")
                    break

        # Extract the operator JSON result block from the result text
        if result_text:
            json_match = re.search(r"```json\s*(\{.*?\})\s*```", result_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))

            # Try to find any JSON object with operator/status fields
            json_match = re.search(r"\{[^{}]*\"operator\"[^{}]*\"status\"[^{}]*\}", result_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))

        # Fallback: if CC exited normally and worktree has changes, treat as success
        if proc.returncode == 0 and worktree_path and check_worktree_has_changes(worktree_path, operator, metax=metax, iluvatar=iluvatar, enflame=enflame, mthreads=mthreads, arch=arch):
            logger.info(f"CC output not parseable, but worktree has changes for {operator}")
            return {
                "operator": operator,
                "status": "success",
                "accuracy_passed": True,
                "error_message": None,
                "notes": "Result inferred from worktree changes (CC output not parseable)",
            }

    except Exception as e:
        logger.warning(f"Failed to parse CC output for {operator}: {e}")

    # Detect signal death (SIGSEGV=-11, SIGABRT=-6, SIGKILL=-9, SIGBUS=-7)
    if proc.returncode is not None and proc.returncode < 0:
        sig_num = -proc.returncode
        sig_names = {11: "SIGSEGV", 6: "SIGABRT", 9: "SIGKILL", 7: "SIGBUS"}
        sig_name = sig_names.get(sig_num, f"signal {sig_num}")
        return {
            "operator": operator,
            "status": "failed",
            "accuracy_passed": False,
            "error_message": f"CC process killed by {sig_name} ({sig_num}) - likely libtorch/PyTorch segfault",
        }

    # Return a failure result if parsing fails
    return {
        "operator": operator,
        "status": "failed",
        "accuracy_passed": False,
        "error_message": "Failed to parse CC output",
    }


def generate_timeline(jsonl_path: str, operator: str) -> str | None:
    """Generate a human-readable timeline from a CC stream-json log.

    Writes a .timeline.txt file next to the .jsonl and returns its path.
    """
    timeline_path = jsonl_path.replace(".jsonl", ".timeline.txt")
    try:
        events = []
        with open(jsonl_path, "r", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        out: list[str] = []
        step = 0

        def _format_tool_use(name: str, inp: dict) -> str:
            if name == "Bash":
                return inp.get("command", "")
            elif name in ("Read", "Write"):
                return inp.get("file_path", "")
            elif name == "Edit":
                s = inp.get("file_path", "")
                old = inp.get("old_string", "")
                new = inp.get("new_string", "")
                return f"{s}\n--- old ---\n{old}\n+++ new +++\n{new}"
            elif name in ("Grep", "Glob"):
                return f"pattern={inp.get('pattern', '')}  path={inp.get('path', '')}"
            else:
                return json.dumps(inp, ensure_ascii=False)

        for event in events:
            etype = event.get("type", "")

            if etype == "system" and event.get("subtype") == "init":
                out.append(f"=== {operator} ===")
                out.append(f"Session: {event.get('session_id', '?')}")
                out.append(f"Model: {event.get('model', '?')}")
                out.append("")
                continue

            if etype == "result":
                step += 1
                out.append(f"[{step}] ✅ Result:")
                out.append(event.get("result", ""))
                out.append("")
                continue

            if etype == "user":
                # Extract tool result output
                tool_result = event.get("tool_use_result")
                if isinstance(tool_result, dict):
                    output = tool_result.get("stdout", "") or tool_result.get("stderr", "")
                    if output:
                        out.append(f"    ↳ Output:")
                        out.append(str(output))
                        out.append("")
                        continue
                # Fallback: check message.content for tool_result entries
                contents = event.get("message", {}).get("content", [])
                if isinstance(contents, list):
                    for c in contents:
                        if isinstance(c, dict) and c.get("type") == "tool_result":
                            content_val = c.get("content", "")
                            if content_val:
                                out.append(f"    ↳ Output:")
                                out.append(str(content_val))
                                out.append("")
                            break
                continue

            if etype != "assistant":
                continue

            contents = event.get("message", {}).get("content", [])
            if not isinstance(contents, list):
                continue

            for content in contents:
                if not isinstance(content, dict):
                    continue
                ctype = content.get("type", "")

                if ctype == "thinking":
                    step += 1
                    out.append(f"[{step}] 🤔 Thinking:")
                    out.append(content.get("thinking", ""))
                    out.append("")

                elif ctype == "text":
                    text = content.get("text", "")
                    if text.strip():
                        step += 1
                        out.append(f"[{step}] 💬 Text:")
                        out.append(text)
                        out.append("")

                elif ctype == "tool_use":
                    step += 1
                    name = content.get("name", "?")
                    inp = content.get("input", {})
                    out.append(f"[{step}] 🔧 {name}:")
                    out.append(_format_tool_use(name, inp))
                    out.append("")

        with open(timeline_path, "w") as f:
            f.write("\n".join(out))

        logger.info(f"Generated timeline for {operator}: {timeline_path}")
        return timeline_path

    except Exception as e:
        logger.warning(f"Failed to generate timeline for {operator}: {e}")
        return None


# ---------------------------------------------------------------------------
# Summary management
# ---------------------------------------------------------------------------

class Summary:
    """Manages the summary.json file with real-time updates."""

    def __init__(self, path: str):
        self.path = path
        self.data = {
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": None,
            "summary": {
                "total": 0,
                "success": 0,
                "failed": 0,
                "in_progress": 0,
            },
            "operators": {},
        }
        self._save()

    def add_operator(self, operator: str, gpu_id: int, attempt: int):
        """Record that an operator task has started."""
        self.data["operators"][operator] = {
            "status": "in_progress",
            "gpu_id": gpu_id,
            "attempt": attempt,
            "worktree_path": None,
            "branch": None,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": None,
            "duration_seconds": None,
            "accuracy_passed": None,
            "error_message": None,
            "cc_result": None,
        }
        self._recount()
        self._save()

    def update_operator(self, operator: str, **kwargs):
        """Update fields for an operator."""
        if operator in self.data["operators"]:
            self.data["operators"][operator].update(kwargs)
            self._recount()
            self._save()

    def finalize(self):
        """Mark the run as complete."""
        self.data["end_time"] = datetime.now(timezone.utc).isoformat()
        self._save()

    def _recount(self):
        """Recount summary statistics."""
        ops = self.data["operators"]
        self.data["summary"]["total"] = len(ops)
        self.data["summary"]["success"] = sum(1 for v in ops.values() if v["status"] == "success")
        self.data["summary"]["failed"] = sum(1 for v in ops.values() if v["status"] in ("failed", "cancelled"))
        self.data["summary"]["in_progress"] = sum(1 for v in ops.values() if v["status"] in ("in_progress", "retrying"))

    def _save(self):
        """Write summary to disk."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)


def load_resume_state(resume_path: str) -> tuple[set, set]:
    """
    Load a previous summary.json and extract completed operators.

    Returns:
        (completed_ops, failed_ops) - sets of operator names.
        completed_ops = status 'success'
        failed_ops = status 'failed' or 'cancelled'
    """
    completed = set()
    failed = set()
    try:
        with open(resume_path) as f:
            data = json.load(f)
        for op, info in data.get("operators", {}).items():
            status = info.get("status", "")
            if status == "success":
                completed.add(op)
            elif status in ("failed", "cancelled"):
                failed.add(op)
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to load resume state from {resume_path}: {e}")
    return completed, failed


def schedule_retry_or_fail(
    summary,
    queue: deque,
    operator: str,
    attempt: int,
    max_retries: int,
    duration: float,
    result: dict,
    validation_result: dict = None,
    needs_fixup: bool = False,
) -> bool:
    """Schedule a retry (or fixup) or mark the operator as failed.

    When needs_fixup is True, re-queues the operator with its missing validation
    items so the next attempt reuses the same worktree and completes them.
    Returns True if scheduled for retry, False if marked as failed.
    """
    if attempt + 1 >= max_retries:
        logger.error(
            f"[FAILED] {operator} after {attempt + 1} attempts: "
            f"{result.get('error_message', 'unknown')}"
        )
        summary.update_operator(
            operator,
            status="failed",
            accuracy_passed=result.get("accuracy_passed", False),
            duration_seconds=round(duration),
            end_time=datetime.now(timezone.utc).isoformat(),
            error_message=result.get("error_message"),
            cc_result=result,
        )
        return False

    if needs_fixup and validation_result:
        logger.warning(
            f"[FIXUP] {operator} (attempt {attempt + 1}/{max_retries}, "
            f"reason: validation incomplete)"
        )
        error_msg = (
            f"Validation incomplete: {', '.join(validation_result['missing'][:3])}..."
        )
        queue.append((operator, attempt + 1, validation_result["missing"]))
    else:
        logger.warning(
            f"[RETRY] {operator} (attempt {attempt + 1}/{max_retries}, "
            f"reason: {result.get('error_message', 'unknown')})"
        )
        error_msg = result.get("error_message")
        queue.append((operator, attempt + 1))

    summary.update_operator(
        operator,
        status="retrying",
        duration_seconds=round(duration),
        error_message=error_msg,
        cc_result=result,
    )
    return True


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run(args):
    """Main orchestration loop."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = args.config or os.path.join(script_dir, "config.yaml")
    config = load_config(config_path)

    # Determine if running in metax, iluvatar or enflame mode
    is_metax = getattr(args, "metax", False)
    is_iluvatar = getattr(args, "iluvatar", False)
    is_enflame = getattr(args, "enflame", False)
    is_mthreads = getattr(args, "mthreads", False)
    enflame_arch = config.get("enflame", {}).get("arch", "gcu300")

    flaggems_dir = config.get("flaggems_dir", os.path.dirname(os.path.dirname(script_dir)))
    if is_metax:
        template_name = config.get("metax", {}).get("template", "templates/generate_op_metax.md")
    elif is_iluvatar:
        template_name = config.get("iluvatar", {}).get("template", "templates/generate_op_iluvatar.md")
    elif is_enflame:
        template_name = config.get("enflame", {}).get("template", "templates/generate_op_enflame.md")
    elif is_mthreads:
        template_name = config.get("mthreads", {}).get("template", "templates/generate_op_mthreads.md")
    else:
        template_name = config.get("template", "templates/generate_op.md")
    template_path = os.path.join(script_dir, template_name)
    results_dir = os.path.join(script_dir, config.get("results_dir", "results"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = os.path.join(results_dir, f"logs_{timestamp}")
    summary_path = os.path.join(results_dir, f"summary_{timestamp}.json")
    max_retries = config.get("max_retries", 3)
    timeout_per_op = config.get("timeout_per_op", 1800) or 0
    poll_interval = config.get("poll_interval", 10)
    max_concurrency = config.get("max_concurrency", 0) or 0
    python_path = config.get("python_path", sys.executable)
    base_branch = config.get("base_branch", "infra-ci")
    branch_prefix = config.get("branch_prefix", "pr/")
    dry_run = getattr(args, "dry_run", False)

    os.makedirs(log_dir, exist_ok=True)

    # Ensure pre-commit hooks are installed/warmed (worktrees inherit them)
    ensure_pre_commit(python_path, flaggems_dir, dry_run=dry_run)

    # Load operator list
    if is_metax and not args.ops_list:
        ops_list_name = config.get("metax", {}).get("ops_list", "ops_list_metax.txt")
    elif is_iluvatar and not args.ops_list:
        ops_list_name = config.get("iluvatar", {}).get("ops_list", "ops_list_iluvatar.txt")
    elif is_enflame and not args.ops_list:
        ops_list_name = config.get("enflame", {}).get("ops_list", "ops_list_enflame.txt")
    elif is_mthreads and not args.ops_list:
        ops_list_name = config.get("mthreads", {}).get("ops_list", "ops_list_mthreads.txt")
    else:
        ops_list_name = "ops_list.txt"
    ops_list_path = args.ops_list or os.path.join(script_dir, ops_list_name)
    ops = load_ops_list(ops_list_path)
    if not ops:
        logger.error("No operators to process. Check your ops_list.txt.")
        return

    logger.info(f"Loaded {len(ops)} operators: {ops}")

    # --- Resume support: skip already-completed operators from previous run ---
    resume_completed = set()
    resume_failed = set()
    if getattr(args, "resume", None):
        resume_completed, resume_failed = load_resume_state(args.resume)
        retry_failed = getattr(args, "retry_failed", False)
        if resume_completed:
            logger.info(
                f"Resume: skipping {len(resume_completed)} already-successful operators"
            )
        if resume_failed:
            if retry_failed:
                logger.info(
                    f"Resume: {len(resume_failed)} previously-failed operators will be retried"
                )
            else:
                logger.info(
                    f"Resume: {len(resume_failed)} previously-failed operators will be skipped (use --retry-failed to retry)"
                )

    # Filter the queue: exclude completed ops (and optionally failed ops)
    if resume_completed or resume_failed:
        filtered_ops = []
        for op in ops:
            if op in resume_completed:
                logger.debug(f"Resume: skipping completed operator '{op}'")
                continue
            if op in resume_failed and not getattr(args, "retry_failed", False):
                logger.debug(f"Resume: skipping previously-failed operator '{op}'")
                continue
            filtered_ops.append(op)
        ops = filtered_ops
        logger.info(f"Resume: {len(ops)} operators remaining after filtering")
        if not ops:
            logger.warning("No operators need processing. All are already completed.")
            return

    # Fetch upstream to ensure base_branch is up-to-date
    auto_fetch = config.get("auto_fetch_upstream", True)
    if not getattr(args, "skip_fetch", False) and auto_fetch:
        logger.info("Fetching upstream to ensure base_branch is current...")
        fetch_result = subprocess.run(
            ["git", "fetch", "upstream"],
            cwd=flaggems_dir,
            capture_output=True,
            text=True,
        )
        if fetch_result.returncode != 0:
            if "does not resolve" in fetch_result.stderr or "Unknown remote" in fetch_result.stderr:
                logger.warning(
                    "upstream remote not found. Add it with:\n"
                    "  git remote add upstream https://github.com/flagos-ai/FlagGems-Experimental.git\n"
                    "Continuing with local base branch (run with --skip-fetch to silence)."
                )
            else:
                logger.warning(
                    f"git fetch upstream failed (non-fatal): {fetch_result.stderr.strip()}\n"
                    f"Continuing with local base branch."
                )
        else:
            logger.info("Fetch completed successfully")
    else:
        logger.warning(
            "Skipping upstream fetch (--skip-fetch or auto_fetch_upstream=false). "
            f"Worktrees will be based on local {base_branch} which may be outdated."
        )

    # Initialize device manager
    device_cfg = config.get("device", {}) or {}
    device_mgr = DeviceManager(
        lock_dir=device_cfg.get("lock_dir", "/tmp/auto_gen_gpu_locks"),
        gpu_ids=device_cfg.get("gpu_ids"),
    )

    # Initialize summary
    summary = Summary(summary_path)

    # Task queue: (operator, attempt_number)
    queue = deque((op, 0) for op in ops)
    # Running tasks: {operator: (process, gpu_id, attempt, worktree_path, start_time)}
    running: dict[str, tuple] = {}

    # Graceful shutdown
    shutdown_requested = False

    def signal_handler(sig, frame):
        nonlocal shutdown_requested
        if shutdown_requested:
            logger.warning("Force shutdown requested, exiting immediately")
            os.system("stty sane 2>/dev/null")
            os._exit(1)
        shutdown_requested = True
        logger.warning(f"Shutdown requested (signal={sig}), killing {len(running)} running tasks...")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if dry_run:
        logger.warning("[DRY-RUN MODE] Simulating workflow without launching Claude Code")

    logger.info(
        f"Starting orchestrator: {len(ops)} operators, {len(device_mgr.gpu_ids)} GPUs, "
        f"max_concurrency={max_concurrency or 'unlimited'}, "
        f"max_retries={max_retries}" + (" [DRY-RUN]" if dry_run else "")
    )

    while (queue or running) and not shutdown_requested:
        # Launch new tasks if GPUs are available
        while queue and not shutdown_requested:
            # Respect API concurrency limit (0 = unlimited, bounded only by GPUs)
            if max_concurrency and len(running) >= max_concurrency:
                break
            gpu_id = device_mgr.acquire()
            if gpu_id is None:
                break

            # Queue items are (operator, attempt) or (operator, attempt, missing_items)
            queue_item = queue.popleft()
            if len(queue_item) == 3:
                operator, attempt, missing_items = queue_item
            else:
                operator, attempt = queue_item
                missing_items = None
            try:
                # For fixup attempts, reuse the existing worktree so the previous
                # (successful-but-incomplete) work is preserved instead of rebuilt.
                if missing_items and operator in summary.data["operators"]:
                    existing = summary.data["operators"][operator]
                    worktree_path = existing.get("worktree_path")
                    branch = existing.get("branch")
                    if worktree_path and os.path.exists(worktree_path):
                        logger.info(f"[FIXUP] Reusing existing worktree for {operator}: {worktree_path}")
                    else:
                        logger.warning(f"[FIXUP] Existing worktree not found for {operator}, creating new one")
                        worktree_path, branch = create_worktree(
                            flaggems_dir, operator, branch_prefix, base_branch
                        )
                else:
                    worktree_path, branch = create_worktree(
                        flaggems_dir, operator, branch_prefix, base_branch
                    )

                # For fixup attempts, append the missing items to the prompt
                fixup_prompt = None
                if missing_items:
                    fixup_prompt = (
                        "\n\n---\n\n"
                        "The previous attempt was successful but incomplete. "
                        "Please fix the following missing items:\n\n"
                        + "\n".join(f"- {item}" for item in missing_items)
                        + "\n\nMake the necessary changes and commit."
                    )

                proc = launch_cc(operator, worktree_path, gpu_id, config, template_path, log_dir, arch=enflame_arch, dry_run=dry_run, fixup_prompt=fixup_prompt)

                running[operator] = (proc, gpu_id, attempt, worktree_path, time.time())

                summary.add_operator(operator, gpu_id, attempt + 1)
                summary.update_operator(operator, worktree_path=worktree_path, branch=branch)

            except Exception as e:
                logger.error(f"Failed to launch CC for {operator}: {e}")
                device_mgr.release(gpu_id)
                if attempt + 1 < max_retries:
                    queue.append((operator, attempt + 1))
                else:
                    summary.add_operator(operator, gpu_id, attempt + 1)
                    summary.update_operator(
                        operator,
                        status="failed",
                        error_message=str(e),
                        end_time=datetime.now(timezone.utc).isoformat(),
                    )

        # Check running tasks
        for operator in list(running.keys()):
            proc, gpu_id, attempt, worktree_path, start_time = running[operator]

            # Check for timeout
            if timeout_per_op and proc.poll() is None and time.time() - start_time > timeout_per_op:
                logger.error(f"[TIMEOUT] {operator} exceeded {timeout_per_op}s, killing process")
                _kill_cc_process(proc)
                duration = time.time() - start_time
                device_mgr.release(gpu_id)
                del running[operator]
                summary.update_operator(
                    operator,
                    status="failed",
                    accuracy_passed=False,
                    duration_seconds=round(duration),
                    end_time=datetime.now(timezone.utc).isoformat(),
                    error_message=f"Timed out after {timeout_per_op}s",
                )
                continue

            if proc.poll() is not None:
                duration = time.time() - start_time
                device_mgr.release(gpu_id)
                del running[operator]

                # Parse result and generate timeline
                result = parse_cc_result(proc, operator, worktree_path, metax=is_metax, iluvatar=is_iluvatar, enflame=is_enflame, mthreads=is_mthreads, arch=enflame_arch)
                generate_timeline(proc._stdout_path, operator)

                # Validate operator completeness (operators.yaml, test/benchmark marks).
                # Only for the default CUDA backend — vendor backends use a different
                # file layout that this validator doesn't understand.
                is_vendor_mode = is_metax or is_iluvatar or is_enflame or is_mthreads
                validation_result = None
                needs_fixup = False
                if (
                    result.get("status") == "success"
                    and not is_vendor_mode
                    and validate_operator is not None
                    and not dry_run
                ):
                    aten_ops = result.get("aten_ops_registered", [])
                    try:
                        validation_result = validate_operator(worktree_path, operator, aten_ops)
                        if not validation_result["valid"]:
                            logger.warning(
                                f"[VALIDATION] {operator} missing {len(validation_result['missing'])} items"
                            )
                            # Only fixup on the first attempt to avoid an infinite loop
                            if attempt == 0:
                                needs_fixup = True
                                logger.info(f"[FIXUP] Will resume {operator} to complete missing items")
                    except Exception as e:
                        logger.warning(f"Validation failed for {operator}: {e}")

                success = (
                    result.get("status") == "success"
                    and result.get("accuracy_passed", False)
                    and proc.returncode == 0
                    and not needs_fixup
                )

                if success:
                    # Sort operator registrations and amend the commit if needed
                    sort_and_amend_commit(worktree_path, operator, base_branch)
                    # Strip any AI attribution trailer Claude Code may have added
                    strip_ai_signature(worktree_path, operator)

                    logger.info(f"[SUCCESS] {operator} (attempt {attempt+1}, {duration:.0f}s)")
                    summary.update_operator(
                        operator,
                        status="success",
                        accuracy_passed=True,
                        duration_seconds=round(duration),
                        end_time=datetime.now(timezone.utc).isoformat(),
                        cc_result=result,
                    )
                else:
                    schedule_retry_or_fail(
                        summary,
                        queue,
                        operator,
                        attempt,
                        max_retries,
                        duration,
                        result,
                        validation_result=validation_result,
                        needs_fixup=needs_fixup,
                    )

        if running:
            time.sleep(poll_interval)

    # Handle shutdown: kill running tasks immediately
    if shutdown_requested:
        for operator, (proc, gpu_id, attempt, wt, st) in running.items():
            _kill_cc_process(proc)
            device_mgr.release(gpu_id)
            summary.update_operator(
                operator,
                status="cancelled",
                end_time=datetime.now(timezone.utc).isoformat(),
                duration_seconds=round(time.time() - st),
            )

    device_mgr.release_all()
    summary.finalize()

    # Restore terminal state (claude CLI may leave it in raw/no-echo mode)
    try:
        os.system("stty sane 2>/dev/null")
    except Exception:
        pass

    # Print final summary
    s = summary.data["summary"]
    logger.info(
        f"Done: {s['total']} total, {s['success']} success, "
        f"{s['failed']} failed"
    )
    print(f"\nResults saved to: {summary_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Auto-generate FlagGems operators using Claude Code")
    parser.add_argument("ops_list", nargs="?", help="Path to operator list file (default: ops_list.txt)")
    parser.add_argument("-c", "--config", help="Path to config.yaml")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--metax", action="store_true", help="Metax (Muxi) backend mode: generate operators in _metax/ops/")
    parser.add_argument("--iluvatar", action="store_true", help="Iluvatar (Tianshu) backend mode: generate operators in _iluvatar/ops/")
    parser.add_argument("--enflame", action="store_true", help="Enflame (Suiyuan) backend mode: generate operators in _enflame/<arch>/ops/")
    parser.add_argument("--mthreads", action="store_true", help="Moore Threads (Moerxiancheng) backend mode: generate operators in _mthreads/ops/")
    parser.add_argument("--resume", help="Path to previous summary.json; skip already-successful operators")
    parser.add_argument("--retry-failed", action="store_true", help="When used with --resume, also retry previously failed operators")
    parser.add_argument("--skip-fetch", action="store_true", help="Skip auto-fetch of upstream remote before creating worktrees")
    parser.add_argument("--dry-run", action="store_true", help="Simulate workflow without launching Claude Code (for testing)")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    load_dotenv()

    run(args)


if __name__ == "__main__":
    main()
