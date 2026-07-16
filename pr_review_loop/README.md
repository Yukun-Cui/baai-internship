# PR Review Auto-Fix Loop

PR Review 评论自动修复闭环系统。从 GitHub 抓取 review 报告 → 解析未回复评论 → 确定性 triage → AI Agent 修复 → 本地验证 → Claude Review Gate → Codex Audit Gate → Push → CI 等待 → 自动回复，形成完整闭环。

## 流水线

```
fetch_reviews.py (抓取未回复 review)
  → 解析为 ReviewTask 列表 (parse_report)
  → 确定性 triage (must_fix / should_reply / ignore / need_human)
  → 按 PR 分组为 fixer shards
  → Fixer Agent 修改 (Claude/DeepSeek)
  → 本地验证 (validate_changed_files.py)
  → Claude Review Gate (独立只读审查)
  → Codex Audit Gate (最终审计)
  → Commit & Push
  → 等待 CI (CI 失败自动生成 fix 任务)
  → 自动回复 GitHub review comments
```

## 目录结构

```
pr_review_loop/
├── run_once.py                  # 主编排器
├── config.yaml                  # 配置文件（无密钥，token 走环境变量）
├── .env                         # 环境变量（真实 token，不提交）
├── tools/
│   ├── claude_fixer.py          # Fixer Agent 包装器
│   ├── claude_review.py         # Claude 只读审查
│   ├── codex_audit.py           # Codex/GPT 审计
│   ├── push_approved_prs.py     # 推送已批准变更
│   ├── commit_approved_prs.py   # 提交已批准变更
│   ├── prepare_pr_worktrees.py  # 预创建 worktrees
│   ├── validate_changed_files.py # 本地验证
│   └── requeue_needs_human.py   # 人工任务重入队
├── prompts/
│   ├── triage.md                # Triage 分类 prompt
│   ├── fixer.md                 # Fixer agent prompt
│   └── audit.md                 # Codex/GPT 审计 prompt（渲染为 codex_audit_prompt.md）
├── test_fixtures/               # 测试桩 (冒烟测试用)
├── github_reviews/              # Review 抓取脚本
└── deepseek-workflow/           # Workflow 配置
```

## 快速开始

### Dry Run (仅分析不执行)

```bash
python3 run_once.py --dry-run --limit 5
```

### 抓取新 review

```bash
GITHUB_TOKEN="$TOKEN" python3 run_once.py --fetch --days 3 --limit 10
```

> `GITHUB_TOKEN` 应由环境变量或 `gh auth login` 提供，禁止写入配置文件。

### 完整闭环冒烟测试

```bash
python3 run_once.py \
  --no-dry-run \
  --limit 3 \
  --execute-fixers \
  --fixer-command 'python3 test_fixtures/stub_fixer.py {run_dir} {shard_dir}' \
  --execute-claude-review \
  --claude-review-command 'python3 test_fixtures/stub_claude_review.py {task_dir}' \
  --execute-audit \
  --audit-command 'python3 test_fixtures/stub_audit.py {task_dir}' \
  --fixer-parallelism 2
```

### 恢复中断的运行

```bash
python3 run_once.py --resume ./records/YYYYMMDD_HHMMSS --no-dry-run ...
```

## 状态机

```
pending → fixer 执行 → fixed/needs_revision (循环 max_fix_rounds 轮)
fixed → local_validation → validated/revision
validated → claude_review → reviewed/revision
reviewed → codex_audit → local_approved/revision
local_approved → commit → push → pushed
pushed → wait_ci → ci_passed/done
                  ↘ ci_failed → ci-fix-* 任务 (下一轮修复)
                              ↘ needs_human (超过 max_fix_rounds)
done → auto_reply
```

## 关键参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `--dry-run` / `--no-dry-run` | `--dry-run` | 是否执行外部命令 |
| `--fetch` | false | 运行 fetch_reviews.py |
| `--limit` | 10 | 最多处理任务数 |
| `--limit-prs` | 0 | 限制唯一 PR 数 |
| `--shard-scope` | pr | 分组方式: pr/path/task |
| `--execute-fixers` | false | 执行 fixer |
| `--execute-local-validation` | false | 执行本地验证 |
| `--execute-claude-review` | false | 执行 Claude review gate |
| `--execute-audit` | false | 执行 Codex audit gate |
| `--auto-commit` | false | 自动提交 |
| `--auto-push` | false | 自动推送 |
| `--wait-ci` | false | 等待 CI 通过 |
| `--auto-reply` | false | 自动回复 GitHub 评论 |
| `--fixer-parallelism` | 3 | 并行 fixer 数 |
| `--max-fix-rounds` | 2 | 最大重试轮数 |
| `--command-timeout` | 1800 | 外部命令超时(秒) |
| `--ci-timeout` | 3600 | CI 等待超时(秒) |
| `--ci-poll-interval` | 30 | CI 轮询间隔(秒) |

