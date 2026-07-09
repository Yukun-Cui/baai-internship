# DeepSeek Workflow

这是一套面向批量 PR / review 修复的轻量工作流模板，核心分工是：

- **Codex**：拆解需求、写计划、做最终审查。
- **Claude Code + DeepSeek**：按 handoff 执行具体工作，记录过程。
- **Codex Review**：检查 diff、验证结果、执行记录和遗留风险。

仓库只保留可复用模板、规则和脚本；实际任务目录 `tasks/`、临时日志和运行产物不纳入版本管理。

## 目录

```text
deepseek-workflow/
├── config.yaml
├── rules/
│   ├── codex_planner.md
│   ├── coding.md
│   ├── deepseek_executor.md
│   └── safety.md
├── scripts/
│   ├── new_task.py
│   ├── make_handoff.py
│   └── status.py
└── templates/
    ├── plan.template.md
    ├── handoff.template.md
    ├── execution.template.md
    └── review.template.md
```

## 标准流程

1. 用户提出任务。
2. Codex 使用 `scripts/new_task.py` 创建任务骨架，补全 `plan.md` 和 `handoff.md`。
3. Claude Code / DeepSeek 只读取 `handoff.md` 执行，不重新设计目标。
4. 执行者把过程、改动、命令和验证结果写入 `execution.md`。
5. Codex 读取 diff、测试结果、`execution.md`，写 `review.md`。
6. 若复核不通过，Codex 继续写 follow-up，执行者按新 handoff 修复。

## 创建任务

在仓库根目录运行：

```bash
python3 deepseek-workflow/scripts/new_task.py "任务标题" "原始需求"
```

脚本会创建：

```text
deepseek-workflow/tasks/<date>-<slug>/
├── request.md
├── plan.md
├── handoff.md
├── execution.md
├── review.md
├── todo.md
├── tracking.md
└── artifacts/
    ├── README.md          # artifacts 目录说明
    ├── audit-ledger.md    # 审计台账
    └── prs/               # 涉及 PR 的产物存放
```

## 交给执行者

在 Claude Code 中给执行者：

```text
请严格按照 deepseek-workflow/tasks/<task-id>/handoff.md 执行。
执行过程写入 execution.md。
遇到 BLOCKED 条件立即停止，不要猜。
```

如果手动更新了 `plan.md` 后需要重建 handoff：

```bash
python3 deepseek-workflow/scripts/make_handoff.py deepseek-workflow/tasks/<task-id>
```

查看任务状态：

```bash
python3 deepseek-workflow/scripts/status.py
```

## 不提交的内容

- `deepseek-workflow/tasks/`
- `deepseek-workflow/tmp/`
- `deepseek-workflow/**/__pycache__/`
- review 报告、CI 日志、真实 PR 处理记录等运行产物
