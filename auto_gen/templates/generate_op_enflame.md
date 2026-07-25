# FlagGems 燧原(Enflame / 燧原科技)算子特化生成任务

你需要为 FlagGems 项目实现一个燧原(Enflame)后端的特化 Triton 算子。

## 任务信息

- **算子名称**: {{OPERATOR}}
- **GPU ID**: {{GPU_ID}}
- **工作目录**: {{WORK_DIR}} (这是一个 git worktree)
- **Python 路径**: {{PYTHON_PATH}}
- **目标架构**: {{ARCH}} (燧原 GCU 架构，如 gcu300 / gcu400)

## 运行环境说明

**重要**：本项目**不需要** `pip install`。`pytest.ini` 已配置 `pythonpath = src`，因此在工作目录（worktree 根目录）下运行 pytest 时，会自动将 `<工作目录>/src` 加入 `sys.path`，从而正确导入当前 worktree 的 `flag_gems` 代码。

- **禁止**运行 `pip install -e .` 或任何形式的 `pip install flag-gems`
- **所有命令**必须在工作目录 `{{WORK_DIR}}` 下执行
- **GPU 指定**：所有涉及 GPU 的命令（pytest、python -c 中 import torch 等）必须加上 `CUDA_VISIBLE_DEVICES={{GPU_ID}}` 前缀
- 运行测试时使用：`CUDA_VISIBLE_DEVICES={{GPU_ID}} {{PYTHON_PATH}} -m pytest ...`

### ⚠️ 重要：修复 flag_gems 导入路径

**问题**：当前环境中 `flag_gems` 以 editable 模式全局安装于 `/root/FlagGems/src/`，通过 `_flag_gems_editable` import hook 拦截导入。即使 `sys.path.insert(0, 'src')` 指向 worktree 的 src/，Python 仍会加载全局版本。

**解决方案**：本仓库 `auto_gen/` 目录下提供了修复脚本 `fix_worktree_import.py`，该脚本会：
1. 从 `sys.path` 移除全局 `/root/FlagGems` 路径
2. 移除 `_flag_gems_editable` import hook
3. 自动检测 worktree 根目录并插入 `sys.path` 最前端
4. 清除 `flag_gems` 缓存

执行任何涉及 `import flag_gems` 的命令时，都必须通过此脚本。用法如下：

```bash
# 方式 A：在 python -c 中使用（-c 模式）
cd {{WORK_DIR}}
{{PYTHON_PATH}} /root/baai-internship/auto_gen/fix_worktree_import.py -c "import flag_gems; print(flag_gems.__file__)"

# 方式 B：运行 pytest（--pytest 模式）
cd {{WORK_DIR}}
{{PYTHON_PATH}} /root/baai-internship/auto_gen/fix_worktree_import.py --pytest tests/test_{{OPERATOR}}.py -m {{OPERATOR}} -vs --log-cli-level=DEBUG
```

> ⚠️ **注意**：必须 `cd {{WORK_DIR}}` 后再执行，脚本依赖 CWD 检测 worktree 根目录。不要在命令中额外 `sys.path.insert`，脚本已处理所有路径。

## 燧原(Enflame)后端说明

**通用算子**已存在于 `src/flag_gems/ops/` 中（在 master 分支上）。

**燧原特化算子**需要创建在按架构分目录的路径下：`src/flag_gems/runtime/backend/_enflame/{{ARCH}}/ops/`。

> ⚠️ **与沐曦/天数后端不同**：燧原后端**按 GCU 架构分目录**（`gcu300/ops/`、`gcu400/ops/`），本任务的目标架构是 **{{ARCH}}**。请只在 `{{ARCH}}/ops/` 下创建和注册算子，不要动其他架构目录。

运行时，`runtime.replace_customized_ops()` 会根据实际检测到的 GCU 架构，自动用对应架构的燧原特化版本替换通用版本。

## FlagGems 项目结构（燧原后端相关）

