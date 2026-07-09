#!/usr/bin/env python3
"""Update open FlagGems PR performance sections from CI benchmark logs.

This script intentionally leaves submit_operator.py's local H20 flow alone.
It is for the later CI-backfill pass: parse CI logs, render the same standard
template sections, patch the PR body, and write one timestamped audit file for
all PRs touched in the run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterable

SKILL_SCRIPTS_DIR = Path(
    os.environ.get(
        "FLAGGEMS_SKILL_SCRIPTS_DIR",
        "/root/baai-internship/skills/flaggems-pr-submit/scripts",
    )
).resolve()
sys.path.insert(0, str(SKILL_SCRIPTS_DIR))

from gen_pr_description import compute_operator_means, query_domestic_gpu
from submit_operator import format_pr_body, get_op_id


DEFAULT_REPO = "flagos-ai/FlagGems"
DEFAULT_AUTHOR = "Yukun-Cui"
DEFAULT_REPO_DIR = "/root/FlagGems"
DEFAULT_AUDIT_DIR = "/root/baai-internship/ci_performance_update/reports"
DEFAULT_MAX_UPDATES = 4

SECTION_RE_TEMPLATE = r"(?ms)^## {heading}\n.*?(?=^## |\Z)"
MEAN_ROW_RE = re.compile(
    r"^\|\s*(?!-+|Operator\b)([^|]+?)\s*\|\s*\**([0-9]+(?:\.[0-9]+)?)\**\s*\|",
    re.MULTILINE,
)
CASE_RE = re.compile(r"\|\s*Nvidia \([^)]+\)\s*\|\s*PASS \((\d+) cases\)")
TITLE_OP_RE = re.compile(r"Add\s+(.+?)\s+operator\b", re.IGNORECASE)
SPECIALIZED_PASS_RE = re.compile(
    r"^\|\s*(?:Tianshu / Iluvatar|Muxi / Metax|[^|]*backend-[^|]*|[^|]*specialization[^|]*)\s*\|\s*PASS\s*\|",
    re.IGNORECASE | re.MULTILINE,
)
BENCH_RE = re.compile(
    r"SUCCESS\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(?:([\d.]+)\s+)?[\[{](.+?)[\]}]\s*$"
)
OP_HEADER_RE = re.compile(
    r"Operator:\s+(\S+)\s+Performance Test\s+\(dtype=([^,]+),"
)
SHAPE_RE = re.compile(r"torch\.Size\(\[([^\]]+)\]\)")


def run_gh(args: list[str], *, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["gh", *args],
        input=input_text,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"gh {' '.join(args)} failed: {detail}")
    return result


def load_json_from_gh(args: list[str]) -> object:
    result = run_gh(args)
    return json.loads(result.stdout)


def normalize_device(device: str) -> str:
    device = device.strip()
    if not device:
        return "CI"
    return device.upper() if re.fullmatch(r"h\d+", device, re.IGNORECASE) else device


def retag_nvidia_device(markdown: str, device: str) -> str:
    device = normalize_device(device)
    markdown = re.sub(r"\(NVIDIA H\d+\)", f"(NVIDIA {device})", markdown)
    markdown = re.sub(r"Nvidia \(H\d+\)", f"Nvidia ({device})", markdown)
    return markdown


def _shape_from_detail(detail: str) -> str:
    shapes = SHAPE_RE.findall(detail)
    if not shapes:
        return detail.strip()
    if len(shapes) == 1:
        return shapes[0].strip()

    parsed = []
    for shape in shapes:
        dims = [d.strip() for d in shape.split(",") if d.strip()]
        parsed.append(dims)

    # Matmul + bias benchmark detail commonly prints [M,K], [K,N], [N].
    # PR tables are easier to compare as [M, K, N]. Require the bias vector
    # so ordinary binary elementwise inputs like [M,N], [M,N] stay explicit.
    if (
        len(parsed) >= 3
        and len(parsed[0]) == 2
        and len(parsed[1]) == 2
        and len(parsed[2]) == 1
    ):
        m, k = parsed[0]
        _k2, n = parsed[1]
        return f"{m}, {k}, {n}"

    return "; ".join(f"[{', '.join(dims)}]" for dims in parsed)


def parse_benchmark_output(text: str) -> list[dict]:
    """Extract benchmark rows from CI/job logs.

    This local parser preserves multi-input benchmark shape details better than
    the submit skill's generic parser, which only keeps the first torch.Size.
    """
    rows = []
    current_op = None
    current_dtype = None
    for line in text.splitlines():
        header = OP_HEADER_RE.search(line)
        if header:
            current_op = header.group(1).strip()
            current_dtype = header.group(2).strip().replace("torch.", "")
            continue

        match = BENCH_RE.search(line)
        if not match:
            continue
        rows.append(
            {
                "operator": current_op,
                "dtype": current_dtype,
                "shape": _shape_from_detail(match.group(5).strip()),
                "torch_ms": float(match.group(1)),
                "gems_ms": float(match.group(2)),
                "speedup": float(match.group(3)),
                "tflops": float(match.group(4)) if match.group(4) else 0.0,
            }
        )
    return rows


def section(markdown: str, heading: str) -> str:
    pattern = SECTION_RE_TEMPLATE.format(heading=re.escape(heading))
    match = re.search(pattern, markdown)
    return match.group(0).rstrip() if match else ""


def replace_section(markdown: str, heading: str, replacement: str) -> str:
    pattern = SECTION_RE_TEMPLATE.format(heading=re.escape(heading))
    replacement = replacement.rstrip()
    if re.search(pattern, markdown):
        return re.sub(pattern, replacement + "\n\n", markdown, count=1).rstrip() + "\n"
    if markdown and not markdown.endswith("\n"):
        markdown += "\n"
    return f"{markdown}\n{replacement}\n"


def parse_body_means(body: str) -> dict[str, float]:
    perf = section(body, "Performance")
    means: dict[str, float] = {}
    for operator, value in MEAN_ROW_RE.findall(perf):
        op = operator.strip()
        if op.lower() in {"dtype", "operator"}:
            continue
        try:
            means[op] = float(value)
        except ValueError:
            pass
    return means


def parse_body_case_count(body: str) -> int | None:
    match = CASE_RE.search(body)
    return int(match.group(1)) if match else None


def parse_optional_float(text: str) -> float:
    text = text.strip().strip("*`")
    if not text or text.lower() in {"not emitted", "n/a", "na", "-", "—"}:
        return 0.0
    return float(text)


def split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_performance_markdown(body: str, fallback_op: str) -> list[dict]:
    """Parse existing PR-body Performance markdown into benchmark rows.

    This is a fallback for older PRs whose raw CI job logs are no longer
    available, but whose body already contains measured CI latency data.
    """
    perf = section(body, "Performance")
    if not perf:
        return []

    rows: list[dict] = []
    current_op = fallback_op
    headers: list[str] = []

    for line in perf.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            current_op = stripped[4:].strip()
            if current_op.endswith(" (in-place)"):
                current_op = current_op[: -len(" (in-place)")]
            headers = []
            continue

        if not stripped.startswith("|"):
            continue
        cells = split_markdown_row(stripped)
        if not cells:
            continue

        lowered = [cell.lower() for cell in cells]
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if "dtype" in lowered[0]:
            headers = lowered
            continue
        if not headers or len(cells) < len(headers):
            continue

        def find_col(*needles: str) -> int | None:
            for i, header in enumerate(headers):
                if all(needle in header for needle in needles):
                    return i
            return None

        dtype_i = find_col("dtype")
        size_i = find_col("size")
        torch_i = find_col("torch", "latency")
        gems_i = find_col("gems", "latency")
        speedup_i = find_col("speedup")
        tflops_i = find_col("tflops")
        required = [dtype_i, size_i, torch_i, gems_i, speedup_i]
        if any(i is None for i in required):
            continue

        try:
            rows.append(
                {
                    "operator": current_op or fallback_op,
                    "dtype": cells[dtype_i].replace("torch.", ""),
                    "shape": cells[size_i],
                    "torch_ms": parse_optional_float(cells[torch_i]),
                    "gems_ms": parse_optional_float(cells[gems_i]),
                    "speedup": parse_optional_float(cells[speedup_i]),
                    "tflops": parse_optional_float(cells[tflops_i]) if tflops_i is not None else 0.0,
                }
            )
        except (ValueError, IndexError):
            continue

    return rows


def should_preserve_multibackend(body: str) -> bool:
    backend = section(body, "Multi-backend Testing")
    return bool(SPECIALIZED_PASS_RE.search(backend))


def infer_operator(pr: dict) -> str:
    title = pr.get("title") or ""
    match = TITLE_OP_RE.search(title)
    if match:
        return match.group(1).strip(" `")

    body = pr.get("body") or ""
    summary = re.search(r"Adds a Triton kernel for `([^`]+)`", body)
    if summary:
        return summary.group(1)

    raise ValueError(f"cannot infer operator for PR #{pr.get('number')}: {title}")


def list_open_prs(repo: str, author: str, limit: int) -> list[dict]:
    data = load_json_from_gh(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--author",
            author,
            "--state",
            "open",
            "--limit",
            str(limit),
            "--json",
            "number,title,url,body,headRefName",
        ]
    )
    return list(data)


def get_pr(repo: str, number: int) -> dict:
    data = load_json_from_gh(
        [
            "pr",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "number,title,url,body,headRefName",
        ]
    )
    return dict(data)


def parse_log_mapping(items: Iterable[str]) -> dict[int, Path]:
    mapping: dict[int, Path] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"--ci-log must be PR=path, got: {item}")
        pr_text, path_text = item.split("=", 1)
        mapping[int(pr_text)] = Path(path_text).expanduser().resolve()
    return mapping


def find_log_in_dir(log_dir: Path, pr: dict, op_name: str) -> Path | None:
    number = str(pr["number"])
    op_id = get_op_id(op_name)
    patterns = [
        f"pr_{number}*.log",
        f"pr-{number}*.log",
        f"{number}.log",
        f"*{number}*.log",
        f"*{op_name}*.log",
        f"*{op_id}*.log",
    ]
    for pattern in patterns:
        matches = sorted(log_dir.glob(pattern))
        if matches:
            return matches[-1]
    return None


def latest_run_for_pr(repo: str, pr: dict, workflow: str | None) -> dict | None:
    args = [
        "run",
        "list",
        "--repo",
        repo,
        "--branch",
        pr["headRefName"],
        "--limit",
        "20",
        "--json",
        "databaseId,displayTitle,workflowName,status,conclusion,url,createdAt",
    ]
    if workflow:
        args.extend(["--workflow", workflow])
    runs = list(load_json_from_gh(args))
    completed = [r for r in runs if r.get("status") == "completed"]
    candidates = completed or runs
    if not workflow:
        unit_test = [r for r in candidates if r.get("workflowName") == "unit-test"]
        if unit_test:
            return unit_test[0]
    return candidates[0] if candidates else None


def fetch_run_log(repo: str, run_id: int) -> str:
    result = run_gh(["run", "view", str(run_id), "--repo", repo, "--log"])
    return result.stdout


def list_run_jobs(repo: str, run_id: int) -> list[dict]:
    data = load_json_from_gh(
        [
            "api",
            f"repos/{repo}/actions/runs/{run_id}/jobs",
            "--jq",
            ".jobs",
        ]
    )
    jobs = []
    if isinstance(data, list):
        # --paginate may produce a single list or nested lists depending on gh.
        for item in data:
            if isinstance(item, list):
                jobs.extend(item)
            elif isinstance(item, dict):
                jobs.append(item)
    return jobs


def fetch_job_log(repo: str, job_id: int) -> str:
    result = run_gh(["api", f"repos/{repo}/actions/jobs/{job_id}/logs"])
    return result.stdout


def job_backend_label(job_name: str) -> str | None:
    lowered = job_name.lower()
    if "python-op" in lowered:
        return "Nvidia CI"
    backend_map = [
        ("backend-iluvatar", "Tianshu / Iluvatar specialization"),
        ("backend-metax", "Muxi / Metax specialization"),
        ("backend-nvidia", "Nvidia backend specialization"),
        ("backend-ascend", "Ascend specialization"),
        ("backend-hygon", "Hygon specialization"),
        ("backend-enflame", "Enflame specialization"),
        ("backend-kunlunxin", "Kunlunxin specialization"),
        ("backend-mthreads", "Mthreads specialization"),
        ("backend-tsingmicro", "Tsingmicro specialization"),
        ("backend-thead", "Thead specialization"),
    ]
    for prefix, label in backend_map:
        if prefix in lowered:
            return label
    return None


def relabel_rows(rows: list[dict], op_name: str, label: str | None) -> list[dict]:
    if not label or label == "Nvidia CI":
        return rows
    relabeled = []
    for row in rows:
        item = dict(row)
        item["operator"] = f"{op_name} ({label})"
        relabeled.append(item)
    return relabeled


def fetch_benchmark_rows_from_run_jobs(
    repo: str,
    run_id: int,
    op_name: str,
) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    sources: list[str] = []
    def job_order(job: dict) -> tuple[int, str]:
        name = (job.get("name") or "").lower()
        if "python-op" in name:
            return (0, name)
        if "backend-" in name:
            return (1, name)
        return (2, name)

    for job in sorted(list_run_jobs(repo, run_id), key=job_order):
        name = job.get("name") or ""
        conclusion = (job.get("conclusion") or "").lower()
        label = job_backend_label(name)
        if not label or conclusion not in {"success", "completed", ""}:
            continue
        try:
            raw = fetch_job_log(repo, int(job["id"]))
        except Exception:
            continue
        job_rows = parse_benchmark_output(raw)
        if not job_rows:
            continue
        rows.extend(relabel_rows(job_rows, op_name, label))
        sources.append(f"{name} job {job['id']}")
    return rows, sources


def rows_for_pr(
    rows: list[dict],
    op_name: str,
    existing_ops: Iterable[str],
    include_all: bool,
) -> tuple[list[dict], str]:
    if include_all:
        return rows, "all CI benchmark rows"

    operators = []
    for row in rows:
        op = row.get("operator")
        if op and op not in operators:
            operators.append(op)

    if len(operators) <= 8:
        return rows, "all rows; log has a small operator set"

    expected = set(existing_ops)
    expected.update({op_name, get_op_id(op_name)})
    selected = [row for row in rows if row.get("operator") in expected]
    return selected, f"filtered rows from {len(operators)} CI operators"


def build_pr_data(op_name: str, rows: list[dict]) -> dict:
    am_speedup = sum(r["speedup"] for r in rows) / len(rows) if rows else 0.0
    return {
        "operator": op_name,
        "nvidia_benchmark": {
            "status": "parsed",
            "command": "",
            "level": "core",
            "rows": rows,
            "case_count": len(rows),
            "arithmetic_mean_speedup": round(am_speedup, 3),
            "operator_means": compute_operator_means(rows, op_name),
        },
        "domestic_gpu": query_domestic_gpu(op_name),
        "warnings": [],
    }


def patch_pr_body(
    current_body: str,
    generated_body: str,
    *,
    preserve_multibackend: bool = False,
) -> str:
    new_body = replace_section(current_body, "Performance", section(generated_body, "Performance"))
    if preserve_multibackend:
        return new_body
    new_body = replace_section(
        new_body,
        "Multi-backend Testing",
        section(generated_body, "Multi-backend Testing"),
    )
    return new_body


def write_body_to_pr(repo: str, number: int, body: str) -> None:
    # Avoid passing a large PR body as a command-line argument.
    with NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
        json.dump({"body": body}, f)
        tmp_name = f.name
    try:
        run_gh(["api", "-X", "PATCH", f"repos/{repo}/pulls/{number}", "--input", tmp_name])
    finally:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass


def format_mean_table(means: dict[str, float]) -> str:
    if not means:
        return "_No previous mean table found._"
    lines = ["| Operator | Mean Speedup |", "|---|---|"]
    for op, value in means.items():
        lines.append(f"| {op} | {value:.3f} |")
    return "\n".join(lines)


def format_after_mean_table(pr_data: dict) -> str:
    means = pr_data["nvidia_benchmark"]["operator_means"]
    if not means:
        return "_No CI benchmark rows parsed._"
    lines = ["| Operator | Cases | Mean Speedup |", "|---|---:|---:|"]
    for item in means:
        lines.append(
            f"| {item['operator']} | {item['case_count']} | {item['speedup']:.3f} |"
        )
    return "\n".join(lines)


def audit_entry(
    pr: dict,
    op_name: str,
    before_body: str,
    after_body: str,
    pr_data: dict,
    source: str,
    row_note: str,
    changed: bool,
) -> str:
    before_means = parse_body_means(before_body)
    before_cases = parse_body_case_count(before_body)
    after_cases = pr_data["nvidia_benchmark"]["case_count"]
    before_perf = section(before_body, "Performance") or "_Missing before Performance section._"
    after_perf = section(after_body, "Performance") or "_Missing after Performance section._"
    status = "UPDATED" if changed else "UNCHANGED"

    return f"""### PR #{pr['number']} - {op_name} - {status}

