# flaggems-pr-submit

FlagGems 算子 PR 提交 skill，用于把 KernelGen/worktree 生成的单个算子整理成可提交到 `flagos-ai/FlagGems-Experimental` 的 PR。它把代码提取、命名统一、提交前检查、本地测试、benchmark、PR 描述生成、push 和 PR 创建串成一条固定流程。

## 目录结构

| 路径 | 说明 |
|------|------|
| `SKILL.md` | agent 使用的主说明，包含触发条件、硬规则、工作流和门禁要求 |
| `scripts/` | 自动化脚本入口，负责提取、检查、生成 PR 描述和提交 |
| `references/` | 辅助参考文档，包括命名规则、PR 模板、常见问题和 checklist |

## 核心工作流

1. 创建干净分支：基于 `upstream/infra-ci` 创建 `pr/<op>` 分支。
2. 提取代码：`extract_from_worktree.py` 从 `.worktrees/gen-<op>` 提取 kernel、test、benchmark、`ops/__init__.py`、顶层 `__init__.py` 和 `conf/operators.yaml`。
3. 统一命名：`name_plan.py` 区分 `source_name`、`impl_name`、`canonical_name`，必要时把文件名、wrapper、mark、benchmark `op_name`、yaml 和注册项都机械迁移到规范名。
4. 提交前门禁：`check_operator.py --strict` 检查注册一致性、yaml 唯一性、命名残留、dtype、benchmark、anti-hack、单算子 PR、上游冲突等。
5. 本地验证：`submit_operator.py` 运行 pre-commit、pytest correctness 和 core benchmark。
6. 生成 PR 描述：`gen_pr_description.py` 从 benchmark 输出生成结构化性能数据，`submit_operator.py` 组装英文 PR body。
7. 提交和推送：自动 `git add` 指定文件、commit、fetch upstream、最终 strict check、push 到 fork。
8. 创建 PR：通过 GitHub API 创建上游 PR。

## 常用命令

在 FlagGems 仓库中执行，从 worktree 提取并准备 6 个 PR 文件：

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

调试时可加 `--dry-run`，但仍会运行检查、测试和 benchmark，只跳过 commit、push 和 PR 创建。

## 主要脚本

| 脚本 | 说明 |
|------|------|
| `scripts/name_plan.py` | 生成 source/impl/canonical 命名计划，并写入 `.name_plan/<op>.json` |
| `scripts/extract_from_worktree.py` | 从生成 worktree 提取 6 个提交文件，并做规范名迁移 |
| `scripts/check_operator.py` | 提交前严格检查，覆盖注册、yaml、测试、benchmark、anti-hack、旧名残留等 |
| `scripts/gen_pr_description.py` | 解析 benchmark 输出，生成 PR 描述所需 JSON |
| `scripts/submit_operator.py` | 一站式提交入口，串行执行检查、测试、benchmark、commit、push、创建 PR |
| `scripts/pr_gate_check.sh` | PR gate 辅助检查脚本 |

## 注意事项

- 每个 PR 只提交一个 aten 算子。
- 不要手动跳过 `submit_operator.py` 的中间步骤；失败后先修复，再重新运行。
- 规范名是最终提交面，生成名只能作为 worktree/source 读取来源；规范名与生成名不同时用 `--canonical-name` 显式指定。
- `GH_TOKEN` 只通过环境变量提供，不要写入 skill、README、日志或 PR 内容。

