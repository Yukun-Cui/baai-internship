# Execution: {{TASK_TITLE}}

Status: TODO

## Tracking

- Controller:
- Worker limit:
- Active workers:
- Completed workers:
- Blocked workers:
- CI-check queue:
- Audit ledger:

## Steps Completed

- None yet.
- Queue not started yet.

## Files Changed

- None yet.

## Commands Run

- None yet.

## Validation

- Not run yet.

## CI Gate

- Not started yet.
- Code-changing PRs must not be marked final until live CI is checked for the pushed head SHA.

## Notes / Risks

- None yet.
- Default controller behavior: continue assigning workers until the actionable queue is exhausted, then stop for Codex review.
- Thread replies are required for line comments; top-level comments do not count as thread replies.
- Default closeout behavior: run a separate CI-check pass after fixes, requeue failed PRs, and only then hand off to Codex review.
- No Co-authored-by, Co-authored by, Generated-by, AI attribution, or coauthor trailers are allowed anywhere.
