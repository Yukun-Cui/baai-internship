# Auto-Gen - FlagGems 算子自动生成工具

基于 Claude Code 的 FlagGems 算子自动生成编排系统，支持多 GPU 并行处理和多硬件后端（CUDA、MetaX、Iluvatar、Enflame）。

## 功能特性

- 🔄 **全自动流程**：代码生成 → 编译 → 测试 → 验证
- 🎯 **多硬件后端**：支持 CUDA、MetaX（沐曦）、Iluvatar（天数）、Enflame（燧原）
- 🔧 **智能调度**：GPU 资源锁管理，支持 8 卡并行
- 📊 **详细追踪**：执行日志、JSONL 对话记录、时间线统计
- 🔁 **自动重试**：失败自动重试，可配置重试次数
- 🧪 **单算子测试**：支持独立测试单个算子

## 快速开始

### 1. 环境准备

```bash
# 安装依赖
pip install pyyaml openpyxl ruamel.yaml pre-commit

# 安装 Claude Code CLI（如未安装）
# 参考：https://docs.anthropic.com/claude/docs/claude-code

# 配置 API 密钥
# 直接编辑 .env，填入 ANTHROPIC_AUTH_TOKEN / ANTHROPIC_BASE_URL / ANTHROPIC_MODEL
# （.env 已被 .gitignore 忽略，不会提交）
```

### 2. 配置环境

编辑 `config.yaml`，修改以下关键配置：

```yaml
flaggems_dir: /path/to/your/FlagGems  # FlagGems 仓库路径
python_path: /usr/bin/python3   # Python 解释器路径
claude_bin: claude                     # Claude Code CLI 命令
device:
  gpu_ids: [0, 1, 2, 3, 4, 5, 6, 7]   # 可用的 GPU ID 列表
```

### 3. 运行脚本

#### 测试单个算子
```bash
./test_single_op.sh relu
```

#### 批量处理算子列表
```bash
# 使用默认配置
python3 orchestrator.py

# 指定配置文件和算子列表
python3 orchestrator.py --config config.yaml ops_list.txt

# 使用 MetaX 后端
python3 orchestrator.py --metax

# 使用 Iluvatar 后端
python3 orchestrator.py --iluvatar

# 使用 Enflame（燧原）后端
python3 orchestrator.py --enflame

# 中断后恢复：跳过已成功的算子，只跑剩余的（传上次 summary.json）
python3 orchestrator.py --resume results/summary_<timestamp>.json ops_list.txt

# 恢复时同时重试上次失败的算子
python3 orchestrator.py --resume results/summary_<timestamp>.json --retry-failed ops_list.txt

# 干跑：不真正启动 Claude Code，只走一遍流程（用于验证配置/调度）
python3 orchestrator.py --dry-run ops_list.txt

# 跳过 git fetch upstream（离线或 upstream 已最新时）
python3 orchestrator.py --skip-fetch ops_list.txt
```

### 自动化行为说明

- **pre-commit**：启动时会自动检测/安装 pre-commit 并预热钩子环境（worktree 会继承主仓库的钩子）。缺失时会交互式询问是否安装。
- **upstream fetch**：默认在建 worktree 前 `git fetch upstream`，确保基线分支最新。缺 upstream remote 或失败时降级为警告（非致命），可用 `--skip-fetch` 跳过，或在 config 里设 `auto_fetch_upstream: false`。
- **注册排序**：算子成功后自动调用 `sort_registrations.py` 对 `conf/operators.yaml`、`src/flag_gems/ops/__init__.py`、`src/flag_gems/__init__.py` 及改动的厂商 `ops/__init__.py` 排序，并 amend 到该次 commit。依赖 `ruamel.yaml`（`pip install ruamel.yaml`）。
- **完整性校验 + fixup**：CC 声称成功后，`validate_operator.py` 会独立静态检查算子是否真的注册齐全——`conf/operators.yaml` 中每个变体（base / `xxx_` / `xxx.out`）存在且带 `KernelGen` 标签，`tests/test_<op>.py` 与 `benchmark/test_<op>.py` 有对应的 `@pytest.mark.<op>`。若不合格，会在第一次尝试时复用同一 worktree、把缺失项追加到 prompt 里让 CC 补齐（`[FIXUP]`），而不是从头重跑。仅对默认 CUDA 后端生效（厂商后端文件布局不同）；`--dry-run` 下跳过。

## 目录结构