```
src/flag_gems/
├── __init__.py              # _FULL_CONFIG 注册表（通用算子）
├── ops/                     # 通用算子实现（已存在，不动）
│   ├── __init__.py
│   ├── add.py
│   └── ...
└── runtime/
    └── backend/_enflame/
        ├── __init__.py                  # VendorDescriptor(vendor=enflame, device=gcu)
        ├── core_shapes.yaml
        ├── tune_configs.yaml
        ├── heuristics_config_utils.py
        ├── fused/                       # 融合算子（按架构再分）
        ├── gcu300/                      # gcu300 架构特化实现
        │   ├── tune_configs.yaml
        │   ├── utils/                   # 本地工具（pointwise_dynamic 等）
        │   └── ops/
        │       ├── __init__.py          # 在此文件注册特化算子
        │       ├── abs.py               # 参考实现
        │       ├── add.py
        │       ├── addmm.py
        │       ├── amax.py
        │       └── ...                  # 在此创建 {{OPERATOR}}.py（当 ARCH=gcu300）
        └── gcu400/                      # gcu400 架构特化实现
            ├── utils/
            └── ops/
                └── ...
tests/                                   # 测试文件（每算子一个独立文件，通常已存在）
├── test_<operator>.py                   # 如 test_relu.py；特化时复用，一般无需新建
└── accuracy_utils.py                    # 共享工具（from . import accuracy_utils as utils）
benchmark/                               # benchmark 文件（每算子一个独立文件，通常已存在）
├── test_<operator>.py                   # 如 test_relu.py；特化时复用
├── base.py                              # UnaryPointwiseBenchmark 等基类
└── consts.py                            # FLOAT_DTYPES 等常量
pytest.ini                               # 配置 pythonpath = src
```

## 燧原(Enflame)硬件约束 ⚠️

燧原 GCU 与 NVIDIA GPU 有以下重要差异，实现时**必须**注意：

1. **不支持 fp64（double）**：`fp64_enabled=False`。不要使用 `torch.float64`，测试也不要用 double 类型。
2. **不支持 int64**：`int64_enabled=False`。如果算子输入可能是 `torch.int64`，需要在算子内部转成 `torch.int32` 计算，再转回原 dtype（参考 `abs.py` 的处理方式）。
3. **架构差异**：gcu300 不支持部分算子（如 `to_copy`, `copy_`），实现前先确认目标架构 `{{ARCH}}` 是否支持。

## 执行步骤

请严格按照以下步骤执行：

### Step 1: 了解算子语义

运行以下命令了解 `{{OPERATOR}}` 的 PyTorch 接口：

```bash
CUDA_VISIBLE_DEVICES={{GPU_ID}} {{PYTHON_PATH}} -c "
import torch
for module_path in ['torch.{{OPERATOR}}', 'torch.nn.functional.{{OPERATOR}}']:
    try:
        fn = eval(module_path)
        help(fn)
        break
    except:
        pass
"
```

同时查阅 `torch.ops.aten` 中的 schema：

```bash
CUDA_VISIBLE_DEVICES={{GPU_ID}} {{PYTHON_PATH}} -c "
import torch
for op in dir(torch.ops.aten):
    if '{{OPERATOR}}' in op.lower():
        fn = getattr(torch.ops.aten, op)
        if hasattr(fn, 'default'):
            print(f'{op}: {fn.default._schema}')
"
```

**注意**：先查看 `src/flag_gems/runtime/backend/_enflame/{{ARCH}}/ops/` 中是否已有 `{{OPERATOR}}.py` 或同类型算子的燧原特化代码，优先参考。如果已存在同名算子，说明可能只需完善，请先阅读现有实现。

### Step 2: 阅读现有关键参考代码

燧原特化算子的常用模式（参考已有实现 `abs.py`, `add.py`, `addmm.py`, `amax.py`）：

1. **Import 规范**（注意：燧原使用**本地 utils**，不是 `flag_gems.utils`）：
```python
import logging

import torch
import triton
import triton.language as tl

from ..utils.pointwise_dynamic import pointwise_dynamic

logger = logging.getLogger(
    f'flag_gems.runtime.backend._enflame.{{ARCH}}.ops.{__name__.split(".")[-1]}'
)
```

> ⚠️ **关键差异**：燧原后端从架构目录下的 `..utils.pointwise_dynamic` 导入 `pointwise_dynamic`，**不要**用 `from flag_gems.utils import pointwise_dynamic`。其他工具（如 `libentry`、`tune` 相关）也优先看 `{{ARCH}}/utils/` 下是否有本地版本。

