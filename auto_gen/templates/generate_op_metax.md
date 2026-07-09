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
{{PYTHON_PATH}} /root/baai-internship/auto_gen/fix_worktree_import.py --pytest tests/TEST_FILE.py -m {{OPERATOR}} -vs --log-cli-level=DEBUG
```

> ⚠️ **注意**：必须 `cd {{WORK_DIR}}` 后再执行，脚本依赖 CWD 检测 worktree 根目录。不要在命令中额外 `sys.path.insert`，脚本已处理所有路径。

## 沐曦(Metax)后端说明

**通用算子**已存在于 `src/flag_gems/ops/` 中（在 master 分支上）。

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
tests/                                   # 标准测试文件
├── test_unary_pointwise_ops.py
├── test_binary_pointwise_ops.py
├── test_reduction_ops.py
├── test_norm_ops.py
├── test_blas_ops.py
├── test_special_ops.py
└── accuracy_utils.py
benchmark/                               # 标准 benchmark 文件
├── test_unary_pointwise_perf.py
├── test_binary_pointwise_perf.py
├── test_reduction_perf.py
└── ...
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

logger = logging.getLogger("flag_gems." + __name__)
```

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
- 必须有 `import logging` 和 `logger = logging.getLogger("flag_gems." + __name__)`
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

### Step 5: 编写 accuracy 测试

**在 FlagGems 标准测试文件中添加测试用例**，不要写到 `/tmp` 或其他地方。

根据算子类型，选择对应的测试文件：
- 一元 pointwise → `tests/test_unary_pointwise_ops.py`
- 二元 pointwise → `tests/test_binary_pointwise_ops.py`
- reduction → `tests/test_reduction_ops.py`
- norm → `tests/test_norm_ops.py`
- 其他 → `tests/test_special_ops.py`

**先阅读对应测试文件**，了解现有测试的模式和使用的工具函数（如 `POINTWISE_SHAPES`, `FLOAT_DTYPES`, `to_reference`, `gems_assert_close`, `gems_assert_equal` 等），然后在文件末尾追加新的测试函数。

**一元 pointwise 测试模板**：
```python
@pytest.mark.{{OPERATOR}}
@pytest.mark.parametrize("shape", POINTWISE_SHAPES)
@pytest.mark.parametrize("dtype", FLOAT_DTYPES)
def test_accuracy_{{OPERATOR}}(shape, dtype):
    inp = torch.randn(shape, dtype=dtype, device=flag_gems.device)
    ref_inp = to_reference(inp)
    ref_out = torch.{{OPERATOR}}(ref_inp)
    with flag_gems.use_gems():
        res_out = torch.{{OPERATOR}}(inp)
    gems_assert_close(res_out, ref_out, dtype)
```

**二元 pointwise 测试模板**：
```python
@pytest.mark.{{OPERATOR}}
@pytest.mark.parametrize("shape", POINTWISE_SHAPES)
@pytest.mark.parametrize("dtype", FLOAT_DTYPES)
def test_accuracy_{{OPERATOR}}(shape, dtype):
    inp1 = torch.randn(shape, dtype=dtype, device=flag_gems.device)
    inp2 = torch.randn(shape, dtype=dtype, device=flag_gems.device)
    ref_inp1 = to_reference(inp1)
    ref_inp2 = to_reference(inp2)
    ref_out = torch.{{OPERATOR}}(ref_inp1, ref_inp2)
    with flag_gems.use_gems():
        res_out = torch.{{OPERATOR}}(inp1, inp2)
    gems_assert_close(res_out, ref_out, dtype)
```

#### 测试深度指导

根据算子的计算复杂度，选择合适的测试深度。不要对所有算子都套用最简单的模板，也不要对简单算子过度测试。

**简单算子**（纯逐元素、无 reduce、无特殊参数）如 abs, ceil, neg, relu, bitwise_not：
- 使用标准 `POINTWISE_SHAPES` + `FLOAT_DTYPES`（或 `INT_DTYPES`）即可
- 使用 `gems_assert_close`（或 `gems_assert_equal`）统一容差
- 1 个测试函数 + 1 个 inplace 测试函数（如果有 inplace 版本）

**中等算子**（涉及 reduce、广播、dim 参数、或多输入）如 sum, softmax, mul, pow, index_put：
- 除标准 shape 外，**额外测试大 reduce 维度 shape**（如 `(1, 8192)`, `(32, 50257)`）
- 如果算子有 `dim` 参数，**测试不同 dim 值**（dim=0, dim=1, dim=-1），不要只测默认值
- 对 reduction 算子，额外测试**极端输入**：全零 tensor、含 `inf`/`-inf` 的 tensor
- 按 dtype 使用**不同容差**：float32 用严格容差 `(rtol=1e-5, atol=1e-5)`，float16 用 `(rtol=1e-3, atol=1e-3)`，bfloat16 用 `(rtol=2e-2, atol=2e-2)`
- 如果算子支持整数类型（如 mul, pow），额外测试 `INT_DTYPES`

**复杂算子**（涉及多步计算、数值稳定性、或模型推理场景）如 layernorm, cross_entropy, nll_loss, multi_margin_loss：
- 使用**模型推理场景 shape**（如 attention shape `(batch, heads, seq, seq)`、embedding shape `(batch, seq, hidden_dim)`）
- 全面测试**极端输入**：全零、全相同值、含 nan/inf、one-hot 分布
- 测试所有 **API 变体**（如 softmax 的 `dtype` 参数、loss 函数的 `reduction` 参数）
- 测试**边界情况**：标量 tensor `()`、零尺寸 tensor `(5, 0, 0)`、单元素 `(1,)`
- 可以组织为多个 TestClass，每个 class 测试一个场景

