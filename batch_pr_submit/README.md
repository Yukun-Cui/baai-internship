# batch_pr_submit

FlagGems 算子批量提 PR 工具。读取算子列表，为每个算子创建独立的 git worktree 做隔离，并行调用 `flaggems-pr-submit` skill 完成「提取 → 校验 → 测试 → benchmark → 提交 → 建 PR」的全流程。每个算子产出一份 JSON 记录和文本日志，互不干扰。

有两套并行实现，按需选用：

- **`batch_submit.sh`** —— 纯 shell 编排，每个算子调 `submit_one.sh`，简单直接。
- **`batch_pr_submit.py`** —— Python 编排，额外支持自动 GPU 空闲检测/抢占、per-GPU flock 锁、断点续跑、预算控制等。

## 文件说明

| 文件 | 说明 |
|------|------|
| `batch_submit.sh` | Shell 批量入口，创建 worktree 并并行调用 `submit_one.sh`。 |
| `submit_one.sh` | 单算子提交，用 worktree 隔离，实际提交逻辑交给 skill 的 `submit_operator.py`。 |
| `batch_pr_submit.py` | Python 批量入口，带 GPU 调度、锁、续跑、预算等增强能力。 |
| `config.env` | Shell 版共享配置：算子列表、仓库目录、skill 脚本目录、日志目录、worktree 根目录、`GH_TOKEN`（本地文件，已 gitignore）。**仅 `batch_submit.sh`/`submit_one.sh` 读取；Python 版 `batch_pr_submit.py` 不读 `config.env`，全部参数走命令行。** |
| `ops_list.txt` | 算子列表示例，复制成自己的列表使用（`operators_*.txt`、`agent_status.json` 等运行产物已 gitignore）。 |

## 配置

编辑 `config.env`（本地文件，不提交；**仅 Shell 版 `batch_submit.sh`/`submit_one.sh` 读取**）：

```bash
MAX_PARALLEL=1                                                   # 并行数（每个 job 独占一块 GPU）
OP_LIST="/root/baai-internship/batch_pr_submit/ops_list.txt"
REPO_DIR="/root/FlagGems"                                        # 源仓库（并行期间不被修改）
SCRIPTS_DIR="/root/baai-internship/skills/flaggems-pr-submit/scripts"
GH_TOKEN="${GH_TOKEN:-}"                                         # 启动前 export
LOG_DIR="/root/baai-internship/batch_pr_submit/logs"
WORKTREE_BASE_DIR="/tmp/flaggems_worktrees"                      # 每个算子的临时 worktree
```

> Python 版 `batch_pr_submit.py` 不读 `config.env`，上述键（`MAX_PARALLEL`/`OP_LIST`/`WORKTREE_BASE_DIR`/`LOG_DIR`/`SCRIPTS_DIR`）对它无效，改用命令行参数：`--ops-file`、`--max-workers`、`--worktree-base`、`--log-dir`、`--skill-dir`。其默认值也不同于 Shell 版——worktree 根默认 `/tmp/flaggems_agent_worktrees`、日志目录默认 `…/logs/agent/`。

`submit_one.sh` 会把 worktree 的 origin 指向你的 fork（在脚本里改成自己的 fork 地址）。

> 提 PR 前先 `export GH_TOKEN=<your_token>`。GH_TOKEN 通过环境变量传入，不要写死在文件里。

## 用法

Shell 版：

```bash
export GH_TOKEN=<your_token>
./batch_submit.sh                       # 用 config.env 里的 OP_LIST，按 config.env 并行数
./batch_submit.sh -j 4                  # 4 路并行
./batch_submit.sh -l ops_list.txt       # 自定义列表
./batch_submit.sh --start 5 --end 10    # 只跑列表第 5-10 行
./batch_submit.sh --dry-run             # 只打印计划，不执行
```

Python 版（带 GPU 自动调度，`--ops-file` 必填）：

```bash
export GH_TOKEN=<your_token>
python3 batch_pr_submit.py --ops-file ops_list.txt \
  --repo-dir /root/FlagGems --max-workers 4 --gpus auto
python3 batch_pr_submit.py --ops-file ops_list.txt --dry-run    # 预演
```

## 输出

每次运行写到 `<LOG_DIR>` 下的一个**按时间戳命名的子目录**里，而非直接落在 `<LOG_DIR>` 下：

- **Shell 版**：`<LOG_DIR>/<TIMESTAMP>/<op_name>.log` —— 完整脚本输出；`<op_name>.json` —— 结构化结果记录。
- **Python 版**：默认 `<LOG_DIR>/agent/<run_id>/<op_name>.log`（`<LOG_DIR>` 默认 `…/logs/agent`，`<run_id>` 为 UTC 时间戳），同一目录下还会产出 `<op_name>_conversation.json`、`_conversation.jsonl`、`_summary.log`。

日志目录已被 `.gitignore` 忽略，不会提交。

## 相关工具

单算子提交细节见 [skills/flaggems-pr-submit](../skills/flaggems-pr-submit/)；批量提交后的审计见 [batch_pr_audit](../batch_pr_audit/)，从 CI 回填性能见 [ci_performance_update](../ci_performance_update/)。
