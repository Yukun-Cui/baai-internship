# FlagGems 沐曦(Metax)算子特化生成任务

你需要为 FlagGems 项目实现一个沐曦后端的特化 Triton 算子。

## 任务信息

- **算子名称**: {{OPERATOR}}
- **GPU ID**: {{GPU_ID}}
- **工作目录**: {{WORK_DIR}} (这是一个 git worktree)
- **Python 路径**: {{PYTHON_PATH}}

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

## 沐曦(Metax)后端说明

**通用算子**已存在于 `src/flag_gems/ops/` 中（在 infra-ci 分支上）。

**沐曦特化算子**需要创建在 `src/flag_gems/runtime/backend/_metax/ops/` 下。

运行时，`runtime.replace_customized_ops()` 会自动用沐曦特化版本替换通用版本。

## FlagGems 项目结构（沐曦后端相关）

```
src/flag_gems/
├── __init__.py              # _FULL_CONFIG 注册表（通用算子）
├── ops/                     # 通用算子实现（已存在，不动）
│   ├── __init__.py
│   ├── add.py
│   └── ...
└── runtime/
    └── backend/_metax/
        ├── __init__.py
        ├── tune_configs.yaml
        └── ops/
            ├── __init__.py              # 在此文件注册沐曦特化算子
            ├── sigmoid.py              # 参考实现
            ├── addmm.py
            ├── amax.py
            ├── zeros.py
            ├── zeros_like.py
            ├── ones.py
            ├── ones_like.py
            ├── full.py
            ├── full_like.py
            ├── bmm.py
            ├── mm.py
            ├── arange.py
            ├── groupnorm.py
            └── ...                      # 在此创建 {{OPERATOR}}.py
tests/                                   # 测试文件（每算子一个独立文件，通常已存在）
├── test_<operator>.py                   # 如 test_relu.py；特化时复用，一般无需新建
└── accuracy_utils.py                    # 共享工具（from . import accuracy_utils as utils）
benchmark/                               # benchmark 文件（每算子一个独立文件，通常已存在）
├── test_<operator>.py                   # 如 test_relu.py；特化时复用
├── base.py                              # UnaryPointwiseBenchmark 等基类
└── consts.py                            # FLOAT_DTYPES 等常量
pytest.ini                               # 配置 pythonpath = src
```

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

**注意**：查看 `src/flag_gems/runtime/backend/_metax/ops/` 中是否已有同类型算子的沐曦特化代码，优先参考。

### Step 2: 阅读现有关键参考代码

沐曦特化算子的常用模式（参考已有实现 `sigmoid.py`, `addmm.py`, `amax.py`）：

1. **Import 规范**：
```python
import logging
import torch
import triton
import triton.language as tl

from flag_gems import runtime
from flag_gems.runtime import torch_device_fn
from flag_gems.utils import libentry, pointwise_dynamic
from flag_gems.utils import triton_lang_extension as tle  # 重要！

logger = logging.getLogger(
    f'flag_gems.runtime.backend._metax.ops.{__name__.split(".")[-1]}'
)
```

> **注意：logger 命名用沐曦后端专用写法（与 mthreads 主线一致），不是 `getLogger(__name__)` 或 `"flag_gems." + __name__`**。vendor 后端经替换系统加载时 `__name__` 可能不以 `flag_gems.` 开头，用显式全路径才能正确挂到 `flag_gems` 根 logger。

2. **使用 `tle.program_id()` 代替 `tl.program_id()`** — 跨后端兼容

3. **使用 `torch_device_fn.device()` 管理设备**：
```python
with torch_device_fn.device(mat1.device):
    my_kernel[grid](...)
```

4. **Logger 使用 `"METAX"` 前缀**：
```python
logger.debug("METAX GEMS ADDMM")
```

5. **使用 `libentry` 装饰器**（用于 tuner 控制）：
```python
@libentry()
@triton.jit
def my_kernel(...):
```

6. **使用 `runtime.get_tuned_config()` 获取 tune 配置**：
```python
@libtuner(
    configs=runtime.get_tuned_config("op_name"),
    key=["M", "N", "K"],
)
```

7. **通用点式操作使用 `pointwise_dynamic`**（如 sigmoid）：
```python
@pointwise_dynamic(promotion_methods=[(0, "INT_TO_FLOAT")])
@triton.jit
def my_pointwise_op(x):
    ...
```

### Step 3: 实现沐曦特化算子代码

在 `src/flag_gems/runtime/backend/_metax/ops/{{OPERATOR}}.py` 创建算子实现。

