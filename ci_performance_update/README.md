# CI Performance Update

Standalone helper scripts for replacing open PR performance data with CI
benchmark results. These scripts are not part of the PR-submit skill workflow.

## 1. Audit Open PRs

Write a timestamped confirmation list before each batch. The audit identifies:

- PRs whose current H20 arithmetic mean speedup is below the threshold and
  therefore need CI performance cleanup
- PRs that are already formatted correctly
- PRs with any arithmetic mean speedup below the attention threshold

```bash
python /root/baai-internship/ci_performance_update/audit_open_pr_h20_performance.py
```

Output goes to:

```text
/root/baai-internship/ci_performance_update/reports/open_pr_ci_description_audit_<timestamp>.md
```

Use `--include-ok` when you also want the report to list PRs that are already
formatted correctly:

```bash
python /root/baai-internship/ci_performance_update/audit_open_pr_h20_performance.py --include-ok
```

By default, `Needs Description Update` only includes PRs that still have H20
data and at least one arithmetic mean speedup below `0.8`. That section is the
input list for the next update batch. The `Low-Speedup Attention` section is
separate: those PRs may already have correct descriptions, but need later
performance follow-up.

To audit all formatting issues regardless of speedup, use:

```bash
python /root/baai-internship/ci_performance_update/audit_open_pr_h20_performance.py \
  --update-policy format-cleanup
```

## 2. Update From CI Logs

Dry run first:

```bash
python /root/baai-internship/ci_performance_update/update_pr_performance_from_ci.py \
  --dry-run \
  --log-dir /path/to/ci_logs
```

Apply updates after confirmation. Actual edits are capped at 4 PRs per run by
default:

```bash
python /root/baai-internship/ci_performance_update/update_pr_performance_from_ci.py \
  --log-dir /path/to/ci_logs
```

For explicit PR/log mapping:

```bash
python /root/baai-internship/ci_performance_update/update_pr_performance_from_ci.py \
  --ci-log 1234=/path/to/pr_1234.log \
  --ci-log 1235=/path/to/pr_1235.log
```

If an older PR no longer has downloadable CI benchmark logs, the update script
falls back to parsing the existing PR-body `Performance` table and rewrites that
section into the standard template. When the existing `Multi-backend Testing`
section contains specialization rows such as `Tianshu / Iluvatar` or
`Muxi / Metax`, it is preserved by default.

Each run writes one before/after audit file to:

```text
/root/baai-internship/ci_performance_update/reports/ci_performance_update_<timestamp>.md
```
