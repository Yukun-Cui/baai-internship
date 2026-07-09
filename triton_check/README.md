# Triton 算子合规性检查工具

通过 Claude Code CLI 调用大模型，自动审查 FlagGems 仓库中的算子实现，判断是否是**真正的 Triton 实现**。

## 判断规则

| # | 规则 | 说明 |
|---|------|------|
| 1 | 禁止 torch 计算 | 核心逻辑不能用 `torch.matmul`, `torch.mm`, `torch.add` 等数值运算 |
| 2 | 允许 FlagGems 调用 | `flag_gems.utils.*`, `flag_gems.ops.*` 等内部模块合法 |
| 3 | 允许 torch 辅助操作 | `torch.empty_like`, `.shape`, `.contiguous()` 等非计算操作合法 |
| 4 | 必须有 triton kernel | 文件中需存在 `@triton.jit` 或通过 FlagGems 工具函数间接使用 |

## 环境要求

- Python 3.10+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) 已安装并可执行
- PyYAML: `pip install pyyaml`

## 配置

### 1. 创建 `.env` 文件

在 `triton_check/` 目录下创建 `.env` 文件（已在 `.gitignore` 中，不会被提交）：

```bash
# API 认证信息（模型由 ANTHROPIC_MODEL 决定，config.yaml 不再单独指定）
ANTHROPIC_AUTH_TOKEN=your_token_here
ANTHROPIC_BASE_URL=https://your-api-endpoint
ANTHROPIC_MODEL=claude-opus-4-8
```

### 2. 修改 `config.yaml`

根据实际环境调整：

```yaml
flaggems_dir: /root/FlagGems    # FlagGems 仓库路径

# 扫描模式：single_worktree（单目录）/ multi_worktree（每算子独立 worktree）
scan_mode: multi_worktree
worktree: ""                              # single_worktree 模式下的 worktree 子路径
worktree_pattern: ".worktrees/gen-{op}"   # multi_worktree 模式下的路径模板

# 仅检查列表中的算子，留空=扫描目录下所有
ops_list: "/root/baai-internship/auto_gen/ops_list.txt"

scan:
  nvidia_ops: true      # 是否检查 src/flag_gems/ops/
  backends: []          # 留空=全部厂商; 指定如 [_metax, _cambricon]

claude:
  bin: claude           # Claude Code CLI 路径（模型走 ANTHROPIC_MODEL）
  max_concurrent: 8     # 并发进程数
  timeout: 120          # 单算子超时(秒)

output_dir: results
```

## 使用方法

```bash
cd triton_check

# 检查全部算子（扫描 ops 目录下所有算子）
python3 checker.py

# 只检查特定算子
python3 checker.py -o add abs attention

# 只检查特定厂商
python3 checker.py --vendor metax cambricon

# 限制数量（调试用）
python3 checker.py --limit 5 -v

# 或直接用快捷脚本
./run.sh -o add --limit 3 -v
```

## 输出

运行后在 `results/` 目录生成 JSON 报告，格式示例：

```json
{
  "timestamp": "2026-05-15T07:07:50+00:00",
  "summary": {"total": 2, "pass": 2, "fail": 0, "error": 0},
  "results": [
    {
      "operator": "add",
      "file": "src/flag_gems/ops/add.py",
      "vendor": "nvidia",
      "pass": true,
      "reason": "核心计算使用 Triton kernel（@triton.jit）",
      "violations": []
    }
  ]
}
```

## 自定义规则

编辑 `prompt_template.md` 可调整判断规则，模板变量：
- `{{OPERATOR}}` — 算子名称
- `{{VENDOR}}` — 厂商名
- `{{FILE_PATH}}` — 文件相对路径
- `{{SOURCE_CODE}}` — 算子源码全文

## 目录结构

```
triton_check/
├── .env                  # API 凭证（不提交）
├── config.yaml           # 配置文件
├── checker.py            # 主脚本
├── prompt_template.md    # LLM 判断 prompt 模板
├── run.sh                # 快捷启动
└── results/              # 输出报告（不提交）
```