**要求：**
- 参考已有沐曦算子的代码风格（`sigmoid.py`, `addmm.py`, `amax.py`）
- 必须有 `import logging` 和沐曦后端专用 logger 命名 `logger = logging.getLogger(f'flag_gems.runtime.backend._metax.ops.{__name__.split(".")[-1]}')`（**不是** `getLogger(__name__)`）
- 函数名遵循已有沐曦命名规范
- 使用 `tle.program_id()` 代替 `tl.program_id()`
- Logger 使用 `"METAX GEMS ..."` 前缀
- **禁止**直接调用 `tl.extra.cuda.libdevice`，这在非 NVIDIA 后端上会崩溃
- **必须**使用 `tl_extra_shim` 提供的跨后端兼容函数

### Step 3.5: 验证真实 Triton 实现 ⚠️

**必须检查**：你的实现必须真正使用 Triton kernel，不能只是调用 torch 函数。

运行以下命令验证：
```bash
grep -E "@triton|def .*_func|@pointwise_dynamic|@libentry" src/flag_gems/runtime/backend/_metax/ops/{{OPERATOR}}.py
```

如果输出为空或只有 import，说明你没有真正实现 Triton kernel，需要重写。

**禁止**：
- 直接调用 `torch.xxx` 作为计算主体（允许调用 torch.tensor 创建输入）
- 只有 import triton 但不使用
- 包装器函数直接透传到 torch

**允许**：
- 使用 `pointwise_dynamic` 装饰器
- 手写 `@triton.jit` kernel
- 调用 `tl.` 或 `tl_extra_shim` 函数

如果验证失败，**必须重写**算子实现，不能跳过此步骤。

### Step 4: 注册沐曦特化算子

**仅需**在 `src/flag_gems/runtime/backend/_metax/ops/__init__.py` 中注册：

```python
from .{{OPERATOR}} import op_func_name

__all__ = [
    ...
    "op_func_name",
]
```

按字母顺序插入。

**注意**：**不需要**修改 `src/flag_gems/ops/__init__.py`，也**不需要**修改 `src/flag_gems/__init__.py` 的 `_FULL_CONFIG`。沐曦后端通过 `runtime.replace_customized_ops()` 自动替换。

### Step 5: 使用已有测试验证（不写新测试）

沐曦特化算子**覆盖的是通用层已存在的算子**，其测试文件通常已存在于 `tests/test_{{OPERATOR}}.py`。
本步骤的目标是**用已有测试验证特化实现的正确性**，**不要新写或修改测试文件**。

先确认该算子的测试是否存在：

```bash
ls {{WORK_DIR}}/tests/test_{{OPERATOR}}.py
```

- **如果存在**：直接进入 Step 6，用它验证。
- **如果不存在**（少数通用层算子未附带独立测试）：参考同类算子的独立测试文件
  `tests/test_relu.py` 新建 `tests/test_{{OPERATOR}}.py`。注意工具函数通过
  `from . import accuracy_utils as utils` 导入、带 `utils.` 前缀使用
  （`utils.POINTWISE_SHAPES`、`utils.FLOAT_DTYPES`、`utils.to_reference`、`utils.gems_assert_close`），
  并为每个变体加 `@pytest.mark.<变体名>`。对精确运算（如 floor, round）用
  `utils.gems_assert_equal` 而非 `utils.gems_assert_close`。

### Step 6: 运行 accuracy 测试

**必须在工作目录 `{{WORK_DIR}}` 下运行**。

> ⚠️ **重要**：由于 `flag_gems` 以 editable 模式全局安装，直接 `import flag_gems` 会加载全局版本而非 worktree 版本。必须使用 `fix_worktree_import.py`（参见上面的"修复 flag_gems 导入路径"章节）。

**正确运行测试的方式**（使用 fix_worktree_import.py 的 `--pytest` 模式，直接跑该算子的独立测试文件）：

```bash
cd {{WORK_DIR}}
CUDA_VISIBLE_DEVICES={{GPU_ID}} {{PYTHON_PATH}} /root/baai-internship/auto_gen/fix_worktree_import.py --pytest tests/test_{{OPERATOR}}.py -m {{OPERATOR}} -vs --log-cli-level=DEBUG
```

**验证算子被调用**：在测试输出中检查是否出现了类似 `METAX GEMS {{OPERATOR}}` 的 DEBUG 日志。
如果没有出现，说明沐曦特化版本没有被 `runtime.replace_customized_ops()` 正确替换，需检查 Step 4 的注册。

**验证导入正确性**（使用 `-c` 模式）：
```bash
cd {{WORK_DIR}}
CUDA_VISIBLE_DEVICES={{GPU_ID}} {{PYTHON_PATH}} /root/baai-internship/auto_gen/fix_worktree_import.py -c "import flag_gems; print(flag_gems.__file__)"
# 必须显示 worktree 路径，非 /root/FlagGems/
```

**如果测试失败**：分析原因 → 修复 `src/flag_gems/runtime/backend/_metax/ops/{{OPERATOR}}.py` → 重新运行，直到通过。

### Step 7: 运行 benchmark