- URL: {pr.get('url', '')}
- CI source: {source}
- Row selection: {row_note}
- Case count: {before_cases if before_cases is not None else 'N/A'} -> {after_cases}

Before means:

{format_mean_table(before_means)}

After means:

{format_after_mean_table(pr_data)}

<details>
<summary>Before Performance</summary>

{before_perf}

</details>

<details>
<summary>After Performance</summary>

{after_perf}

</details>
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill open PR Performance sections from CI benchmark logs."
    )
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repo, owner/name")
    parser.add_argument("--repo-dir", default=DEFAULT_REPO_DIR, help="Local FlagGems repo for template metadata")
    parser.add_argument("--author", default=DEFAULT_AUTHOR, help="Open PR author when --pr is omitted")
    parser.add_argument("--pr", type=int, action="append", help="PR number to update; repeatable")
    parser.add_argument("--limit", type=int, default=100, help="Open PR list limit")
    parser.add_argument("--device", default="CI", help="CI Nvidia device label for PR body")
    parser.add_argument("--ci-log", action="append", default=[], help="Explicit CI log mapping: PR=path")
    parser.add_argument("--log-dir", help="Directory containing CI logs named by PR number or operator")
    parser.add_argument("--workflow", help="Optional workflow name/id for gh run list")
    parser.add_argument("--include-all-ci-operators", action="store_true", help="Keep every parsed operator in each CI log")
    parser.add_argument(
        "--no-body-fallback",
        action="store_true",
        help="Do not parse the existing PR body when CI logs contain no benchmark rows",
    )
    parser.add_argument(
        "--replace-specialized-multibackend",
        action="store_true",
        help="Replace Multi-backend Testing even when the current PR body has specialized backend rows",
    )
    parser.add_argument("--audit-dir", default=DEFAULT_AUDIT_DIR, help="Directory for timestamped audit markdown")
    parser.add_argument("--max-updates", type=int, default=DEFAULT_MAX_UPDATES, help="Maximum PR bodies to edit in one run")
    parser.add_argument("--dry-run", action="store_true", help="Generate audit only; do not edit PR bodies")
    args = parser.parse_args()

    explicit_logs = parse_log_mapping(args.ci_log)
    if args.pr:
        prs = [get_pr(args.repo, n) for n in args.pr]
    else:
        prs = list_open_prs(args.repo, args.author, args.limit)

    if not prs:
        print("No PRs to process.")
        return 0

    audit_dir = Path(args.audit_dir).expanduser().resolve()
    audit_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_path = audit_dir / f"ci_performance_update_{stamp}.md"

    entries = [
        f"# CI Performance Update {stamp}",
        "",
        f"- Repo: {args.repo}",
        f"- Device label: Nvidia ({normalize_device(args.device)})",
        f"- Max actual updates: {args.max_updates}",
        f"- Dry run: {args.dry_run}",
        "",
    ]

    would_change_count = 0
    edited_count = 0
    skipped_count = 0
    limit_skipped_count = 0

    for pr in prs:
        number = int(pr["number"])
        try:
            op_name = infer_operator(pr)
            body = pr.get("body") or ""

            source = ""
            rows: list[dict] = []
            if number in explicit_logs:
                log_path = explicit_logs[number]
                raw_log = log_path.read_text(encoding="utf-8", errors="replace")
                source = str(log_path)
                rows = parse_benchmark_output(raw_log)
            elif args.log_dir:
                log_path = find_log_in_dir(Path(args.log_dir), pr, op_name)
                if not log_path:
                    raise FileNotFoundError(f"no CI log found in {args.log_dir}")
                raw_log = log_path.read_text(encoding="utf-8", errors="replace")
                source = str(log_path)
                rows = parse_benchmark_output(raw_log)
            else:
                run = latest_run_for_pr(args.repo, pr, args.workflow)
                if not run:
                    raise RuntimeError("no GitHub Actions run found for PR head branch")
                source = run.get("url") or f"run {run['databaseId']}"
                rows, job_sources = fetch_benchmark_rows_from_run_jobs(
                    args.repo,
                    int(run["databaseId"]),
                    op_name,
                )
                if job_sources:
                    source = f"{source}; jobs: {', '.join(job_sources)}"
                if not rows:
                    raw_log = fetch_run_log(args.repo, int(run["databaseId"]))
                    rows = parse_benchmark_output(raw_log)

            if not rows and not args.no_body_fallback:
                previous_source = source
                rows = parse_performance_markdown(body, op_name)
                source = (
                    "current PR body Performance markdown"
                    f" (no benchmark rows parsed from {previous_source})"
                )
            if not rows:
                raise RuntimeError("no benchmark SUCCESS rows parsed from CI log")

            selected_rows, row_note = rows_for_pr(
                rows,
                op_name,
                parse_body_means(body).keys(),
                args.include_all_ci_operators,
            )
            if not selected_rows:
                raise RuntimeError("CI log had benchmark rows, but none matched this PR")

            pr_data = build_pr_data(op_name, selected_rows)
            generated = retag_nvidia_device(
                format_pr_body(op_name, pr_data, args.repo_dir),
                args.device,
            )
            preserve_multibackend = (
                should_preserve_multibackend(body)
                and not args.replace_specialized_multibackend
            )
            new_body = patch_pr_body(
                body,
                generated,
                preserve_multibackend=preserve_multibackend,
            )
            changed = new_body != body

            if changed:
                would_change_count += 1

            if changed and not args.dry_run and edited_count >= args.max_updates:
                limit_skipped_count += 1
                entries.append(
                    f"### PR #{number} - {op_name} - SKIPPED\n\n"
                    f"- Reason: max update limit reached ({args.max_updates})\n"
                )
                print(
                    f"PR #{number} {op_name}: skipped: max update limit reached",
                    file=sys.stderr,
                )
                continue

            if changed and not args.dry_run:
                write_body_to_pr(args.repo, number, new_body)
                edited_count += 1

            entries.append(
                audit_entry(pr, op_name, body, new_body, pr_data, source, row_note, changed)
            )
            print(f"PR #{number} {op_name}: {'updated' if changed else 'unchanged'}")
        except Exception as exc:
            skipped_count += 1
            entries.append(f"### PR #{number} - SKIPPED\n\n- Reason: {exc}\n")
            print(f"PR #{number}: skipped: {exc}", file=sys.stderr)

    audit_path.write_text("\n".join(entries).rstrip() + "\n", encoding="utf-8")
    print(f"Audit written: {audit_path}")
    print(
        f"Would change: {would_change_count}; edited: {edited_count}; "
        f"skipped: {skipped_count}; limit-skipped: {limit_skipped_count}; "
        f"dry-run: {args.dry_run}"
    )
    return 0 if skipped_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