```
auto_gen/
├── orchestrator.py              # 主编排脚本
├── device_manager.py            # GPU 设备管理器
├── sort_registrations.py        # 算子注册排序（成功后自动 amend）
├── validate_operator.py         # 算子完整性校验（触发 fixup 重试）
├── config.yaml                  # 配置文件
├── .env                         # API 密钥配置（不提交）
├── ops_list.txt                 # 算子列表（CUDA 默认）
├── ops_list_enflame.txt         # 算子列表（Enflame 后端）
├── test_single_op.sh            # 单算子测试脚本
├── templates/                   # Prompt 模板
│   ├── generate_op.md           # CUDA 后端模板
│   ├── generate_op_metax.md     # MetaX 后端模板
│   ├── generate_op_iluvatar.md  # Iluvatar 后端模板
│   ├── generate_op_iluvatar_optimize.md  # Iluvatar 优化模板
│   └── generate_op_enflame.md   # Enflame（燧原）后端模板
├── extract_metax_failed_ops.py  # 提取 MetaX 失败算子
├── extract_iluvatar_failed_ops.py  # 提取 Iluvatar 失败算子
├── extract_enflame_failed_ops.py   # 提取 Enflame（燧原）失败算子
├── fix_worktree_import.py       # 修复 worktree 导入问题
└── results/                     # 运行结果（自动生成）
    ├── logs_<timestamp>/        # 每次运行的算子执行日志与时间线
    └── summary_<timestamp>.json # 总体执行摘要
```

## 配置说明

### config.yaml 核心配置

```yaml
# FlagGems 仓库路径
flaggems_dir: /root/FlagGems

# Python 解释器路径
python_path: /usr/bin/python3

# Claude Code CLI 命令
claude_bin: claude

# GPU 设备配置
device:
  gpu_ids: [0, 1, 2, 3, 4, 5, 6, 7]  # 可用 GPU 列表
  lock_dir: /tmp/auto_gen_gpu_locks   # GPU 锁文件目录

# 执行参数
max_retries: 3                # 失败重试次数
timeout_per_op: 9600          # 单个算子超时时间（秒）
budget_per_op: 10000000.0     # 单个算子预算（tokens）
poll_interval: 10             # 状态轮询间隔（秒）

# 结果输出
results_dir: results          # 结果输出目录
template: templates/generate_op.md  # 默认 prompt 模板

# MetaX 后端配置
metax:
  template: templates/generate_op_metax.md
  ops_list: ops_list_metax.txt

# Iluvatar 后端配置
iluvatar:
  template: templates/generate_op_iluvatar_optimize.md
  ops_list: ops_list_iluvatar.txt

# Enflame（燧原）后端配置
enflame:
  template: templates/generate_op_enflame.md
  ops_list: ops_list_enflame.txt
  arch: gcu300          # 目标 GCU 架构，可选 gcu300 / gcu400
```

> ⚠️ **燧原后端说明**：与沐曦/天数不同，燧原特化算子在 FlagGems 中**按架构分目录**存放于
> `src/flag_gems/runtime/backend/_enflame/<arch>/ops/`（如 `gcu300/ops/`、`gcu400/ops/`）。
> `enflame.arch` 决定生成到哪个架构目录，默认 `gcu300`。燧原硬件不支持 fp64/int64，
> 模板已内置相应约束（int64→int32 转换、`GEMS_ENFLAME` logger 前缀、本地 `..utils.pointwise_dynamic` 导入）。

### .env API 配置

```bash
ANTHROPIC_AUTH_TOKEN=sk-xxx  # 你的 API 密钥（代码读取的是 ANTHROPIC_AUTH_TOKEN）
ANTHROPIC_BASE_URL=https://your-api-endpoint  # API 端点
ANTHROPIC_MODEL=claude-opus-4-8  # 使用的模型
```

## 算子列表格式

算子列表文件支持多种格式：

```
# 注释行会被忽略

# 简单格式
relu
sigmoid

# PyTorch 格式（会自动去除 aten:: 前缀）
aten::tanh
aten::abs

# 带重载后缀（会自动去除 .Tensor 等后缀）
aten::round.Tensor
aten::add.Scalar
```

## 工作流程

1. **读取配置**：加载 `config.yaml` 和 `.env`
2. **解析算子列表**：读取并解析算子列表文件
3. **GPU 分配**：为每个算子分配可用的 GPU
4. **创建 Worktree**：为每个算子创建独立的 git worktree
5. **调用 Claude Code**：使用配置的 prompt 模板生成算子代码
6. **编译测试**：在 worktree 中编译并测试生成的代码
7. **记录结果**：保存日志、JSONL 对话记录、时间线
8. **清理资源**：清理 worktree，释放 GPU 锁
9. **生成摘要**：汇总所有算子的执行结果

