#!/usr/bin/env python3
"""Triton 算子合规性检查工具 - 通过 Claude Code CLI 判断算子实现是否合规。"""

import argparse
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent.absolute()


def load_dotenv(env_path: str = None):
    if env_path is None:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if not os.path.exists(env_path):
            env_path = "/root/baai-internship/auto_gen/.env"
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


def load_config(config_path: str) -> dict:
    if yaml is None:
        print("Error: pyyaml required. Install with: pip install pyyaml")
        sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_ops_list(path: str) -> list[str]:
    """Load operator names from a text file."""
    ops = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if line.startswith("aten::"):
                    line = line[len("aten::"):]
                if "." in line:
                    line = line.split(".")[0]
                if line and line not in ops:
                    ops.append(line)
    return ops


def find_op_file_in_dir(ops_dir: Path, op_name: str) -> Path | None:
    """Find the actual .py file for an operator in a directory.

    Handles naming variations: op_name='triu_' -> triu.py or triu_.py,
    op_name='_weight_norm' -> weightnorm.py or _weight_norm.py, etc.
    """
    candidates = [
        ops_dir / f"{op_name}.py",
        ops_dir / f"{op_name.strip('_')}.py",
        ops_dir / f"{op_name.replace('_', '')}.py",
        ops_dir / f"{op_name.lstrip('_')}.py",
        ops_dir / f"{op_name.rstrip('_')}.py",
        ops_dir / f"{op_name.lower()}.py",
        ops_dir / f"{op_name.lower().replace('_', '')}.py",
    ]
    # For names like avg_pool3d_backward -> avg_pool3d.py
    if "_backward" in op_name:
        base_name = op_name.replace("_backward", "")
        candidates.append(ops_dir / f"{base_name}.py")

    for c in candidates:
        if c.is_file():
            return c

    # Fallback: find any new .py file via git diff
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "master", "--diff-filter=A"],
            cwd=str(ops_dir.parent.parent.parent.parent),
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.strip().split("\n"):
            if line.startswith("src/flag_gems/ops/") and line.endswith(".py") and "__" not in line:
                p = ops_dir.parent.parent.parent.parent / line
                if p.is_file():
                    return p
    except Exception:
        pass

    return None


def scan_operators(config: dict, ops_filter: list[str] = None) -> list[dict]:
    """Scan operator files based on config. Returns list of {name, file, vendor, path}."""
    flaggems_dir = Path(config["flaggems_dir"])
    scan_mode = config.get("scan_mode", "single_worktree")
    scan_cfg = config.get("scan", {})
    operators = []

    if scan_mode == "multi_worktree":
        # Each operator has its own worktree
        pattern = config.get("worktree_pattern", ".worktrees/gen-{op}")
        if not ops_filter:
            logger.error("multi_worktree mode requires --ops-list or -o to specify operators")
            return []

        for op_name in ops_filter:
            wt_rel = pattern.replace("{op}", op_name)
            base = flaggems_dir / wt_rel

            if not base.is_dir():
                logger.warning(f"Worktree not found for {op_name}: {base}")
                continue

            # Try nvidia ops dir
            if scan_cfg.get("nvidia_ops", True):
                ops_dir = base / "src" / "flag_gems" / "ops"
                if ops_dir.is_dir():
                    op_file = find_op_file_in_dir(ops_dir, op_name)
                    if op_file:
                        operators.append({
                            "name": op_name,
                            "file": str(op_file.relative_to(base)),
                            "vendor": "nvidia",
                            "path": str(op_file),
                        })
                        continue

            # Try backend vendor dirs
            backend_dir = base / "src" / "flag_gems" / "runtime" / "backend"
            if backend_dir.is_dir():
                backends_cfg = scan_cfg.get("backends", [])
                for vendor_dir in sorted(backend_dir.iterdir()):
                    if not vendor_dir.is_dir() or vendor_dir.name.startswith("__"):
                        continue
                    if backends_cfg and vendor_dir.name not in backends_cfg:
                        continue
                    ops_subdir = vendor_dir / "ops"
                    if not ops_subdir.is_dir():
                        continue
                    op_file = find_op_file_in_dir(ops_subdir, op_name)
                    if op_file:
                        operators.append({
                            "name": op_name,
                            "file": str(op_file.relative_to(base)),
                            "vendor": vendor_dir.name.strip("_"),
                            "path": str(op_file),
                        })
                        break

            if not any(o["name"] == op_name for o in operators):
                logger.warning(f"No operator file found for {op_name} in {base}")

    else:
        # Original single_worktree mode
        worktree = config.get("worktree", "")
        base = flaggems_dir / worktree if worktree else flaggems_dir

        # NVIDIA ops
        if scan_cfg.get("nvidia_ops", True):
            ops_dir = base / "src" / "flag_gems" / "ops"
            if ops_dir.is_dir():
                for f in sorted(ops_dir.glob("*.py")):
                    if f.name.startswith("__"):
                        continue
                    op_name = f.stem
                    if ops_filter and op_name not in ops_filter:
                        continue
                    operators.append({
                        "name": op_name,
                        "file": str(f.relative_to(base)),
                        "vendor": "nvidia",
                        "path": str(f),
                    })

        # Backend vendors
        backends_cfg = scan_cfg.get("backends", [])
        backend_dir = base / "src" / "flag_gems" / "runtime" / "backend"
        if backend_dir.is_dir():
            for vendor_dir in sorted(backend_dir.iterdir()):
                if not vendor_dir.is_dir() or vendor_dir.name.startswith("__"):
                    continue
                if backends_cfg and vendor_dir.name not in backends_cfg:
                    continue
                ops_subdir = vendor_dir / "ops"
                if not ops_subdir.is_dir():
                    continue
                for f in sorted(ops_subdir.glob("*.py")):
                    if f.name.startswith("__"):
                        continue
                    op_name = f.stem
                    if ops_filter and op_name not in ops_filter:
                        continue
                    operators.append({
                        "name": op_name,
                        "file": str(f.relative_to(base)),
                        "vendor": vendor_dir.name.strip("_"),
                        "path": str(f),
                    })

    return operators


