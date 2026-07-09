# DeepSeek Handoff: {{TASK_TITLE}}

You are the executor. Do not redesign the task. Follow this handoff exactly.

## Read First

1. `request.md`
2. `plan.md`
3. `todo.md`
4. `tracking.md`
5. `artifacts/audit-ledger.md`
6. `../../rules/safety.md`
7. `../../rules/deepseek_executor.md`

## Task

{{TASK_SUMMARY}}

## Steps

1. {{STEP_1}}
2. {{STEP_2}}
3. {{STEP_3}}

## Tracking

- Keep a short live ledger of assigned workers and their status.
- Never exceed the worker limit in this task.
- Record each worker's PR, repo/worktree, and current state before spawning the next one.
- Do not stop after a single batch if actionable queue items remain; keep refilling worker slots until the queue is exhausted.
- If a worker cannot post a reply in the original review thread, it must record the failure and stop that reply attempt; do not substitute a top-level comment.
- Keep `artifacts/audit-ledger.md` as the chronological source of truth.
- After code-changing workers finish, assign a separate CI-check worker/pass. Do not mark pushed fixes final until live CI is checked for the pushed head SHA.
- If live CI fails, requeue the PR for a fix worker and repeat the CI-check pass.

## Review Reply And Attribution Rules

- For each handled review comment, write a short reply draft for the exact review thread.
- Do not post the reply yourself unless the controller explicitly asks.
- Do not mention AI tools, agents, model names, or internal workflow details in reply drafts.
- Do not add any `Co-authored-by`, `Co-authored by`, `Generated-by`, or AI attribution trailer to commit messages, PR comments, patches, file headers, or generated documentation.
- 禁止在 commit message、PR 回复、patch、文件头、文档中添加 Co-authored-by、Co-authored by、Generated-by 或任何 AI 署名/协作者署名。

## Required Logging

- Update `execution.md` after each major step.
- Update `tracking.md` when each worker starts or finishes.
- Append `artifacts/audit-ledger.md` for assignments, pushes, replies, CI checks, failures, requeues, and blockers.

## Validation

Run:

```bash
{{VALIDATION_COMMANDS}}
```

## Stop And Report BLOCKED If

- Any required context is missing.
- A command needs destructive permissions.
- The plan conflicts with the actual code.
- Validation cannot be run.
- The queue cannot safely continue and no further worker can be assigned.
- The CI-check queue cannot be completed or blocked with evidence.
