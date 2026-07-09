# Plan: {{TASK_TITLE}}

## Goal

{{GOAL}}

## Context

{{CONTEXT}}

## Files To Read First

- {{FILE_OR_DIR}}

## Execution Steps

1. {{STEP_1}}
2. {{STEP_2}}
3. {{STEP_3}}

## Tracking

- Controller:
- Worker limit:
- CI-check worker limit:
- Active workers:
- Completed workers:
- Blocked workers:
- Single audit source: `artifacts/audit-ledger.md`

## Commands Allowed

```bash
{{COMMANDS}}
```

## Validation

```bash
{{VALIDATION_COMMANDS}}
```

## Acceptance Criteria

- {{CRITERION_1}}
- {{CRITERION_2}}
- Controller keeps scheduling workers until the actionable queue is exhausted, then hands off to Codex review.
- Code-changing work is not final until a separate CI-check pass records live CI status for the pushed head SHA.
- Every processed PR has a per-PR artifact and a chronological audit-ledger entry.
- No commit, PR reply, file header, patch, or generated document contains Co-authored-by, Co-authored by, Generated-by, AI attribution, or coauthor trailers.

## Stop Conditions

- Stop if required files are missing.
- Stop if tests fail twice for unclear reasons.
- Stop before destructive commands or force push.
- Stop if the worker limit is exceeded.
- Stop only when there are no actionable queue items left and no active workers remain, unless a stronger blocker in this list fires first.
- Stop only after the CI-check queue is closed or explicitly blocked with evidence.

## Notes For Executor

{{NOTES}}
