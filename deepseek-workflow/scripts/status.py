#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / 'tasks'

if not TASKS.exists():
    print('No tasks yet.')
    raise SystemExit(0)

tasks = [p for p in sorted(TASKS.iterdir()) if p.is_dir()]
if not tasks:
    print('No tasks yet.')
    raise SystemExit(0)

for task in tasks:
    execution = task / 'execution.md'
    status = 'UNKNOWN'
    if execution.exists():
        for line in execution.read_text(encoding='utf-8').splitlines():
            if line.startswith('Status:'):
                status = line.split(':', 1)[1].strip()
                break
    print(f'{task.name}: {status}')
