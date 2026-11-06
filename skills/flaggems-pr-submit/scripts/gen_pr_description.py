#!/usr/bin/env python3
"""Generate PR description data for FlagGems operator PRs.

Usage:
  # Full mode: run benchmark
  python gen_pr_description.py <op_name> --repo /path/to/repo

  # Pipe mode (benchmark already run)
  pytest benchmark/test_<op>.py --level core -s | \
    python gen_pr_description.py <op_name> --nvidia-stdin

  # From log file
  python gen_pr_description.py <op_name> --nvidia-log <path>

  # Skip re-running benchmark (use cached data)
  python gen_pr_description.py <op_name> --repo /path/to/repo --skip-run

Output: JSON to stdout with nvidia_benchmark rows.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path



# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Benchmark output line parser
# Format: SUCCESS  torch_ms  gems_ms  speedup  [tflops]  shape_detail
# ``shape_detail`` is a free-form ``str(metrics.shape_detail)`` and may be a bare
# list (``[torch.Size([...])]``) or a ``(list, kwargs_dict)`` tuple when the
# benchmark's ``input_fn`` yields extra keyword arguments (e.g. ``{'bins': ...}``,
# ``{'dim': -1}``). Match the detail as ``(.+?)\s*$`` so both forms parse.
BENCH_RE = re.compile(
    r"SUCCESS\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(?:([\d.]+)\s+)?(.+?)\s*$"
)
OP_HEADER_RE = re.compile(
    r"Operator:\s+(\S+)\s+Performance Test\s+\(dtype=([^,]+),"
)
SHAPE_RE = re.compile(r"torch\.Size\(\[([^\]]+)\]\)")


# ---------------------------------------------------------------------------
# Benchmark: run & parse
# ---------------------------------------------------------------------------


def find_benchmark_file(repo_dir: Path, op_name: str) -> Path | None:
    """Locate benchmark/test_<op>.py in repo.

    Test/benchmark file names drop the leading underscore: ``a`` and ``_a``
    share ``benchmark/test_a.py`` (see ``paths.test_file_id``). The bare name is
    therefore tried first.
    """
    bare = op_name.lstrip("_")
    bench_file = repo_dir / "benchmark" / f"test_{bare}.py"
    if bench_file.exists():
        return bench_file
    # legacy layout: a private-name op that still has its own test__<op>.py
    bench_file = repo_dir / "benchmark" / f"test_{op_name}.py"
    if bench_file.exists():
        return bench_file
    # fallback: glob
    candidates = list(repo_dir.glob(f"benchmark/test_{bare}*.py"))
    if candidates:
        return candidates[0]
    return None


def benchmark_mark(op_name: str) -> str:
    """pytest marker for this op (``underscore``-prefixed for private names)."""
    return f"underscore{op_name}" if op_name.startswith("_") else op_name


def run_nvidia_benchmark(repo_dir: Path, op_name: str, timeout: int = 300) -> str:
    """Run pytest benchmark with --level core, return stdout."""
    bench_file = find_benchmark_file(repo_dir, op_name)
    if not bench_file:
        raise FileNotFoundError(
            f"No benchmark file found for '{op_name}' in {repo_dir}/benchmark/"
        )
    rel = bench_file.relative_to(repo_dir)
    # ``-m <mark>`` keeps a shared file (``a`` + ``_a`` in test_a.py) from
    # reporting the neighbour operator's rows as this operator's performance.
    cmd = [
        "python", "-m", "pytest", str(rel),
        "-m", benchmark_mark(op_name), "--level", "core", "-s",
    ]
    result = subprocess.run(
        cmd,
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout


def parse_benchmark_output(text: str) -> list[dict]:
    """Extract performance rows from benchmark output."""
    rows = []
    current_op = None
    current_dtype = None
    for line in text.split("\n"):
        header = OP_HEADER_RE.search(line)
        if header:
            current_op = header.group(1).strip()
            current_dtype = header.group(2).strip().replace("torch.", "")
            continue

        m = BENCH_RE.search(line)
        if not m:
            continue
        shape_raw = m.group(5).strip()
        shape_match = SHAPE_RE.findall(shape_raw)
        shape = shape_match[0] if shape_match else shape_raw
        rows.append(
            {
                "operator": current_op,
                "dtype": current_dtype,
                "shape": shape,
                "torch_ms": float(m.group(1)),
                "gems_ms": float(m.group(2)),
                "speedup": float(m.group(3)),
                "tflops": float(m.group(4)) if m.group(4) else 0.0,
            }
        )
    return rows


def compute_operator_means(rows: list[dict], fallback_op: str) -> list[dict]:
    """Compute arithmetic mean speedup per operator/variant in display order."""
    groups: dict[str, list[float]] = {}
    order = []
    for row in rows:
        op = row.get("operator") or fallback_op
        if op not in groups:
            groups[op] = []
            order.append(op)
        if row.get("speedup") is not None:
            groups[op].append(row["speedup"])

    means = []
    for op in order:
        values = groups[op]
        mean = sum(values) / len(values) if values else 0.0
        means.append(
            {"operator": op, "case_count": len(values), "speedup": round(mean, 3)}
        )
    return means


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    p = argparse.ArgumentParser(
        description="Generate PR description data for FlagGems operator PRs"
    )
    p.add_argument("op_name", help="Operator name (e.g., special_bessel_j1)")
    p.add_argument(
        "--repo",
        default="/root/FlagGems",
        help="Path to FlagGems repo",
    )
    p.add_argument("--nvidia-log", help="Path to Nvidia benchmark log file")
    p.add_argument(
        "--nvidia-stdin",
        action="store_true",
        help="Read Nvidia benchmark output from stdin",
    )
    p.add_argument(
        "--skip-run",
        action="store_true",
        help="Skip running benchmark (emit an empty benchmark section)",
    )
    p.add_argument(
        "--output", "-o",
        help="Output file (default: stdout)",
    )
    args = p.parse_args()

    op_name = args.op_name
    repo_dir = Path(args.repo).resolve()

    # --- Nvidia benchmark ---
    nvidia_rows = []
    nvidia_status = "skipped"
    nvidia_cmd = ""

    if args.nvidia_stdin:
        nvidia_rows = parse_benchmark_output(sys.stdin.read())
        nvidia_status = "parsed"
    elif args.nvidia_log:
        with open(args.nvidia_log) as f:
            nvidia_rows = parse_benchmark_output(f.read())
        nvidia_status = "parsed"
    elif not args.skip_run:
        try:
            raw = run_nvidia_benchmark(repo_dir, op_name)
            bench_file = find_benchmark_file(repo_dir, op_name)
            nvidia_cmd = (
                f"pytest {bench_file.relative_to(repo_dir)} "
                f"-m {benchmark_mark(op_name)} --level core -s"
                if bench_file
                else ""
            )
            nvidia_rows = parse_benchmark_output(raw)
            nvidia_status = "success" if nvidia_rows else "no_data"
        except Exception as e:
            nvidia_status = f"error: {e}"

    # --- Compute stats ---
    am_speedup = 0.0
    if nvidia_rows:
        am_speedup = sum(r["speedup"] for r in nvidia_rows) / len(nvidia_rows)

    nvidia_case_count = len(nvidia_rows) if nvidia_rows else 0
    operator_means = compute_operator_means(nvidia_rows, op_name)

    warnings = []

    # --- Assemble output ---
    output = {
        "operator": op_name,
        "nvidia_benchmark": {
            "status": nvidia_status,
            "command": nvidia_cmd,
            "level": "core",
            "rows": nvidia_rows,
            "case_count": nvidia_case_count,
            "arithmetic_mean_speedup": round(am_speedup, 3),
            "operator_means": operator_means,
        },
        "warnings": warnings,
    }

    json_str = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w") as f:
            f.write(json_str)
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
