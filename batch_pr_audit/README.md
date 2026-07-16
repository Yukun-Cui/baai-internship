# batch_pr_audit — FlagGems PR 批量审计工具

对 FlagGems 算子 PR 执行 **两阶段并行审计**，自动发现提交流程中的合规性问题。

## 架构

```
输入 PR 列表 → 并行处理每个 PR →
  阶段1: gh CLI 收集 PR artifacts (pr.json, diff.patch, files.txt)
  阶段2: 确定性规则检查 (纯 Python 正则/解析, 7 类规则)
  阶段3: AI Agent 审查 (调用 claude CLI, streaming JSON, 可选)
→ 输出 summary.json + summary.md
```

## 快速开始

```bash
# 审计指定 PR (仅确定性检查, 不调用 AI)
python3 batch_pr_audit.py --no-agent --prs "#3900, #3901, #3902"

# 审计指定 PR + AI 深度审查
python3 batch_pr_audit.py --prs "#3900, #3901" --model claude-opus-4-8

# 从文件读取 PR 列表
python3 batch_pr_audit.py --prs-file pr_list.txt --no-agent

# 通过 gh 搜索查询 PR
python3 batch_pr_audit.py --query "is:open label:operator" --no-agent

# 修改并发数和超时
python3 batch_pr_audit.py --prs "#3900" --max-workers 2 --timeout 30
```

## 配置

编辑 `config.env` 或通过命令行参数覆盖:

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `REPO` | `flagos-ai/FlagGems-Experimental` | 目标仓库 |
| `SKILL_DIR` | `/root/baai-internship/skills/flaggems-pr-submit` | PR 提交 skill 路径 |
| `MODEL` | `claude-opus-4-8` | Agent 使用的模型 |
| `MAX_WORKERS` | `4` | 并行 worker 数 |
| `TIMEOUT_MINUTES` | `25` | 每个 PR 的 agent 超时(分钟) |
| `PERMISSION_MODE` | `acceptEdits` | claude CLI 权限模式 |

## 确定性检查规则 (7 类)

### PR 级别
- PR body 完整性: 是否有空 body、debug 残留词、Co-Authored-By 残留
- 文件范围: 是否触碰到全局 infra、是否跨多个算子

### 配置一致性
- `operators.yaml`: id 重复、必要字段缺失、labels 完整性、kind 合法性
- `_FULL_CONFIG`: 注册目标是否正确(wrapper vs kernel)、是否有重复注册
- `__init__.py`: 新增 public wrapper 是否都导出、是否误导出 kernel 函数
- YAML/`_FULL_CONFIG` 中 `special_*` 命名是否正确使用 `special.xxx` 格式

### 代码质量
- torch 私有 API 使用、硬编码 dtype 列表、尾随空格
- `gems_assert_close` 滥用 `rtol`、skip/xfail 缺少 issue 引用
- `print()` 残留、Co-Authored-By 残留

### Kernel 风险
- 重复函数定义、dispatch 递归风险 (wrapper 中调 `torch.<same_op>()`)
- 死代码 (@use_tl_extra pass stub 未被调用)
- 内联 `triton.Config` 替代 `tune_configs.yaml`

### 结构完整性
- 新算子文件: KernelGen 版权头、logging 配置
- 新测试文件: 必需 import 模式
- 新 benchmark 文件: 标准 benchmark 类使用

### 特化/覆盖率
- Backend 特化: `ops/__init__.py` 更新、`tune_configs.yaml` 范围
- Fused 算子: 目录位置、`fused/__init__.py` 注册
- 函数覆盖率: wrapper ↔ yaml ↔ pytest mark ↔ benchmark op_name 四向一致性
- Variant 一致性: `_out` / `_` 变体在 `_FULL_CONFIG` 中的注册
- 特化 PR 依赖: 是否有对应的泛化实现 PR

### 其他
- Benchmark 公平性、设备硬编码、logger 格式、speedup 低保

## 发现严重级别

| 级别 | 含义 |
|------|------|
| `high` | 阻赛性问题，必须在合并前修复 |
| `medium` | 可操作问题，建议修复 |
| `low` | 轻微问题，可选修复 |
| `info` | 提示性信息 |

## 输出

每次运行在 `reports/<timestamp>/` 下生成:

```
reports/20260615_060731/
├── summary.json          # 结构化汇总(所有 PR)
├── summary.md            # Markdown 汇总表格
├── status.json           # 实时状态(运行中持续更新)
├── pr_3900/
│   ├── pr.json           # PR 元数据
│   ├── diff.patch        # 完整 diff
│   ├── files.txt         # 变更文件列表
│   ├── deterministic_checks.json  # 确定性检查结果
│   ├── report.md         # 审计报告
│   ├── conversation.jsonl  # AI agent 完整对话记录
│   └── raw.log           # agent 原始输出日志
└── ...
```

## 文件清单

```
batch_pr_audit/
├── batch_pr_audit.py          # 主脚本
├── config.env                 # 默认配置
├── prompts/
│   └── pr_audit_prompt.md    # Claude agent 审查 prompt 模板
└── README.md                  # 本文件
```