## 命令模板占位符

| 占位符 | Fixer | Validation | Claude Review | Audit | Push |
|---------|-------|-----------|--------------|-------|------|
| `{run_dir}` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `{shard_dir}` | ✓ | | | | |
| `{task_dir}` | ✓† | ✓ | ✓ | ✓ | |
| `{task_id}` | ✓† | ✓ | ✓ | ✓ | |
| `{pr_num}` | ✓† | ✓ | ✓ | ✓ | |
| `{path}` | ✓† | ✓ | ✓ | ✓ | |
| `{handoff}` | ✓ | | | | |
| `{round}` | ✓ | ✓ | ✓ | ✓ | |
| `{worktree}` | | ✓¹ | ✓ | ✓ | |
| `{audit_prompt}` | | | | ✓ | |

¹ Validation 阶段代码也会填 `{worktree}`，但内置默认校验器 `validate_changed_files.py` 不使用它。

† 仅在单任务 shard 时有效

## 安全设计

- **默认 dry-run**: 不传 `--no-dry-run` 不执行任何外部命令
- **分层开关**: 每层 gate 独立开关，可按需启用
- **新鲜度检查**: push 前自动重新抓取 review，防止重复回复
- **可恢复**: `--resume` 从中断处恢复，状态持久化在 `status.json`
- **Worktree 隔离**: fixer 在独立 git worktree 中操作，不污染主分支

## 输出

每次运行写入 `records/YYYYMMDD_HHMMSS/`:

```
├── tasks.jsonl               # 所有 ReviewTask
├── summary.md                # 运行摘要
├── run_config.json           # 运行参数快照
├── loop_events.json          # 每轮执行记录
├── source_reviews.md         # 原始 review 报告
├── ci_results.json           # CI 检查结果
├── runs/
│   ├── shards/               # fixer 分片 handoff
│   │   ├── shard-001/        # 常规 review 分片
│   │   └── shard-ext-001/    # CI/rebase 分片
│   └── pr-<N>/
│       ├── review-<id>/      # 每个 review 的任务目录
│       │   ├── task.json     # 任务详情
│       │   ├── status.json   # 可恢复状态
│       │   ├── task.md       # 任务摘要
│       │   ├── fixer_handoff.md   # Fixer prompt
│       │   ├── codex_audit_prompt.md  # Audit prompt
│       │   ├── execution.md  # 执行记录
│       │   ├── reply_draft.md # 回复草稿
│       │   └── final_report.md   # 最终报告
│       ├── ci-fix-*/         # CI 修复任务 (自动生成)
│       └── rebase-conflict-*/ # Rebase 冲突任务 (自动生成)
└── package/                  # 可分享的便携副本
```

## 使用示例（按场景）

> 约定：命令都在 `pr_review_loop/` 目录下运行；`--no-dry-run` 才会真正执行外部命令，不加就是只分析。
> Token 从 `.env` 或 `gh auth login` 提供，**不要**写进配置文件。

先加载环境变量（所有需要 token 的命令前都建议先跑一次）：

```bash
set -a; source .env; set +a
```

> `config.yaml` 会被自动加载：`commands:`（`claude_review_command`/`audit_command`/`commit_command`/`push_command` 等）、`workflow:`、`paths:` 里的值会填入对应参数，作为默认值。**命令行显式传的参数优先级最高**（例如 `--no-dry-run` 会覆盖 config 里的 `dry_run: true`），其次是 config，最后才是内置默认值。所以下面场景 3/5 里没在命令行写 `--claude-review-command` 等，是因为它们已在 config 里配好。

---

### 场景 0：只想看看有哪些 review 要修（最安全，先跑这个）

不改任何代码，只抓取 + 分析 + 生成任务清单，结果写到 `records/`。

```bash
set -a; source .env; set +a
python3 run_once.py --fetch --days 7 --limit 10 --dry-run
```

看 `records/<时间戳>/summary.md` 和 `tasks.jsonl` 确认 triage 结果。

