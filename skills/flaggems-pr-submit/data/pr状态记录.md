# PR 提交状态记录

`submit_operator.py` 会把每个算子的提交事件（FAIL / PR_CREATED / LOW_SPEEDUP 等）追加到本文件。
新环境从这份空表开始；历史运行记录属于工作数据，不随仓库提交。

| 时间 | 算子 | 事件 | 说明 |
|------|------|------|------|
| 2026-08-05 02:41 | replication_pad1d_backward | FAIL | GH_TOKEN is not set; export GH_TOKEN or pass --token before creating a PR |
| 2026-08-05 02:41 | replication_pad1d_backward | FAIL | 只找到 3 个文件（需要 6 个）: ['src/flag_gems/ops/__init__.py', 'src/flag_gems/__init__.py', 'conf/operators.ya |
| 2026-08-05 02:42 | replication_pad1d_backward | FAIL | 只找到 3 个文件（需要 6 个）: ['src/flag_gems/ops/__init__.py', 'src/flag_gems/__init__.py', 'conf/operators.ya |
| 2026-08-05 02:43 | replication_pad1d_backward | FAIL | 只找到 3 个文件（需要 6 个）: ['src/flag_gems/ops/__init__.py', 'src/flag_gems/__init__.py', 'conf/operators.ya |
| 2026-08-05 02:44 | replication_pad1d_backward | FAIL | 命令失败 (exit 1): python /root/baai-internship/skills/flaggems-pr-submit/scripts/check_operator.py repl |
| 2026-08-05 02:52 | replication_pad1d_backward | FAIL | GH_TOKEN is not set; export GH_TOKEN or pass --token before creating a PR |
| 2026-08-05 02:53 | replication_pad1d_backward | FAIL | 只找到 3 个文件（需要 6 个）: ['src/flag_gems/ops/__init__.py', 'src/flag_gems/__init__.py', 'conf/operators.ya |
| 2026-08-05 02:54 | replication_pad1d_backward | FAIL | 命令失败 (exit 1): python /root/baai-internship/skills/flaggems-pr-submit/scripts/check_operator.py repl |
| 2026-08-05 02:54 | replication_pad1d_backward | FAIL | 命令失败 (exit 1): python /root/baai-internship/skills/flaggems-pr-submit/scripts/check_operator.py repl |
| 2026-08-05 03:20 | replication_pad1d_backward | FAIL | 只找到 3 个文件（需要 6 个）: ['src/flag_gems/ops/__init__.py', 'src/flag_gems/__init__.py', 'conf/operators.ya |
| 2026-08-05 03:21 | replication_pad1d_backward | FAIL | 命令失败 (exit 1): python /root/baai-internship/skills/flaggems-pr-submit/scripts/check_operator.py repl |
