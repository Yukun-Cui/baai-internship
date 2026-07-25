# BAAI 实习专用仓库

BAAI 实习期间沉淀的自动化脚本、Agent workflow、PR review 处理工具和可复用模板。仓库目标是保留“下一次还能直接复用”的东西：脚本、配置示例、prompt、规则、模板和 README；真实任务记录、review 报告、CI 日志、token、临时输出不应提交。

## 推荐工作流

处理一批 GitHub review 时，常用链路是：

```text
github_reviews 抓取未回复 review
  -> Codex 使用 deepseek-workflow 规划任务
  -> Claude Code / DeepSeek 按 handoff 执行
  -> Codex 审查 diff、执行记录和 CI
  -> 必要时进入 pr_review_loop 自动闭环
```

## 工具目录

| 目录 | 说明 | 入口 |
|------|------|------|
| [deepseek-workflow](./deepseek-workflow/) | Codex 规划、Claude Code + DeepSeek 执行、Codex 复核的任务模板体系 | `python3 ./deepseek-workflow/scripts/new_task.py "标题" "需求"` |
| [github_reviews](./github_reviews/) | GitHub PR Review 抓取，批量生成未回复 review/comment 报告 | `./github_reviews/quick_check.sh` |
| [pr_review_loop](./pr_review_loop/) | PR Review 自动修复闭环，抓取 review → 修复 → 多层 Gate → Push → CI → 回复 | `python3 ./pr_review_loop/run_once.py --dry-run` |
| [batch_pr_audit](./batch_pr_audit/) | FlagGems PR 批量审计，确定性规则 + AI Agent 两阶段并行审计 | `python3 ./batch_pr_audit/batch_pr_audit.py --no-agent --prs "..."` |
| [auto_gen](./auto_gen/) | FlagGems 算子自动生成工具，支持多 GPU 并行与多后端 | `python3 ./auto_gen/orchestrator.py` |
| [triton_check](./triton_check/) | Triton 算子合规性检查，审查实现是否使用真正的 Triton kernel | `./triton_check/run.sh` |
| [batch_pr_submit](./batch_pr_submit/) | FlagGems 算子批量提 PR，并行 worktree 隔离 | `./batch_pr_submit/batch_submit.sh` |
| [ci_performance_update](./ci_performance_update/) | 从 CI 提取性能数据并更新 PR 描述，审计 H20 性能 | `python3 ./ci_performance_update/update_pr_performance_from_ci.py` |
| [anti_hack](./anti_hack/) | FlagGems 反作弊检查，检测 bypass dual-execution 模式 | 参考模块，见 `./anti_hack/README.md` |
| [proxy](./proxy/) | HTTP/1.1 流式反向代理，解决中转 API HTTP/2 流式断连问题 | `python3 ./proxy/proxy.py` |
| [skills](./skills/) | Agent skills 集合：FlagGems 算子 PR 提交流程（NVIDIA 通用 + 摩尔线程特化）、编译器 Pass 驱动的算子源码层优化流程 | `./skills/flaggems-pr-submit/SKILL.md`、`./skills/flaggems-pr-submit-mthreads/SKILL.md`、`./skills/flaggems-pass-opt/SKILL.md` |

## 快速开始

抓取最近 7 天未回复 review：

```bash
./github_reviews/quick_check.sh
```

用抓取结果创建一个 DeepSeek 执行任务：

```bash
python3 ./deepseek-workflow/scripts/new_task.py \
  "fix unreplied reviews" \
  "根据 github_reviews/results/<report>.md 处理未回复 review"
```

然后由 Codex 补全 `deepseek-workflow/tasks/<task-id>/plan.md` 和 `handoff.md`，执行者只按 handoff 做事并更新 `execution.md`。

## 提交规则

可以提交：

- 可复用脚本、prompt、规则、模板和 README
- 小型测试桩和不含真实工作数据的样例

不要提交：

- `deepseek-workflow/tasks/`
- `github_reviews/results/`
- `pr_review_loop/records/`
- CI 日志、真实 review 报告、实际 PR 修复记录
- `.env`、token、私钥、代理密码
- `__pycache__/`、临时输出、压缩包和大文件

每个工具可独立使用，细节见对应目录下的 README。
