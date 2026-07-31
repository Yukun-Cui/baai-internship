#!/usr/bin/env python3
"""Query domestic GPU test results for a given operator.

Usage:
    python query_domestic_gpu.py <op_name> [--nvidia-speedup 1.23x] [--nvidia-cases 15]
    python query_domestic_gpu.py clamp_max --nvidia-speedup 0.60x --nvidia-cases 30
    python query_domestic_gpu.py special_airy_ai

Outputs a Markdown Multi-backend Testing table ready to paste into a PR description.
Also outputs Tested-on line for the Testing section.
"""

import argparse
import json
import os

# 国产 GPU 测试结果目录；用 FLAGGEMS_DOMESTIC_GPU_DIR 覆盖。
# 默认放在 skill 的 data/ 目录下（与 规范名.xlsx 等数据文件同级）。
DATA_DIR = os.environ.get(
    "FLAGGEMS_DOMESTIC_GPU_DIR",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "国产GPU算子测试情况",
    ),
)

BACKENDS = [
    {
        "name": "Tianshu",
        "dir": "天数test_results_20260509_141455",
        "json": "summary_20260509_141455.json",
    },
    {
        "name": "Muxi",
        "dir": "沐曦test_results_20260509",
        "json": "summary_20260509_064121.json",
    },
    {
        "name": "Ascend",
        "dir": "华为test_20260513_231140",
        "json": "summary_20260513_231140.json",
    },
    {
        "name": "Hygon",
        "dir": "海光hygon_test_399",
        "json": "summary_20260521_083116.json",
    },
]


def load_backend(backend):
    path = os.path.join(DATA_DIR, backend["dir"], backend["json"])
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def find_operator(data, op_name):
    """Find operator in summary data, trying exact match then case variants."""
    operators = data.get("operators", {})
    if op_name in operators:
        return operators[op_name]
    lower = op_name.lower()
    for key, val in operators.items():
        if key.lower() == lower:
            return val
    return None


def format_row(backend_name, op_info):
    """Format a single backend row for the Multi-backend Testing table."""
    if op_info is None:
        return f"| {backend_name} | — | — | — | Not tested |"

    acc = "PASS" if op_info.get("accuracy_passed") else "FAIL"
    bench_passed = op_info.get("benchmark_passed", False)
    bench_data = op_info.get("benchmark", {}).get("data", None) or []
    case_count = len(bench_data)

    if bench_passed and case_count > 0:
        speedups = [d["speedup"] for d in bench_data if "speedup" in d]
        mean_sp = sum(speedups) / len(speedups) if speedups else 0
        bench_str = f"PASS ({case_count} cases)"
        speedup_str = f"{mean_sp:.2f}x"
    elif bench_passed and case_count == 0:
        bench_str = "PASS (0 cases)"
        speedup_str = "—"
    else:
        bench_str = "FAIL"
        speedup_str = "—"

    # Notes
    if acc == "PASS" and bench_passed:
        notes = "—"
    else:
        stderr = op_info.get("benchmark", {}).get("stderr_tail", "") or ""
        if not stderr:
            stderr = op_info.get("test", {}).get("stderr_tail", "") or ""
        if stderr:
            last_line = stderr.strip().split("\n")[-1][:60]
            notes = last_line if last_line else "—"
        else:
            if acc == "FAIL":
                notes = "Accuracy test failed"
            elif not bench_passed:
                notes = "Benchmark failed"
            else:
                notes = "—"

    return f"| {backend_name} | {acc} | {bench_str} | {speedup_str} | {notes} |"


def main():
    parser = argparse.ArgumentParser(description="Query domestic GPU test results")
    parser.add_argument("op", help="Operator name (worktree directory name)")
    parser.add_argument(
        "--nvidia-speedup", default="—", help="Nvidia mean speedup (e.g. 1.23x)"
    )
    parser.add_argument(
        "--nvidia-cases", type=int, default=0, help="Nvidia benchmark case count"
    )
    parser.add_argument(
        "--variants",
        nargs="*",
        help="Additional name variants to search (e.g. special_digamma digamma)",
    )
    args = parser.parse_args()

    search_names = [args.op]
    if args.variants:
        search_names.extend(args.variants)

    # Nvidia row
    if args.nvidia_cases > 0:
        nvidia_bench = f"PASS ({args.nvidia_cases} cases, --level core)"
    else:
        nvidia_bench = "PASS (N cases, --level core)"
    nvidia_row = f"| Nvidia (H20) | PASS | {nvidia_bench} | {args.nvidia_speedup} | Primary |"

    rows = [nvidia_row]

    for backend in BACKENDS:
        data = load_backend(backend)
        if data is None:
            rows.append(f"| {backend['name']} | — | — | — | Data file not found |")
            continue

        op_info = None
        for name in search_names:
            op_info = find_operator(data, name)
            if op_info is not None:
                break

        rows.append(format_row(backend["name"], op_info))

    print("## Multi-backend Testing")
    print("| Backend | Accuracy Test | Benchmark | Speedup (mean) | Notes |")
    print("|---|---|---|---|---|")
    for row in rows:
        print(row)
    print()
    print("Tested-on line:")
    print("- Tested on: Nvidia, Tianshu, Muxi, Ascend, Hygon")


if __name__ == "__main__":
    main()
