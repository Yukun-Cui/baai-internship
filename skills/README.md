# Skills

这里存放可直接安装到 Claude/Codex 类 agent 环境中的工作流 skill。

| Skill | 说明 | 入口 |
|------|------|------|
| [flaggems-pr-submit](./flaggems-pr-submit/) | FlagGems 算子 PR 提交 skill，覆盖规范名查询、worktree 代码提取、命名规范化、提交前门禁、本地测试/benchmark、PR 创建和链接回填 | `SKILL.md` / `scripts/submit_operator.py` |
| [flaggems-pr-submit-mthreads](./flaggems-pr-submit-mthreads/) | FlagGems 摩尔线程（Moore Threads/MUSA）特化算子 PR 提交 skill，复用上游测试/benchmark，通常只提交 2 个文件（kernel + `_mthreads/ops/__init__.py`），覆盖 musa 设备验证、fallback、后端专用 logger 命名等门禁 | `SKILL.md` / `scripts/prepare_kernel.sh` |
| [flaggems-pass-opt](./flaggems-pass-opt/) | 用编译器优化 Pass 驱动 FlagGems 算子源码层优化 skill，覆盖选 Pass+算子配对、手工落地等价变换、正确性门禁、orig/opt A/B benchmark、成功样例归档 | `SKILL.md` / `scripts/pass.sh` |

