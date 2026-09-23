#!/usr/bin/env python3
"""从 summary.json 提取 benchmark 数据，生成 PR description markdown。

Usage:
    python format_benchmark.py <op> [--summary PATH] [--full]

    --summary: summary.json 路径（默认取 FLAGGEMS_SUMMARY_JSON 环境变量）
    --full:    输出完整 PR description 模板（不仅是表格）

环境变量:
    FLAGGEMS_SUMMARY_JSON  auto_gen benchmark 结果 summary.json 路径
    FLAGGEMS_ASCEND_OPS    Ascend kernel 目录（仓库内相对路径）
    FLAGGEMS_TITLE_PREFIX  PR 标题前缀，默认 [KernelGen][Ascend]
    FLAGGEMS_OP_STAGE      operators.yaml 的 stage 标注，默认 alpha 5.1
"""
import argparse
import json
import os
import sys

DEFAULT_SUMMARY = os.environ.get("FLAGGEMS_SUMMARY_JSON", "")
ASCEND_OPS = os.environ.get("FLAGGEMS_ASCEND_OPS", "src/flag_gems/runtime/backend/_ascend/ops")
TITLE_PREFIX = os.environ.get("FLAGGEMS_TITLE_PREFIX", "[KernelGen][Ascend]")
OP_STAGE = os.environ.get("FLAGGEMS_OP_STAGE", "alpha 5.1")


def load_benchmark(summary_path, op):
    with open(summary_path) as f:
        data = json.load(f)
    op_data = data.get("operators", {}).get(op)
    if not op_data:
        return None, None
    cc = op_data.get("cc_result", {})
    br = cc.get("benchmark_results", {})
    items = br.get("data", [])
    notes = cc.get("notes", "")
    return items, notes


def format_table(items):
    if not items:
        return "No benchmark data available."

    lines = []
    lines.append("| dtype | shape | Torch (ms) | Gems (ms) | Speedup |")
    lines.append("|---|---|---|---|---|")

    for item in items:
        dtype = item["dtype"].replace("torch.", "")
        shape = item["shape"]
        torch_ms = item["torch_latency_ms"]
        gems_ms = item["gems_latency_ms"]
        speedup = item["speedup"]

        if torch_ms >= 1:
            torch_str = f"{torch_ms:.1f}"
            gems_str = f"{gems_ms:.1f}"
        else:
            torch_str = f"{torch_ms:.3f}"
            gems_str = f"{gems_ms:.3f}"

        lines.append(f"| {dtype} | {shape} | {torch_str} | {gems_str} | {speedup}x |")

    return "\n".join(lines)


def format_full_pr(op, items, notes):
    table = format_table(items)

    desc = op.replace("_", " ")

    body = f"""# {TITLE_PREFIX} Add {op} operator with Triton kernel

## Summary
Add `{op}` operator Triton kernel implementation for the Ascend backend. {notes or f'Implements {desc} operation.'}

## Testing
- Parametrized tests for shapes × dtypes
- Validated against PyTorch CPU-FP64 reference (`utils.to_reference` with `--ref cpu`)

## Performance

{table}

## Files Changed
- `{ASCEND_OPS}/{op}.py`: Triton kernel implementation (Ascend)
- `{ASCEND_OPS}/__init__.py`: Register import and `__all__`
- `tests/test_{op}.py`: Accuracy tests
- `benchmark/test_{op}.py`: Performance benchmarks
- `conf/operators.yaml`: Add operator entry (stage: {OP_STAGE})"""

    return body


def main():
    parser = argparse.ArgumentParser(description="Format benchmark data for PR description")
    parser.add_argument("op", help="Operator name")
    parser.add_argument(
        "--summary",
        default=DEFAULT_SUMMARY,
        help="Path to summary.json (default: $FLAGGEMS_SUMMARY_JSON)",
    )
    parser.add_argument("--full", action="store_true", help="Output full PR description template")
    args = parser.parse_args()

    if not args.summary:
        print(
            "ERROR: summary.json 路径未指定。用 --summary PATH 或 export FLAGGEMS_SUMMARY_JSON=...",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.path.exists(args.summary):
        print(f"ERROR: summary.json not found: {args.summary}", file=sys.stderr)
        sys.exit(1)

    items, notes = load_benchmark(args.summary, args.op)
    if items is None:
        print(f"ERROR: operator '{args.op}' not found in summary.json", file=sys.stderr)
        sys.exit(1)

    if args.full:
        print(format_full_pr(args.op, items, notes))
    else:
        print(format_table(items))


if __name__ == "__main__":
    main()