def render_prompt(template_path: str, operator: dict) -> str:
    """Render the prompt template with operator info and source code."""
    with open(template_path) as f:
        template = f.read()
    with open(operator["path"]) as f:
        source = f.read()

    replacements = {
        "{{OPERATOR}}": operator["name"],
        "{{VENDOR}}": operator["vendor"],
        "{{FILE_PATH}}": operator["file"],
        "{{SOURCE_CODE}}": source,
    }
    for key, val in replacements.items():
        template = template.replace(key, val)
    return template


def ensure_cc_config(env: dict) -> str:
    """Create isolated Claude Code config dir. Returns config dir path."""
    cc_config_dir = str(SCRIPT_DIR / ".claude_config")
    os.makedirs(cc_config_dir, exist_ok=True)
    settings_path = os.path.join(cc_config_dir, "settings.json")
    settings = {
        "env": {},
        "skipDangerousModePermissionPrompt": True,
        "skipWebFetchPreflight": True,
    }
    for key in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
                "ANTHROPIC_API_KEY", "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS"):
        val = env.get(key)
        if val:
            settings["env"][key] = val
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
    return cc_config_dir


def launch_check(operator: dict, config: dict, template_path: str, log_dir: str) -> subprocess.Popen:
    """Launch a Claude Code CLI process to check one operator."""
    prompt = render_prompt(template_path, operator)
    claude_cfg = config.get("claude", {})

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env["IS_SANDBOX"] = "1"

    cc_config_dir = ensure_cc_config(env)
    env["CLAUDE_CONFIG_DIR"] = cc_config_dir

    claude_bin = claude_cfg.get("bin", "claude")
    cmd = [
        claude_bin,
        "-p", prompt,
        "--dangerously-skip-permissions",
        "--output-format", "stream-json",
        "--verbose",
    ]

    model = claude_cfg.get("model")
    if model:
        cmd.extend(["--model", model])

    stdout_path = os.path.join(log_dir, f"{operator['vendor']}_{operator['name']}.jsonl")
    stderr_path = os.path.join(log_dir, f"{operator['vendor']}_{operator['name']}.log")

    stdout_file = open(stdout_path, "w")
    stderr_file = open(stderr_path, "w")

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(SCRIPT_DIR),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            start_new_session=True,
        )
    except Exception:
        stdout_file.close()
        stderr_file.close()
        raise

    proc._stdout_path = stdout_path
    proc._stderr_path = stderr_path
    proc._stdout_file = stdout_file
    proc._stderr_file = stderr_file
    proc._operator = operator

    logger.info(f"Launched check for {operator['vendor']}/{operator['name']} (PID={proc.pid})")
    return proc


def kill_process(proc: subprocess.Popen):
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
        pass
    proc._stdout_file.close()
    proc._stderr_file.close()