## 输出文件说明

每次运行生成带时间戳的目录：`results/logs_<timestamp>/` 和 `results/summary_<timestamp>.json`。

### results/logs_<timestamp>/ 目录
- `<op_name>.log`：算子执行日志（Claude Code 的 stdout/stderr）
- `<op_name>.jsonl`：完整的 Claude Code 对话记录（stream-json）
- `<op_name>.timeline.txt`：从 jsonl 生成的可读执行时间线

### results/summary_<timestamp>.json
```json
{
  "start_time": "2026-07-09T03:00:00+00:00",
  "end_time": "2026-07-09T03:40:00+00:00",
  "summary": {
    "total": 10,
    "success": 8,
    "failed": 2,
    "in_progress": 0
  },
  "operators": {
    "relu": {"status": "success", "gpu_id": 0, "duration_seconds": 120.5, "...": "..."},
    "tanh": {"status": "failed", "error_message": "...", "...": "..."}
  }
}
```

## 故障排查

### 日志文件为 0 字节
- 检查 `claude` 命令是否可用、`.env` 中的 token 是否正确
- 查看对应 `results/logs_<timestamp>/<op>.log` 里的 stderr 输出

### GPU 锁死锁
```bash
# 清理所有 GPU 锁
rm -rf /tmp/auto_gen_gpu_locks/*
```

### Worktree 清理失败
```bash
# 手动清理所有 worktree
cd /path/to/FlagGems
git worktree list
git worktree remove <worktree-path> --force
```

### Claude Code 连接失败
- 检查 `.env` 中的 API 密钥是否正确
- 检查网络连接
- 验证 `claude` 命令是否可用：`which claude`

## 辅助工具

### extract_metax_failed_ops.py
从 Excel 文件中提取 MetaX 失败算子列表。

```bash
python3 extract_metax_failed_ops.py metax_results.xlsx -o ops_list_metax.txt
```

### extract_iluvatar_failed_ops.py
从 Excel 文件中提取 Iluvatar 失败算子列表。

```bash
python3 extract_iluvatar_failed_ops.py --input iluvatar_results.xlsx --output ops_list_iluvatar.txt
```

### extract_enflame_failed_ops.py
从 Excel 文件中提取 Enflame（燧原）失败算子列表。自动探测表头中的"燧原"结果列。

```bash
python3 extract_enflame_failed_ops.py --input results.xlsx --output ops_list_enflame.txt
# 若自动探测列失败，可用 --result-col 手动指定（0 基列索引）
python3 extract_enflame_failed_ops.py --input results.xlsx --result-col 4
```

### fix_worktree_import.py
修复 worktree 中的模块导入问题。

```bash
# 在 worktree 目录内运行（自动探测 worktree 根，或用 FIX_WORKTREE_DIR 指定）
python3 fix_worktree_import.py -c "import flag_gems; print(flag_gems.__file__)"
python3 fix_worktree_import.py --pytest tests/test_xxx.py -m <op> -vs
```

## 实现文档

后端实现细节散落在 `templates/generate_op_*.md` 各模板内（MetaX / Iluvatar / Enflame），无单独 changelog 文件。

## 注意事项

1. **首次运行**：建议先用 `ops_list.txt` 里的少量简单算子测试
2. **磁盘空间**：每个 worktree 约占用 500MB-1GB，确保有足够空间
3. **GPU 资源**：确保 GPU 可用且未被其他任务占用
4. **中断恢复**：可以用 `Ctrl+C` 优雅停止，会自动清理资源
5. **并行数量**：默认使用所有配置的 GPU，可通过修改 `device.gpu_ids` 控制并行数

## 性能优化建议

- 使用 SSD 存储 worktree 以加快文件操作
- 调整 `timeout_per_op` 以适应不同复杂度的算子
- 合理设置 `budget_per_op` 避免过度消耗 API 额度
- 对于简单算子，可以降低 `max_retries` 节省时间

## 贡献指南

欢迎提交 Issue 和 Pull Request！

- 新增硬件后端：参考现有 `templates/generate_op_*.md` 的结构，按 MetaX / Iluvatar / Enflame 的模式扩展
- 优化 prompt 模板：修改 `templates/` 下的模板文件
- 改进调度算法：修改 `device_manager.py`

## 许可证

本项目代码仅供学习和研究使用。
