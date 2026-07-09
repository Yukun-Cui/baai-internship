#!/usr/bin/env python3
"""Audit open PR performance description status.

This is the confirmation step before batch editing PR bodies. It reads open PRs,
detects descriptions that still need CI-performance cleanup, and writes one
timestamped markdown list. No PR is modified by this script.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

from update_pr_performance_from_ci import (
    DEFAULT_AUTHOR,
    DEFAULT_REPO,
    infer_operator,
    get_pr,
    list_open_prs,
    parse_body_case_count,
    parse_body_means,
    parse_performance_markdown,
    section,
)


DEFAULT_REPORT_DIR = "/root/baai-internship/ci_performance_update/reports"
DEFAULT_SPEEDUP_THRESHOLD = 0.8
H20_RE = re.compile(r"\bNVIDIA H20\b|Nvidia \(H20\)", re.IGNORECASE)
CI_RE = re.compile(r"\bNVIDIA CI\b|Nvidia \(CI\)|python-op CI", re.IGNORECASE)
NON_STANDARD_RE = re.compile(r"not emitted|TFLOPS is recorded|Size \([^)]*\)", re.IGNORECASE)
SPECIALIZATION_RE = re.compile(r"\(([^)]*specialization)\)", re.IGNORECASE)
SPECIALIZED_PASS_RE = re.compile(
    r"^\|\s*(?:Tianshu / Iluvatar|Muxi / Metax|[^|]*backend-[^|]*|[^|]*specialization[^|]*)\s*\|\s*PASS\s*\|",
    re.IGNORECASE | re.MULTILINE,
)


def h20_status(body: str) -> tuple[bool, str]:
    perf = section(body, "Performance")
    multi_backend = section(body, "Multi-backend Testing")
    perf_has_h20 = bool(H20_RE.search(perf))
    backend_has_h20 = bool(H20_RE.search(multi_backend))
    if perf_has_h20 and backend_has_h20:
        return True, "Performance and Multi-backend Testing"
    if perf_has_h20:
        return True, "Performance"
    if backend_has_h20:
        return True, "Multi-backend Testing"
    return False, ""


def mean_summary(means: dict[str, float]) -> str:
    if not means:
        return "N/A"
    return " / ".join(f"{op}: {value:.3f}" for op, value in means.items())


def audit_pr(pr: dict, threshold: float, update_policy: str = "h20-low-speedup") -> dict:
    body = pr.get("body") or ""
    op_name = infer_operator(pr)
    perf = section(body, "Performance")
    backend = section(body, "Multi-backend Testing")
    means = parse_body_means(body)
    rows = parse_performance_markdown(body, op_name)
    is_h20, h20_source = h20_status(body)

    format_reasons = []
    if not perf:
        format_reasons.append("missing Performance section")
    if not backend:
        format_reasons.append("missing Multi-backend Testing section")
    if is_h20:
        format_reasons.append(f"H20 label in {h20_source}")
    if perf and not CI_RE.search(perf):
        format_reasons.append("Performance is not labeled as CI")
    if NON_STANDARD_RE.search(perf):
        format_reasons.append("non-standard Performance table text")

    low_speedups = {op: value for op, value in means.items() if value < threshold}

    backend_specialized = bool(SPECIALIZED_PASS_RE.search(backend))
    perf_specialized = bool(SPECIALIZATION_RE.search(perf))
    if backend_specialized and not perf_specialized:
        format_reasons.append("specialized backend summary exists but Performance lacks specialization detail sections")

    if update_policy == "h20-low-speedup":
        needs_update = is_h20 and bool(low_speedups)
        reasons = []
        if needs_update:
            reasons.append(
                f"H20 mean speedup below {threshold:.3f}: {mean_summary(low_speedups)}"
            )
            reasons.extend(format_reasons)
    else:
        needs_update = bool(format_reasons)
        reasons = format_reasons

    status = "NEEDS_UPDATE" if needs_update else "OK"
    attention = bool(low_speedups)

    return {
        "number": int(pr["number"]),
        "url": pr.get("url", ""),
        "title": pr.get("title", ""),
        "operator": op_name,
        "status": status,
        "attention": attention,
        "reasons": reasons,
        "means": means,
        "low_speedups": low_speedups,
        "case_count": parse_body_case_count(body) or len(rows) or "N/A",
        "performance": perf or "_Missing Performance section._",
    }


def details_block(item: dict) -> str:
    reason_text = "; ".join(item["reasons"]) if item["reasons"] else "Already CI-formatted"
    attention_text = (
        mean_summary(item["low_speedups"]) if item["low_speedups"] else "None"
    )
    return f"""### PR #{item['number']} - {item['operator']}

