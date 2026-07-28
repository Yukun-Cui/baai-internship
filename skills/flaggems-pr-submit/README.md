# flaggems-pr-submit

FlagGems 算子 PR 提交 skill，用于把 KernelGen/worktree 生成的单个算子整理成可提交到 `flagos-ai/FlagGems-Experimental` 的 PR。它把规范名查询、代码提取、命名统一、提交前检查、本地测试、benchmark、PR 描述生成、push、PR 创建和规范名表回填串成一条固定流程。

## 目录结构

| 路径 | 说明 |
|------|------|
| `SKILL.md` | agent 使用的主说明，包含触发条件、硬规则、工作流和门禁要求 |
| `scripts/` | 自动化脚本入口，负责查询、提取、检查、生成 PR 描述和提交 |
| `references/` | 辅助参考文档，包括命名规则、PR 模板、常见问题和 checklist |
| `data/` | skill 运行所需的可变数据，包括规范名表、待提交列表和 PR 状态记录 |

## 数据文件

默认数据目录是 `data/`：

| 文件 | 用途 |
|------|------|
| `data/规范名.xlsx` | 规范命名映射，也是 PR 链接回填目标 |
| `data/第一批pr算子.xlsx` | 待提交算子列表和预期/历史加速比 |
| `data/pr状态记录.md` | 提交流程中的失败、warning、低加速比和 PR 创建事件 |

可通过环境变量覆盖默认路径：

- `FLAGGEMS_PR_SUBMIT_DATA_DIR`
- `FLAGGEMS_NORM_XLSX`
- `FLAGGEMS_PR_XLSX`
- `FLAGGEMS_PR_RECORD_PATH`

## 核心工作流

1. 查询规范名：`operator_registry.py lookup <op>` 读取 `data/规范名.xlsx` 和 `data/第一批pr算子.xlsx`，获得规范名、已有 PR 链接、加速比和表格行号。
2. 创建干净分支：基于 `upstream/infra-ci` 创建 `pr/<op>` 分支。
3. 提取代码：`extract_from_worktree.py` 从 `.worktrees/gen-<op>` 提取 kernel、test、benchmark、`ops/__init__.py`、顶层 `__init__.py` 和 `conf/operators.yaml`。
4. 统一命名：`name_plan.py` 区分 `source_name`、`impl_name`、`canonical_name`，必要时把文件名、wrapper、mark、benchmark `op_name`、yaml 和注册项都机械迁移到规范名。
5. 提交前门禁：`check_operator.py --strict` 检查注册一致性、yaml 唯一性、命名残留、dtype、benchmark、anti-hack、单算子 PR、上游冲突等。
6. 本地验证：`submit_operator.py` 运行 pre-commit、pytest correctness 和 core benchmark。
7. 生成 PR 描述：`gen_pr_description.py` 从 benchmark 输出生成结构化性能数据，`submit_operator.py` 组装英文 PR body。
8. 提交和推送：自动 `git add` 指定文件、commit、fetch upstream、最终 strict check、push 到 fork。
9. 创建 PR 并回填：通过 GitHub API 创建上游 PR，然后调用 `operator_registry.py backfill` 把 PR 链接写回 `data/规范名.xlsx`。

## 常用命令

在 FlagGems 仓库中执行：

```bash
python /path/to/flaggems-pr-submit/scripts/operator_registry.py lookup <op>
```

从 worktree 提取并准备 6 个 PR 文件：

```bash
python /path/to/flaggems-pr-submit/scripts/extract_from_worktree.py <op> \
  --repo-dir /root/FlagGems
```

如果生成名、内部实现名和规范名不一致，可显式指定：

```bash
python /path/to/flaggems-pr-submit/scripts/extract_from_worktree.py <canonical-op> \
  --source-name <worktree-op> \
  --impl-name <worktree-wrapper-op> \
  --canonical-name <canonical-op> \
  --repo-dir /root/FlagGems
```

验证、测试、benchmark 并提交 PR：

```bash
CUDA_VISIBLE_DEVICES=<gpu-id> \
python /path/to/flaggems-pr-submit/scripts/submit_operator.py <op> \
  --repo-dir /root/FlagGems
```

调试时可加 `--dry-run`，但仍会运行检查、测试和 benchmark，只跳过 commit、push、PR 创建和回填。

## 主要脚本

| 脚本 | 说明 |
|------|------|
| `scripts/operator_registry.py` | 查询规范名、列出待提交/已提交算子、回填 PR 链接 |
| `scripts/name_plan.py` | 生成 source/impl/canonical 命名计划，并写入 `.name_plan/<op>.json` |
| `scripts/extract_from_worktree.py` | 从生成 worktree 提取 6 个提交文件，并做规范名迁移 |
| `scripts/check_operator.py` | 提交前严格检查，覆盖注册、yaml、测试、benchmark、anti-hack、旧名残留等 |
| `scripts/gen_pr_description.py` | 解析 benchmark 输出，生成 PR 描述所需 JSON |
| `scripts/submit_operator.py` | 一站式提交入口，串行执行检查、测试、benchmark、commit、push、创建 PR、回填 |
| `scripts/pr_gate_check.sh` | PR gate 辅助检查脚本 |

## 注意事项

- 每个 PR 只提交一个 aten 算子。
- 不要手动跳过 `submit_operator.py` 的中间步骤；失败后先修复，再重新运行。
- 规范名是最终提交面，生成名只能作为 worktree/source 读取来源。
- `GH_TOKEN` 只通过环境变量提供，不要写入 skill、README、日志或 PR 内容。
- `data/` 是可变数据目录，提交前确认其中 Excel 和状态记录是否为你希望发布的版本。