def parse_result(proc: subprocess.Popen) -> dict:
    """Parse the LLM judgment from stream-json output."""
    operator = proc._operator
    try:
        proc._stdout_file.close()
        proc._stderr_file.close()
    except Exception:
        pass

    result_text = ""
    try:
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
    except Exception as e:
        logger.warning(f"Failed to read output for {operator['name']}: {e}")

    if result_text:
        # Try to extract JSON from code block
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", result_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON object
        json_match = re.search(r"\{[^{}]*\"pass\"[^{}]*\}", result_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        # Try more permissive: find any JSON with "pass" key
        json_match = re.search(r"\{.*?\"pass\"\s*:.*?\}", result_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

    return {
        "pass": None,
        "reason": "Failed to parse LLM output",
        "has_triton_kernel": None,
        "torch_compute_calls": [],
        "violations": [],
        "_parse_error": True,
        "_raw_output": result_text[:500] if result_text else "",
    }


def run(args):
    """Main orchestration loop."""
    config_path = args.config or str(SCRIPT_DIR / "config.yaml")
    config = load_config(config_path)
    claude_cfg = config.get("claude", {})

    max_concurrent = claude_cfg.get("max_concurrent", 4)
    timeout = claude_cfg.get("timeout", 120)
    template_path = str(SCRIPT_DIR / "prompt_template.md")
    output_dir = SCRIPT_DIR / config.get("output_dir", "results")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = str(output_dir / f"logs_{timestamp}")
    os.makedirs(log_dir, exist_ok=True)

    # Scan operators
    ops_filter = None
    if args.operator:
        ops_filter = args.operator
    elif args.ops_list or config.get("ops_list"):
        ops_list_path = args.ops_list or config.get("ops_list")
        if not os.path.isabs(ops_list_path):
            ops_list_path = os.path.join(str(SCRIPT_DIR), ops_list_path)
        ops_filter = load_ops_list(ops_list_path)
        logger.info(f"Loaded {len(ops_filter)} operators from {ops_list_path}")

    operators = scan_operators(config, ops_filter=ops_filter)
    if args.vendor:
        operators = [op for op in operators if op["vendor"] in args.vendor]
    if args.limit:
        operators = operators[:args.limit]

    if not operators:
        logger.error("No operators to check. Verify config and filters.")
        return

    logger.info(f"Scanning {len(operators)} operators, max_concurrent={max_concurrent}")

    # Results
    results = []
    queue = list(operators)
    running: dict[str, tuple] = {}  # key -> (proc, start_time)
    shutdown = False

    def signal_handler(sig, frame):
        nonlocal shutdown
        if shutdown:
            os._exit(1)
        shutdown = True
        logger.warning(f"Shutdown requested, killing {len(running)} processes...")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    while (queue or running) and not shutdown:
        # Launch new processes
        while queue and len(running) < max_concurrent and not shutdown:
            op = queue.pop(0)
            key = f"{op['vendor']}_{op['name']}"
            try:
                proc = launch_check(op, config, template_path, log_dir)
                running[key] = (proc, time.time())
            except Exception as e:
                logger.error(f"Failed to launch check for {key}: {e}")
                results.append({
                    "operator": op["name"],
                    "file": op["file"],
                    "vendor": op["vendor"],
                    "pass": None,
                    "reason": f"Launch failed: {e}",
                    "violations": [],
                })

        # Check running processes
        for key in list(running.keys()):
            proc, start_time = running[key]

            # Timeout check
            if timeout and proc.poll() is None and time.time() - start_time > timeout:
                logger.warning(f"[TIMEOUT] {key} after {timeout}s")
                kill_process(proc)
                del running[key]
                op = proc._operator
                results.append({
                    "operator": op["name"],
                    "file": op["file"],
                    "vendor": op["vendor"],
                    "pass": None,
                    "reason": f"Timeout after {timeout}s",
                    "violations": [],
                })
                continue

            if proc.poll() is not None:
                del running[key]
                op = proc._operator
                judgment = parse_result(proc)
                result_entry = {
                    "operator": op["name"],
                    "file": op["file"],
                    "vendor": op["vendor"],
                    "pass": judgment.get("pass"),
                    "reason": judgment.get("reason", ""),
                    "has_triton_kernel": judgment.get("has_triton_kernel"),
                    "torch_compute_calls": judgment.get("torch_compute_calls", []),
                    "violations": judgment.get("violations", []),
                }
                if judgment.get("_parse_error"):
                    result_entry["_parse_error"] = True
                    result_entry["_raw_output"] = judgment.get("_raw_output", "")

                status = "PASS" if judgment.get("pass") else "FAIL" if judgment.get("pass") is False else "ERROR"
                logger.info(f"[{status}] {op['vendor']}/{op['name']}: {judgment.get('reason', '')[:80]}")
                results.append(result_entry)

        if running:
            time.sleep(2)

    # Handle shutdown
    if shutdown:
        for key, (proc, _) in running.items():
            kill_process(proc)

    # Generate report
    pass_count = sum(1 for r in results if r["pass"] is True)
    fail_count = sum(1 for r in results if r["pass"] is False)
    error_count = sum(1 for r in results if r["pass"] is None)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "flaggems_dir": config["flaggems_dir"],
            "model": claude_cfg.get("model", ""),
            "max_concurrent": max_concurrent,
            "timeout": timeout,
        },
        "summary": {
            "total": len(results),
            "pass": pass_count,
            "fail": fail_count,
            "error": error_count,
        },
        "results": results,
    }

    report_path = str(output_dir / f"report_{timestamp}.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info(f"\nDone: {len(results)} total, {pass_count} pass, {fail_count} fail, {error_count} error")
    print(f"\nReport saved to: {report_path}")

    # Print summary of failures
    failures = [r for r in results if r["pass"] is False]
    if failures:
        print(f"\n--- FAILURES ({len(failures)}) ---")
        for r in failures:
            print(f"  {r['vendor']}/{r['operator']}: {r['reason']}")


def main():
    parser = argparse.ArgumentParser(description="Triton 算子合规性检查工具")
    parser.add_argument("-c", "--config", help="Path to config.yaml")
    parser.add_argument("-o", "--operator", nargs="*", help="Only check specific operator(s)")
    parser.add_argument("--ops-list", help="Path to operator list file (one op per line)")
    parser.add_argument("--vendor", nargs="*", help="Only check specific vendor(s)")
    parser.add_argument("--limit", type=int, help="Limit number of operators to check")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
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