- URL: {item['url']}
- Status: {item['status']}
- Reasons: {reason_text}
- Cases: {item['case_count']}
- Current mean speedup: {mean_summary(item['means'])}
- Low-speedup attention: {attention_text}

<details>
<summary>Current Performance</summary>

{item['performance']}

</details>
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write a confirmation list of open PRs that need CI performance description updates."
    )
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repo, owner/name")
    parser.add_argument("--author", default=DEFAULT_AUTHOR, help="Open PR author when --pr is omitted")
    parser.add_argument("--pr", type=int, action="append", help="PR number to audit; repeatable")
    parser.add_argument("--limit", type=int, default=100, help="Open PR list limit")
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR, help="Directory for timestamped markdown reports")
    parser.add_argument("--threshold", type=float, default=DEFAULT_SPEEDUP_THRESHOLD, help="Mean speedup threshold for attention items")
    parser.add_argument(
        "--update-policy",
        choices=["h20-low-speedup", "format-cleanup"],
        default="h20-low-speedup",
        help="Policy for the Needs Description Update section",
    )
    parser.add_argument("--include-ok", action="store_true", help="Also list PRs that do not need description updates")
    parser.add_argument("--include-non-h20", action="store_true", help="Deprecated alias for --include-ok")
    args = parser.parse_args()

    if args.pr:
        prs = [get_pr(args.repo, n) for n in args.pr]
    else:
        prs = list_open_prs(args.repo, args.author, args.limit)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    report_dir = Path(args.report_dir).expanduser().resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"open_pr_ci_description_audit_{stamp}.md"

    needs_update = []
    ok_items = []
    attention_items = []
    skipped_rows = []

    for pr in prs:
        number = int(pr["number"])
        try:
            item = audit_pr(pr, args.threshold, args.update_policy)
            if item["status"] == "NEEDS_UPDATE":
                needs_update.append(item)
            else:
                ok_items.append(item)
            if item["attention"]:
                attention_items.append(item)
        except Exception as exc:
            skipped_rows.append(f"| #{number} | {pr.get('url', '')} | {exc} |")

    lines = [
        f"# Open PR CI Performance Description Audit {stamp}",
        "",
        f"- Repo: {args.repo}",
        f"- Author: {args.author}",
        f"- Open PRs checked: {len(prs)}",
        f"- Needs description update: {len(needs_update)}",
        f"- Update policy: {args.update_policy}",
        f"- Low-speedup attention threshold: {args.threshold:.3f}",
        f"- Low-speedup attention PRs: {len(attention_items)}",
        "",
        "## Needs Description Update",
        "",
    ]
    if needs_update:
        for item in needs_update:
            lines.append(details_block(item))
    else:
        lines.append("_No open PR body currently needs a CI performance description update._")

    lines.extend(["", "## Low-Speedup Attention", ""])
    if attention_items:
        lines.extend(
            [
                "| PR | Operator | Low Mean Speedups | Status | URL |",
                "|---|---|---|---|---|",
            ]
        )
        for item in attention_items:
            lines.append(
                f"| #{item['number']} | {item['operator']} | "
                f"{mean_summary(item['low_speedups'])} | {item['status']} | {item['url']} |"
            )
    else:
        lines.append("_No mean speedup is below the threshold._")

    if args.include_ok or args.include_non_h20:
        lines.extend(["", "## Already OK", ""])
        if ok_items:
            lines.extend(["| PR | Operator | Means | URL |", "|---|---|---|---|"])
            for item in ok_items:
                lines.append(
                    f"| #{item['number']} | {item['operator']} | "
                    f"{mean_summary(item['means'])} | {item['url']} |"
                )
        else:
            lines.append("_No OK PRs in this scan._")

    if skipped_rows:
        lines.extend(["", "## Skipped", "", "| PR | URL | Reason |", "|---|---|---|"])
        lines.extend(skipped_rows)

    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Report written: {report_path}")
    print(
        f"Needs update: {len(needs_update)}; "
        f"low-speedup attention: {len(attention_items)}; skipped: {len(skipped_rows)}"
    )
    return 0 if not skipped_rows else 1


if __name__ == "__main__":
    sys.exit(main())