---

### 场景 1：只修某一个具体 PR（比如 PR #1234）

用 `--limit-prs 1` 或先抓取再筛。最简单的方式是抓取后限制唯一 PR 数：

```bash
set -a; source .env; set +a
python3 run_once.py --fetch --days 30 --limit-prs 1 --dry-run
```

如果抓到的第一个 PR 不是你要的，先单独抓取生成报告，再用 `--report` 指定：

```bash
# 1) 抓取 review 报告（fetch 脚本按仓库/作者/时间过滤，不支持按单个 PR 号过滤）
python3 github_reviews/fetch_reviews.py --repo flagos-ai/FlagGems-Experimental --open --unreplied \
  --output records/latest_reviews.md
# 2) 用生成的报告跑 loop（可在报告里删掉不想处理的 PR 段落）
python3 run_once.py --report records/latest_reviews.md --dry-run
```

---

### 场景 2：复用已经抓好的 review 报告（不重新抓取）

```bash
python3 run_once.py --report records/20260707_074412/source_reviews.md --dry-run
```

---

### 场景 3：让 AI 真正改代码，但**不提交、不推送**（改动停在 worktree，你自己检查）

需要先把 `fixer_command` 配好（config.yaml 里默认是空的）。用内置的 `claude_fixer.py`：

```bash
set -a; source .env; set +a
python3 run_once.py \
  --fetch --days 7 --limit-prs 1 \
  --no-dry-run \
  --execute-fixers \
  --fixer-command 'python3 tools/claude_fixer.py --worktree /root/pr_worktrees/pr{pr_num} --handoff {handoff} --task-dir {task_dir} --timeout 900' \
  --execute-local-validation \
  --execute-claude-review \
  --execute-audit \
  --max-fix-rounds 2
```

> 注意：`{pr_num}`、`{task_dir}` 只在**单任务 shard**时有效。若一个 PR 有多条 review，用 `--shard-scope task` 让每条 review 单独成 shard，占位符才可用。
> 跑完后手动去 `/root/pr_worktrees/pr<N>` 看 `git diff`，满意再进场景 5 推送。

---

### 场景 4：完整闭环冒烟测试（用 stub 桩，不碰真实代码/GitHub）

验证流水线本身是否通，推荐第一次接触工具时先跑这个：

```bash
python3 run_once.py \
  --no-dry-run \
  --limit 3 \
  --execute-fixers \
  --fixer-command 'python3 test_fixtures/stub_fixer.py {run_dir} {shard_dir}' \
  --execute-claude-review \
  --claude-review-command 'python3 test_fixtures/stub_claude_review.py {task_dir}' \
  --execute-audit \
  --audit-command 'python3 test_fixtures/stub_audit.py {task_dir}' \
  --fixer-parallelism 2
```

---

### 场景 5：全自动闭环（改代码 → 审查 → 提交 → 推送 → 等 CI → 自动回复）

**风险最高**，会真正 push 并回复 GitHub 评论。建议先跑过场景 3 确认改动没问题。

```bash
set -a; source .env; set +a
python3 run_once.py \
  --fetch --days 7 --limit-prs 1 \
  --no-dry-run \
  --execute-fixers \
  --fixer-command 'python3 tools/claude_fixer.py --worktree /root/pr_worktrees/pr{pr_num} --handoff {handoff} --task-dir {task_dir} --timeout 900' \
  --execute-local-validation \
  --execute-claude-review \
  --execute-audit \
  --auto-commit \
  --auto-push \
  --require-fresh-before-push \
  --wait-ci \
  --auto-reply \
  --max-fix-rounds 2
```

各开关含义见上文「关键参数」表。去掉末尾任意一个开关即可停在对应步骤。

---

### 场景 6：恢复中断的运行

进程挂了或手动停了，用 `--resume` 从 `status.json` 断点续跑（其余参数保持一致）：

```bash
set -a; source .env; set +a
python3 run_once.py --resume records/20260707_074412 --no-dry-run \
  --execute-fixers --fixer-command '...' \
  --execute-claude-review --execute-audit --auto-push --wait-ci --auto-reply
```

---

### 推荐上手顺序

1. **场景 0** 先看清有哪些 review。
2. **场景 4** 用 stub 跑通整条流水线，熟悉输出结构。
3. **场景 3** 让 AI 真正改一个 PR，但停在 worktree 手动检查。
4. 确认无误后再上 **场景 5** 全自动。