> **注意：logger 命名用燧原后端专用写法（含 `{{ARCH}}` 真实模块路径），不是主文件夹的 `getLogger(__name__)`**。vendor 后端经替换系统加载时 `__name__` 可能不以 `flag_gems.` 开头，用显式全路径才能正确挂到 `flag_gems` 根 logger。

2. **Logger 使用 `GEMS_ENFLAME` 前缀**：
```python
def abs(A):
    logger.debug("GEMS_ENFLAME ABS")
    ...
```

3. **int64 处理**（燧原不支持 int64，参考 `abs.py`）：
```python
def abs(A):
    logger.debug("GEMS_ENFLAME ABS")
    return_type = A.dtype
    if A.dtype == torch.int64:
        A = A.to(torch.int32)
    return abs_func(A).to(return_type)
```

4. **通用点式操作使用本地 `pointwise_dynamic`**：
```python
@pointwise_dynamic(promotion_methods=[(0, "COMPLEX_TO_FLOAT")])
@triton.jit
def abs_func(x):
    return tl.abs(x)
```

5. **跨后端兼容**：**禁止**直接调用 `tl.extra.cuda.libdevice`，这在非 NVIDIA 后端上会崩溃。优先使用 Triton 内置函数或本地 utils 提供的 shim。

### Step 3: 实现燧原特化算子代码

在 `src/flag_gems/runtime/backend/_enflame/{{ARCH}}/ops/{{OPERATOR}}.py` 创建算子实现。

**要求：**
- 参考已有燧原算子的代码风格（`abs.py`, `add.py`, `addmm.py`, `amax.py`）
- 必须有 `import logging` 和燧原后端专用 logger 命名 `logger = logging.getLogger(f'flag_gems.runtime.backend._enflame.{{ARCH}}.ops.{__name__.split(".")[-1]}')`（**不是** `getLogger(__name__)`）
- 从 `..utils.pointwise_dynamic` 导入 `pointwise_dynamic`（本地版本）
- 函数名遵循已有燧原命名规范（如 `{{OPERATOR}}`、`{{OPERATOR}}_`、`{{OPERATOR}}_func`）
- Logger 使用 `"GEMS_ENFLAME ..."` 前缀（全大写算子名）
- **必须**处理 int64 输入（转 int32 计算再转回），不支持 fp64
- **禁止**直接调用 `tl.extra.cuda.libdevice`

### Step 3.5: 验证真实 Triton 实现 ⚠️

**必须检查**：你的实现必须真正使用 Triton kernel，不能只是调用 torch 函数。

运行以下命令验证：
```bash
grep -E "@triton|def .*_func|@pointwise_dynamic|@libentry" src/flag_gems/runtime/backend/_enflame/{{ARCH}}/ops/{{OPERATOR}}.py
```

如果输出为空或只有 import，说明你没有真正实现 Triton kernel，需要重写。

**禁止**：
- 直接调用 `torch.xxx` 作为计算主体（允许调用 torch.tensor 创建输入、int64→int32 转换）
- 只有 import triton 但不使用
- 包装器函数直接透传到 torch

**允许**：
- 使用 `pointwise_dynamic` 装饰器
- 手写 `@triton.jit` kernel
- 调用 `tl.` 函数

如果验证失败，**必须重写**算子实现，不能跳过此步骤。

### Step 4: 注册燧原特化算子

**仅需**在 `src/flag_gems/runtime/backend/_enflame/{{ARCH}}/ops/__init__.py` 中注册。

燧原的注册风格是**直接 import**（不是维护 `__all__` append），参考现有条目：

```python
from .{{OPERATOR}} import {{OPERATOR}}, {{OPERATOR}}_  # 按实际导出的函数名
```

**按字母顺序**插入到已有 import 语句之间。

**注意**：**不需要**修改 `src/flag_gems/ops/__init__.py`，也**不需要**修改 `src/flag_gems/__init__.py` 的 `_FULL_CONFIG`。燧原后端通过 `runtime.replace_customized_ops()` 按架构自动替换。

### Step 5: 使用已有测试验证（不写新测试）

燧原特化算子覆盖的是**通用层已有算子**（在 `src/flag_gems/ops/` 中），因此该算子对应的测试文件 `tests/test_{{OPERATOR}}.py` **通常已经存在**。本步骤的目标是**用已有测试来验证**你的燧原特化实现，而**不是**编写新测试。

先确认测试文件是否存在：

```bash
ls {{WORK_DIR}}/tests/test_{{OPERATOR}}.py
```

