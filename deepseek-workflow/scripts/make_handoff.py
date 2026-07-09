#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if len(sys.argv) != 2:
        print('Usage: make_handoff.py deepseek-workflow/tasks/<task-id>')
        return 2

    task_dir = Path(sys.argv[1]).resolve()
    plan = task_dir / 'plan.md'
    handoff = task_dir / 'handoff.md'
    request = task_dir / 'request.md'
    execution = task_dir / 'execution.md'
    if not plan.exists():
        print(f'Missing plan: {plan}')
        return 1

    content = (
        '# DeepSeek Handoff\n\n'
        'You are the executor. Do not redesign the task. Follow the plan exactly.\n\n'
        'Read these files first:\n\n'
        f'- {request}\n'
        f'- {plan}\n'
        f'- {ROOT / "rules" / "safety.md"}\n'
        f'- {ROOT / "rules" / "deepseek_executor.md"}\n\n'
        'Write progress and final results to:\n\n'
        f'- {execution}\n\n'
        '## Plan\n\n'
        + plan.read_text(encoding='utf-8')
    )
    handoff.write_text(content, encoding='utf-8')
    print(handoff)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
