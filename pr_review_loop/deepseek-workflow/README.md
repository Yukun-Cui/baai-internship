# DeepSeek Workflow（打包副本）

> 这是 `pr_review_loop` 自包含打包时携带的精简副本，仅含 `config.yaml`。
> 完整的规则、脚本和模板见仓库顶层的
> [`deepseek-workflow/`](../../deepseek-workflow/)，创建任务也在那边运行：
>
> ```bash
> python3 deepseek-workflow/scripts/new_task.py "任务标题" "原始需求"
> ```

核心分工：**Codex 规划 → Claude Code 执行 → Codex 复核**。执行者只读 `handoff.md` 干活、把过程写入 `execution.md`，遇到 BLOCKED 立即停止。