- **如果存在**（绝大多数情况）：无需编写任何测试，直接进入 Step 6 运行它。
- **如果缺失**（极少数情况）：参考 `tests/test_relu.py` 的写法新建 `tests/test_{{OPERATOR}}.py`，注意：
  - 通过 `from . import accuracy_utils as utils` 导入共享工具，使用时加 `utils.` 前缀（如 `utils.POINTWISE_SHAPES`、`utils.FLOAT_DTYPES`、`utils.to_reference`、`utils.gems_assert_close`）。
  - 每个变体用 `@pytest.mark.<变体名>` 标记（如 `@pytest.mark.{{OPERATOR}}`）。
  - 对精确运算（如 floor、round），使用 `utils.gems_assert_equal` 而非 `utils.gems_assert_close`。

> ⚠️ **燧原约束**：测试**不要**使用 `torch.float64`（不支持 fp64）。如果算子涉及整数，用 `torch.int32` 而非 `torch.int64`（燧原不支持 int64），或依赖算子内部的 int64→int32 转换但避免用 int64 作为参考。

### Step 6: 运行 accuracy 测试

**必须在工作目录 `{{WORK_DIR}}` 下运行**。

> ⚠️ **重要**：由于 `flag_gems` 以 editable 模式全局安装，直接 `import flag_gems` 会加载全局版本而非 worktree 版本。必须使用 `fix_worktree_import.py`（参见上面的"修复 flag_gems 导入路径"章节）。

**正确运行测试的方式**（使用 fix_worktree_import.py 的 `--pytest` 模式）：

```bash
cd {{WORK_DIR}}
CUDA_VISIBLE_DEVICES={{GPU_ID}} {{PYTHON_PATH}} /root/baai-internship/auto_gen/fix_worktree_import.py --pytest tests/test_{{OPERATOR}}.py -m {{OPERATOR}} -vs --log-cli-level=DEBUG
```

**验证算子被调用**：在测试输出中检查是否出现了类似 `GEMS_ENFLAME {{OPERATOR}}` 的 DEBUG 日志。

**验证导入正确性**（使用 `-c` 模式）：
```bash
cd {{WORK_DIR}}
CUDA_VISIBLE_DEVICES={{GPU_ID}} {{PYTHON_PATH}} /root/baai-internship/auto_gen/fix_worktree_import.py -c "import flag_gems; print(flag_gems.__file__)"
# 必须显示 worktree 路径，非 /root/FlagGems/
```

### Step 7: 运行 benchmark

燧原特化算子复用**已存在**的 `benchmark/test_{{OPERATOR}}.py`（通常已存在，如 `benchmark/test_relu.py`），**无需**编写新的 benchmark。该文件基于 `from . import base, consts`（如 `base.UnaryPointwiseBenchmark`、`consts.FLOAT_DTYPES`），并已按算子名标记 `@pytest.mark.{{OPERATOR}}`。

运行 benchmark（必须在工作目录下，使用 fix_worktree_import.py）：

```bash
cd {{WORK_DIR}}
CUDA_VISIBLE_DEVICES={{GPU_ID}} {{PYTHON_PATH}} /root/baai-internship/auto_gen/fix_worktree_import.py --pytest benchmark/test_{{OPERATOR}}.py -m {{OPERATOR}} -vs
```

> ⚠️ **注意**：特化实现至少不能比通用实现差；如果性能反而下降，需重新优化。

benchmark 输出格式示例：
```
Operator: {{OPERATOR}}  Performance Test (dtype=torch.float16, mode=kernel,level=comprehensive)
SUCCESS    <torch_latency_ms>    <gems_latency_ms>    <speedup>    <gems_gbps>    [<shape>]
SUCCESS    ...
```

请从输出中提取每一行 `SUCCESS` 的数据，按 dtype 分组记录到最终 JSON 中。