沐曦特化算子复用已有的独立 benchmark 文件 `benchmark/test_{{OPERATOR}}.py`（通常已存在），
**不需要新写 benchmark**。运行它对比特化实现与通用实现的性能（在工作目录下，使用 fix_worktree_import.py）：

```bash
cd {{WORK_DIR}}
CUDA_VISIBLE_DEVICES={{GPU_ID}} {{PYTHON_PATH}} /root/baai-internship/auto_gen/fix_worktree_import.py --pytest benchmark/test_{{OPERATOR}}.py -m {{OPERATOR}} -vs
```

**特化实现至少不能比通用实现差**；如果性能反而下降，需重新优化。

**解析 benchmark 输出**：benchmark 输出格式为：
```
Operator: {{OPERATOR}}  Performance Test (dtype=torch.float16, mode=kernel,level=comprehensive)
SUCCESS    <torch_latency_ms>    <gems_latency_ms>    <speedup>    <gems_gbps>    [<shape>]
SUCCESS    ...
Operator: {{OPERATOR}}  Performance Test (dtype=torch.float32, ...)
SUCCESS    ...
```

请从输出中提取每一行 `SUCCESS` 的数据，按 dtype 分组记录到最终 JSON 中。

**性能优化指导，最大优化次数30次**：
- 如果所有 shape 的加速比都 >= 0.8，**无需优化**，直接输出结果
- 如果有任何 shape 加速比 < 0.8，**必须尝试优化**：
  1. 分析瓶颈：检查 kernel 的 block 大小、num_warps、是否使用了 autotuning
  2. 参考同类型高性能算子的实现（如 `src/flag_gems/ops/add.py`、`src/flag_gems/ops/softmax.py`）
  3. 参考应用优化技术：
     - 添加 `@triton.autotune` 装饰器，测试不同配置
     - 调整 `BLOCK_SIZE`、`num_warps`
     - 使用 `tl.store` 的 `boundary_check` 参数避免分支
     - 对 reduction 算子优化 reduce 维度的大小
  4. 重新运行 benchmark 验证优化效果
  5. 如果优化后仍未达到 0.8，但比初始版本有提升，可以接受当前最佳结果

### Step 7.5: 提交代码

**当 accuracy 测试通过、benchmark 也已运行后**，将改动一次性提交到当前 worktree 的分支。
沐曦特化通常**只改**特化实现和其注册文件（不动通用层、不写新测试）：

```bash
cd {{WORK_DIR}}
git add -A
git commit -m "Add {{OPERATOR}} metax specialized operator implementation"
```

**【禁止 AI 署名】** commit message **只能**包含上面 `-m` 指定的内容。**严禁**添加任何形式的
AI 署名或生成标记，包括但不限于 `Co-Authored-By: Claude ...`、`Generated with Claude Code`、
`🤖` 等 trailer。提交后请用 `git log -1 --format=%B` 复查，确认 message 中不含任何此类内容。

### Step 8: 输出结果

在所有步骤完成后，你**必须**输出以下 JSON 格式的最终结果。用 ````json` 和 ```` ` 代码块包裹：

```json
{
  "operator": "{{OPERATOR}}",
  "status": "success 或 failed",
  "accuracy_passed": true/false,
  "files_created": [
    "src/flag_gems/runtime/backend/_metax/ops/{{OPERATOR}}.py"
  ],
  "files_modified": [
    "src/flag_gems/runtime/backend/_metax/ops/__init__.py"
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
  "notes": "沐曦特化算子实现"
}
```

**注意**：`benchmark_results.data` 数组中应包含 benchmark 输出中**每一行 SUCCESS** 的数据。如果 benchmark 运行失败或没有输出，`data` 可以为空数组 `[]`。

## 重要约束

1. **正确性优先**：必须通过 accuracy 测试
2. **代码风格**：严格遵循沐曦已有算子代码风格
3. **复用已有测试**：特化算子覆盖的是通用层已有算子，优先复用已存在的 `tests/test_{{OPERATOR}}.py` 和 `benchmark/test_{{OPERATOR}}.py`，不新写测试；仅当独立测试文件确实缺失时才参考 `test_relu.py` 新建
4. **跨后端兼容**：禁止直接调用 `tl.extra.cuda.libdevice`，必须使用 `tl_extra_shim` 或 Triton 内置函数
5. **字母顺序**：所有注册必须严格按字母顺序插入
6. **最终代码保留**：无论成功失败，都保留修改的代码在 worktree 中
7. **不要删除或修改已有算子代码和测试**（包括通用算子和沐曦已有算子）
8. **JSON 结果必须输出**：即使失败也要输出 JSON，标明 status 为 failed
9. **禁止 pip install**：不要运行 `pip install -e .` 或任何安装命令
10. **工作目录**：所有命令必须在 `{{WORK_DIR}}` 下执行
11. **禁止写临时文件**：不要将测试或代码写到 `/tmp` 或其他临时目录
