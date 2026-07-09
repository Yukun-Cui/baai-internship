#!/usr/bin/env python3
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / 'tasks'
TEMPLATES = ROOT / 'templates'


def slugify(title: str) -> str:
    slug = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]+', '-', title.strip()).strip('-')
    return slug[:60] or 'task'


def main() -> int:
    if len(sys.argv) < 3:
        print('Usage: new_task.py "任务标题" "原始需求"')
        return 2

    title = sys.argv[1].strip()
    request = sys.argv[2].strip()
    task_id = f'{date.today().isoformat()}-{slugify(title)}'
    task_dir = TASKS / task_id
    suffix = 2
    while task_dir.exists():
        task_dir = TASKS / f'{task_id}-{suffix}'
        suffix += 1

    (task_dir / 'artifacts' / 'prs').mkdir(parents=True, exist_ok=False)
    (task_dir / 'request.md').write_text(f'# Request: {title}\n\n{request}\n', encoding='utf-8')

    replacements = {
        '{{TASK_TITLE}}': title,
        '{{GOAL}}': 'TODO: Codex fill this in.',
        '{{CONTEXT}}': 'TODO: Codex fill this in.',
        '{{FILE_OR_DIR}}': 'TODO',
        '{{STEP_1}}': 'TODO',
        '{{STEP_2}}': 'TODO',
        '{{STEP_3}}': 'TODO',
        '{{COMMANDS}}': '# TODO',
        '{{VALIDATION_COMMANDS}}': '# TODO',
        '{{CRITERION_1}}': 'TODO',
        '{{CRITERION_2}}': 'TODO',
        '{{NOTES}}': 'TODO',
        '{{TASK_SUMMARY}}': request,
    }

    for template_name, output_name in [
        ('plan.template.md', 'plan.md'),
        ('handoff.template.md', 'handoff.md'),
        ('execution.template.md', 'execution.md'),
        ('review.template.md', 'review.md'),
    ]:
        content = (TEMPLATES / template_name).read_text(encoding='utf-8')
        for old, new in replacements.items():
            content = content.replace(old, new)
        (task_dir / output_name).write_text(content, encoding='utf-8')

    # Tracking-first workflows usually need these ledgers even if Codex later rewrites them.
    (task_dir / 'todo.md').write_text(
        '# TODO\n\n'
        'Status values: `pending`, `in_progress`, `done`, `blocked`.\n\n'
        '## Queue\n\n'
        '| Item | Status | Owner | Notes |\n'
        '|---|---|---|---|\n'
        '| TODO | pending | controller | fill this in |\n',
        encoding='utf-8',
    )
    (task_dir / 'tracking.md').write_text(
        '# Tracking\n\n'
        'Controller: `controller`\n\n'
        'Worker limit: `2`\n\n'
        '## Active Workers\n\n'
        '| Worker | Item | Status | Notes |\n'
        '|---|---|---|---|\n'
        '| - | - | idle | none yet |\n\n'
        '## Completed Workers\n\n'
        '| Worker | Item | Result | Notes |\n'
        '|---|---|---|---|\n'
        '| - | - | - | none yet |\n\n'
        '## Blocked Workers\n\n'
        '| Worker | Item | Blocker | Queue can continue? |\n'
        '|---|---|---|---|\n'
        '| - | - | - | - |\n\n'
        '## Run Rule\n\n'
        '- Controller keeps assigning workers until the actionable queue is exhausted.\n'
        '- Do not stop after one batch if pending actionable items remain.\n'
        '- Stop only when no actionable queue item remains and no active worker remains, or when a blocking condition makes further progress unsafe.\n',
        encoding='utf-8',
    )
    (task_dir / 'artifacts' / 'README.md').write_text(
        '# Artifacts\n\n'
        '- Put compressed summaries, per-worker outputs, and tracking snapshots here.\n'
        '- Put per-PR artifacts under `prs/`.\n'
        '- Keep `audit-ledger.md` as the chronological source of truth.\n',
        encoding='utf-8',
    )
    (task_dir / 'artifacts' / 'audit-ledger.md').write_text(
        '# Audit Ledger\n\n'
        'This file is the chronological source of truth for controller and worker actions.\n\n'
        '| UTC Time | Actor | Item | Action | Evidence / Result | Next Status |\n'
        '|---|---|---|---|---|---|\n'
        '| TODO | controller | - | task created | fill this in | pending |\n',
        encoding='utf-8',
    )

    print(task_dir)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