**性能优化指导，最大优化次数30次**：
- 如果所有 shape 的加速比都 >= 0.8，**无需优化**，直接输出结果
- 如果有任何 shape 加速比 < 0.8，**必须尝试优化**：
  1. 分析瓶颈：检查 kernel 的 block 大小、num_warps、是否使用了 autotuning
  2. 参考同类型高性能燧原算子的实现，以及 `{{ARCH}}/utils/` 下的 codegen/config 工具
  3. 参考应用优化技术：
     - 添加 `@triton.autotune` 装饰器，测试不同配置
     - 调整 `BLOCK_SIZE`、`num_warps`（燧原有 `enflame_heuristics_for_num_warps` 等启发式）
     - 对 reduction 算子优化 reduce 维度的大小
  4. 重新运行 benchmark 验证优化效果
  5. 如果优化后仍未达到 0.8，但比初始版本有提升，可以接受当前最佳结果

### Step 7.5: 提交代码

**当 accuracy 测试通过、benchmark 也已运行后**，将改动一次性提交到当前 worktree 的分支。
燧原特化通常**只改**特化实现和其注册文件（不动通用层、不写新测试）：

```bash
cd {{WORK_DIR}}
git add -A
git commit -m "Add {{OPERATOR}} enflame {{ARCH}} specialized operator implementation"
```

**【禁止 AI 署名】** commit message **只能**包含上面 `-m` 指定的内容。**严禁**添加任何形式的
AI 署名或生成标记，包括但不限于 `Co-Authored-By: Claude ...`、`Generated with Claude Code`、
`🤖` 等 trailer。提交后请用 `git log -1 --format=%B` 复查，确认 message 中不含任何此类内容。

### Step 8: 输出结果

在所有步骤完成后，你**必须**输出以下 JSON 格式的最终结果。用 ````json` 和 ```` ` 代码块包裹：

```json
{
  "operator": "{{OPERATOR}}",
  "arch": "{{ARCH}}",
  "status": "success 或 failed",
  "accuracy_passed": true/false,
  "files_created": [
    "src/flag_gems/runtime/backend/_enflame/{{ARCH}}/ops/{{OPERATOR}}.py"
  ],
  "files_modified": [
    "src/flag_gems/runtime/backend/_enflame/{{ARCH}}/ops/__init__.py"
  ],
  "implementation_mode": "pointwise_dynamic 或 manual_kernel 或 autograd_function",
  "test_results": {
    "total": 12,
    "passed": 12,
    "failed": 0,
    "test_command": "python -m pytest tests/test_{{OPERATOR}}.py -m {{OPERATOR}} -vs"
  },
  "benchmark_results": {
    "benchmark_command": "python -m pytest benchmark/test_{{OPERATOR}}.py -m {{OPERATOR}} -vs",
    "data": [
      {
        "dtype": "torch.float16",
        "shape": "[1024, 1024]",
        "torch_latency_ms": 0.056,
        "gems_latency_ms": 0.057,
        "speedup": 0.987
      }
    ]
  },
  "error_message": "null 或错误描述",
  "notes": "燧原 {{ARCH}} 特化算子实现"
}
```

**注意**：`benchmark_results.data` 数组中应包含 benchmark 输出中**每一行 SUCCESS** 的数据。如果 benchmark 运行失败或没有输出，`data` 可以为空数组 `[]`。

## 重要约束

1. **正确性优先**：必须通过 accuracy 测试
2. **代码风格**：严格遵循燧原已有算子代码风格（本地 utils import、`GEMS_ENFLAME` logger 前缀）
3. **架构隔离**：只在 `{{ARCH}}/ops/` 下创建和注册，不要动其他架构目录
4. **硬件约束**：不支持 fp64；不支持 int64（需 int64→int32 转换）
5. **复用已有测试**：特化算子覆盖的是通用层已有算子，优先复用已存在的 `tests/test_{{OPERATOR}}.py` 和 `benchmark/test_{{OPERATOR}}.py`，不新写测试；仅当独立测试文件确实缺失时才参考 `test_relu.py` 新建
6. **跨后端兼容**：禁止直接调用 `tl.extra.cuda.libdevice`
7. **字母顺序**：所有注册必须严格按字母顺序插入
8. **最终代码保留**：无论成功失败，都保留修改的代码在 worktree 中
9. **不要删除或修改已有算子代码和测试**（包括通用算子和燧原已有算子）
10. **JSON 结果必须输出**：即使失败也要输出 JSON，标明 status 为 failed
11. **禁止 pip install**：不要运行 `pip install -e .` 或任何安装命令
12. **工作目录**：所有命令必须在 `{{WORK_DIR}}` 下执行
13. **禁止写临时文件**：不要将测试或代码写到 `/tmp` 或其他临时目录
