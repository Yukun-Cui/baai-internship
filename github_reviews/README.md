# GitHub Reviews

用于批量抓取指定作者在 GitHub PR 中收到的 review、line comment 和 PR comment，并生成 Markdown 报告。常见用法是先用它收集未回复 review，再交给 `deepseek-workflow` 规划修复任务。

## 前置条件

- 安装 GitHub CLI：`gh`
- 已登录：`gh auth login`，或设置 `GH_TOKEN`
- token 需要能读取目标仓库的 PR / review / comment

## 快速使用

```bash
./github_reviews/quick_check.sh
```

默认检查最近 7 天未回复的外部 actionable review/comment。

指定天数：

```bash
./github_reviews/quick_check.sh 3
```

指定仓库、作者和日期：

```bash
./github_reviews/fetch_reviews.sh \
  --repo flagos-ai/FlagGems \
  --author Yukun-Cui \
  --date today \
  --unreplied
```

输出默认写到 `github_reviews/results/reviews_<timestamp>.md`。`results/` 是运行产物，不提交。

## 常用参数

| 参数 | 说明 |
|---|---|
| `--repo owner/name` | 目标仓库，默认 `flagos-ai/FlagGems` |
| `--author user` | PR 作者，默认 `Yukun-Cui` |
| `--days N` | 只统计最近 N 天 |
| `--since YYYY-MM-DD` | 只统计指定日期之后 |
| `--date today\|YYYY-MM-DD` | 只统计某一天 |
| `--state open\|closed\|all` | PR 状态过滤 |
| `--open` | `--state open` 快捷方式 |
| `--unreplied` | 只输出未回复的 actionable 外部评论 |
| `--output path.md` | 指定输出文件 |

## 和 workflow 搭配

1. 运行 `github_reviews/fetch_reviews.sh --unreplied` 生成报告。
2. Codex 根据报告创建 `deepseek-workflow/tasks/<task-id>/`。
3. Claude Code / DeepSeek 按 `handoff.md` 修复和记录。
4. Codex 审查 `execution.md`、diff、测试和 CI 状态。