**注意**：上面只是模板，你需要根据算子的实际接口和语义调整（输入数据生成方式、断言方式等）。对于精确运算（如 floor, round），应使用 `gems_assert_equal` 而非 `gems_assert_close`。

### Step 6: 运行 accuracy 测试

**必须在工作目录 `{{WORK_DIR}}` 下运行**。

> ⚠️ **重要**：由于 `flag_gems` 以 editable 模式全局安装，直接 `import flag_gems` 会加载全局版本而非 worktree 版本。必须使用 `fix_worktree_import.py`（参见上面的"修复 flag_gems 导入路径"章节）。

**正确运行测试的方式**（使用 fix_worktree_import.py 的 `--pytest` 模式）：

```bash
cd {{WORK_DIR}}
CUDA_VISIBLE_DEVICES={{GPU_ID}} {{PYTHON_PATH}} /root/baai-internship/auto_gen/fix_worktree_import.py --pytest tests/TEST_FILE.py -m {{OPERATOR}} -vs --log-cli-level=DEBUG
```

请将 `TEST_FILE.py` 替换为对应的测试文件名（如 `test_binary_pointwise_ops.py`）。

**验证算子被调用**：在测试输出中检查是否出现了类似 `METAX GEMS {{OPERATOR}}` 的 DEBUG 日志。

**验证导入正确性**（使用 `-c` 模式）：
```bash
cd {{WORK_DIR}}
CUDA_VISIBLE_DEVICES={{GPU_ID}} {{PYTHON_PATH}} /root/baai-internship/auto_gen/fix_worktree_import.py -c "import flag_gems; print(flag_gems.__file__)"
# 必须显示 worktree 路径，非 /root/FlagGems/
```

### Step 6.5: 提交代码

**当 accuracy 测试全部通过后**，立即将所有改动提交到当前 worktree 的分支：

```bash
cd {{WORK_DIR}}
git add -A
git commit --author="taooo <gumptao2997@gmail.com>" -m "Add {{OPERATOR}} metax specialized operator implementation"
```

**必须在运行 benchmark 之前提交**，确保代码变更不会丢失。

### Step 7: 编写 benchmark 并运行

**在 FlagGems 标准 benchmark 文件中添加 benchmark 条目**。

根据算子类型，选择对应的 benchmark 文件：
- 一元 pointwise → `benchmark/test_unary_pointwise_perf.py`
- 二元 pointwise → `benchmark/test_binary_pointwise_perf.py`
- reduction → `benchmark/test_reduction_perf.py`
- 其他 → `benchmark/test_special_perf.py`

**先阅读对应 benchmark 文件**，了解 `forward_operations` 列表的格式，然后将新算子追加到列表末尾。

**一元 pointwise benchmark 模板**（添加到 `forward_operations` 列表中）：
```python
("{{OPERATOR}}", torch.{{OPERATOR}}, FLOAT_DTYPES),
```

**二元 pointwise benchmark 模板**（添加到 `forward_operations` 列表中）：
```python
("{{OPERATOR}}", torch.{{OPERATOR}}, FLOAT_DTYPES),
```

运行 benchmark（同样必须在工作目录下，使用 fix_worktree_import.py）：

```bash
cd {{WORK_DIR}}
CUDA_VISIBLE_DEVICES={{GPU_ID}} {{PYTHON_PATH}} /root/baai-internship/auto_gen/fix_worktree_import.py --pytest benchmark/<benchmark_file>.py -m {{OPERATOR}} -vs
```

> ⚠️ **注意**：`<benchmark_file>.py` 中已有按算子名标记的 `@pytest.mark.xxx`，直接使用 `-m {{OPERATOR}}` 即可筛选。

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
    "src/flag_gems/runtime/backend/_metax/ops/__init__.py",
    "tests/test_xxx_ops.py",
    "benchmark/test_xxx_perf.py"
  ],
  "implementation_mode": "pointwise_dynamic 或 manual_kernel 或 autograd_function",
  "test_results": {
    "total": 12,
    "passed": 12,
    "failed": 0,
    "test_command": "python -m pytest tests/test_xxx_ops.py -m {{OPERATOR}} -vs"
  },
  "benchmark_results": {
    "benchmark_command": "python -m pytest benchmark/test_xxx_perf.py -m {{OPERATOR}} -vs",
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
3. **标准测试**：测试和 benchmark 必须写入 FlagGems 标准文件中
4. **跨后端兼容**：禁止直接调用 `tl.extra.cuda.libdevice`，必须使用 `tl_extra_shim` 或 Triton 内置函数
5. **字母顺序**：所有注册必须严格按字母顺序插入
6. **最终代码保留**：无论成功失败，都保留修改的代码在 worktree 中
7. **不要删除或修改已有算子代码和测试**（包括通用算子和沐曦已有算子）
8. **JSON 结果必须输出**：即使失败也要输出 JSON，标明 status 为 failed
9. **禁止 pip install**：不要运行 `pip install -e .` 或任何安装命令
10. **工作目录**：所有命令必须在 `{{WORK_DIR}}` 下执行
11. **禁止写临时文件**：不要将测试或代码写到 `/tmp` 或其他临时目录
