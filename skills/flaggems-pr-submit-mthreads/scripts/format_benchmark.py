#!/usr/bin/env python3
"""解析摩尔线程 benchmark 的 pytest stdout，生成 PR description markdown。

数据源是 worktree 中实跑的 benchmark 输出（不是预生成 JSON）：
    cd <worktree> && MUSA_VISIBLE_DEVICES=<gpu> python3 fix_worktree_import.py \\
        --pytest benchmark/test_<op>.py -m <op> -vs | tee /tmp/<op>_mthreads_bench.log

Usage:
    python format_benchmark.py <op> --bench-log /tmp/<op>_bench.log [--full]
    pytest ... -s | python format_benchmark.py <op> [--full]   # 从 stdin 读

    --full: 输出完整 PR description（含 Summary/Testing/Files），否则只输出表格
    --notes: 附加到 Summary 的一句话描述

加速比统计用几何平均（比率数据）。
"""
import argparse
import math
import re
import sys

# 与通用 skill (gen_pr_description.py) 保持同一套解析正则
BENCH_RE = re.compile(
    r"SUCCESS\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(?:([\d.]+)\s+)?[\[{(](.+?)[\]})]\s*$"
)
OP_HEADER_RE = re.compile(
    r"Operator:\s+(\S+)\s+Performance Test\s+\(dtype=([^,]+),"
)
SHAPE_RE = re.compile(r"torch\.Size\(\[([^\]]+)\]\)")


def geometric_mean(values):
    vals = [v for v in values if isinstance(v, (int, float)) and v > 0]
    if not vals:
        return 0.0
    return math.exp(sum(math.log(v) for v in vals) / len(vals))


def parse_benchmark_output(text):
    """从 pytest benchmark stdout 提取性能行。"""
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


def format_table(rows):
    if not rows:
        return "No benchmark data parsed. 确认 benchmark 以 `-s` 运行且有 SUCCESS 行。"

    has_tflops = any(r.get("tflops") for r in rows)
    if has_tflops:
        lines = [
            "| dtype | Size | Torch Latency (ms) | Gems Latency (ms) | Speedup | TFLOPS |",
            "|-------|------|--------------------|-------------------|---------|--------|",
        ]
    else:
        lines = [
            "| dtype | Size | Torch Latency (ms) | Gems Latency (ms) | Speedup |",
            "|-------|------|--------------------|-------------------|---------|",
        ]

    for r in rows:
        dtype = r.get("dtype") or "N/A"
        row = (
            f"| {dtype} | {r['shape']} | {r['torch_ms']:.6f} | "
            f"{r['gems_ms']:.6f} | {r['speedup']:.3f}x |"
        )
        if has_tflops:
            row += f" {r.get('tflops', 0):.3f} |"
        lines.append(row)

    gm = geometric_mean(r["speedup"] for r in rows)
    if gm:
        lines.append("")
        lines.append(f"**Geometric Mean Speedup: {gm:.2f}x**")
    return "\n".join(lines)


def format_full_pr(op, rows, notes):
    table = format_table(rows)
    desc = op.replace("_", " ")
    body = f"""# [KernelGen][MThreads] Add {op} Moore Threads specialized operator

## Summary
Add a Moore Threads (MUSA) specialized Triton kernel for `{op}`, overriding the generic
implementation via `runtime.replace_customized_ops()`. {notes or f'Implements the {desc} operation.'}

## Testing
- Reused the existing upstream accuracy tests `tests/test_{op}.py` (`-m {op}`)
- Validated against reference on the MUSA device; specialization confirmed active via the
  `GEMS_MTHREADS {op.upper()}` debug log
- Falls back to the generic implementation for unsupported dtype/device/shape
  (fp64/int64 are not supported on Moore Threads hardware)

## Performance
Compared against the generic FlagGems implementation on Moore Threads (MUSA).

### {op}
{table}

## Files Changed
- `src/flag_gems/runtime/backend/_mthreads/ops/{op}.py`: Moore Threads Triton kernel + fallback
- `src/flag_gems/runtime/backend/_mthreads/ops/__init__.py`: Register import and `__all__`"""
    return body


def main():
    parser = argparse.ArgumentParser(description="Parse Moore Threads benchmark stdout for PR description")
    parser.add_argument("op", help="Operator name")
    parser.add_argument("--bench-log", help="benchmark stdout 文件；缺省从 stdin 读")
    parser.add_argument("--notes", default="", help="附加到 Summary 的描述")
    parser.add_argument("--full", action="store_true", help="输出完整 PR description")
    args = parser.parse_args()

    if args.bench_log:
        with open(args.bench_log) as f:
            text = f.read()
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print("ERROR: 需要 --bench-log <file> 或从管道传入 benchmark 输出", file=sys.stderr)
        sys.exit(1)

    rows = parse_benchmark_output(text)
    if not rows:
        print("WARNING: 未解析到 benchmark 数据行（确认 pytest 用了 -s 且有 SUCCESS 行）", file=sys.stderr)

    if args.full:
        print(format_full_pr(args.op, rows, args.notes))
    else:
        print(format_table(rows))


if __name__ == "__main__":
    main()
