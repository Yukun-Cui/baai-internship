# flaggems-pr-submit-mthreads

FlagGems **摩尔线程(Moore Threads/MUSA)** 特化算子 PR 提交 skill，用于把 KernelGen/worktree
生成的单个摩尔线程特化算子整理成可提交到上游的 PR。摩尔线程特化覆盖的是通用层已有算子，
运行时由 `runtime.replace_customized_ops()` 自动替换，因此本 skill 复用上游已有的测试/benchmark
验证，通常只提交 **2 个文件**（kernel + `_mthreads/ops/__init__.py`）。

它是 `flaggems-pr-submit`（NVIDIA 通用）的姊妹 skill，针对摩尔线程后端的差异做了适配。

## 与其他 skill 的关键差异

| 项目 | NVIDIA 通用 | 摩尔线程特化（本 skill） |
|------|------------|------------------------|
| Kernel 路径 | `src/flag_gems/ops/` | `src/flag_gems/runtime/backend/_mthreads/ops/` |
| 提交文件数 | 6 | 通常 2 |
| test/benchmark | 新建 | 复用上游已有 |
| operators.yaml | 改 | 不改 |
| 设备 | `cuda` | `musa`（`torch_musa`） |
| 回退 | — | 回退 `flag_gems.ops.<op>` 通用实现 |
| Logger | `GEMS <OP>` | `GEMS_MTHREADS <OP>` |
| PR 标签 | `[Nvidia]` | `[KernelGen][MThreads]` |
| 分支 | `pr/<op>` | `pr/mthreads-<op>` |
| 硬件限制 | — | 不支持 fp64/int64 |

## 目录结构

| 路径 | 说明 |
|------|------|
| `SKILL.md` | agent 主说明：触发条件、硬规则、工作流、门禁 |
| `scripts/` | 自动化脚本：查询、预检、提取注册、检查、生成 PR 描述、提交、创建 PR |
| `references/` | 辅助文档：PR checklist、常见问题、命名规则(naming) |
| `data/` | 可变数据（PR 状态记录）；规范名/待提交列表默认复用 `flaggems-pr-submit/data/` |

## 脚本

| 脚本 | 用途 |
|------|------|
| `operator_registry.py` | 规范名查询 (`lookup`) + PR 链接回填 (`backfill`) + 待提交/已提交列表 |
| `preflight.sh` | 提交前预检：worktree、通用算子存在上游、特化不存在上游、test 复用判定、benchmark 数据 |
| `prepare_kernel.sh` | 从 worktree 复制 kernel + 确保 Apache 文件头 + 按字母序注册 `_mthreads/ops/__init__.py` |
| `check_operator.py` | 自动化验证：文件头、注册、musa 设备、fallback、`GEMS_MTHREADS` logger、`tl_extra_shim`、fp64/int64、单算子 PR、上游冲突 |
| `format_benchmark.py` | 解析现跑的 benchmark stdout（`--bench-log`）提取加速比（几何平均）生成英文 PR 描述 |
| `commit_and_push.sh` | 验证分支 + 逐文件 stage + commit（无 AI 署名）+ push fork |
| `create_pr.sh` | 生成 PR body + `gh pr create` + 回填链接 |

## 核心工作流

1. **Phase 0**：`operator_registry.py lookup <op>` + `preflight.sh <op>` — 查规范名，确认通用算子在上游、特化不在上游。
2. **Phase 1**：`git fetch upstream` + 基于 `upstream/master` 建分支 `pr/mthreads-<op>`。
3. **Phase 1.5**：在 worktree 中用 `fix_worktree_import.py` 跑精度测试和 benchmark，确认特化被 `replace_customized_ops()` 替换（输出中有 `GEMS_MTHREADS <OP>` 日志）并获取加速比。
4. **Phase 2**：`prepare_kernel.sh` 复制 kernel + 注册 `__init__.py`（BLAS 类算子注册在 capability≥3 分区）。
5. **Phase 3**：`check_operator.py --repo-dir` 门禁，0 errors。
6. **Phase 4**：`pre-commit run --files <2 个文件>`。
7. **Phase 5**：`commit_and_push.sh` — 逐文件 stage、commit（无 Co-Authored-By）、push fork。
8. **Phase 6**：`create_pr.sh` — 生成英文 PR body（含加速比）并创建 upstream PR。
9. **Phase 7**：`operator_registry.py backfill <op> <pr_url>` 回填链接。

## 环境变量

- `FLAGGEMS_REPO` — FlagGems 仓库路径（默认 `/root/FlagGems`）
- `FLAGGEMS_NORM_XLSX` / `FLAGGEMS_PR_XLSX` — 覆盖规范名表 / 待提交列表路径
- `BENCH_LOG` — 覆盖 benchmark log 路径（默认 `/tmp/<op>_mthreads_bench.log`）

## 摩尔线程环境提示

- 卡状态用 `mthreads-gmi`，指定卡用 `MUSA_VISIBLE_DEVICES`（不是 `nvidia-smi`/`CUDA_VISIBLE_DEVICES`）
- worktree 内运行 import/pytest 必须先 `cd` 进 worktree，再用 `auto_gen/fix_worktree_import.py`
- 参考 kernel：`_mthreads/ops/celu.py`（pointwise + fallback）、`log.py`（手写 kernel）、`addmm.py`（BLAS）
