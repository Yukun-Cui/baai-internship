# FlagGems 算子生成任务

你需要为 FlagGems 项目实现一个新的 Triton 算子。

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

## FlagGems 项目结构

```
src/flag_gems/
├── __init__.py              # _FULL_CONFIG 注册表
├── ops/
│   ├── __init__.py          # import 所有算子
│   └── <operator>.py        # 各算子实现
├── utils/
│   ├── pointwise_dynamic.py # pointwise 装饰器
│   └── triton_lang_extension.py  # tl_extra_shim 跨后端兼容层
└── runtime/
    └── backend/_nvidia/
        └── tune_configs.yaml  # autotuning 配置
tests/
├── test_<operator>.py            # 每个算子一个独立测试文件（如 test_relu.py）
├── accuracy_utils.py             # 共享工具：POINTWISE_SHAPES, FLOAT_DTYPES, gems_assert_close 等
│                                 #   （通过 `from . import accuracy_utils as utils` 导入，带 utils. 前缀使用）
└── conftest.py
benchmark/
├── test_<operator>.py            # 每个算子一个独立 benchmark 文件（如 test_relu.py）
├── base.py                       # UnaryPointwiseBenchmark 等基类
├── consts.py                     # FLOAT_DTYPES 等常量
└── ...
conf/
└── operators.yaml                # 算子目录：每个变体一条，需带 KernelGen 标签
pytest.ini                        # 配置 pythonpath = src，自动导入 worktree 的代码
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

### Step 2: 确定实现模式 & 阅读参考代码

FlagGems 有三种主要实现模式，根据算子类型选择：

**模式 A: pointwise_dynamic（逐元素操作）**
适用于：一元/二元逐元素操作（如 abs, relu, add, mul）
参考文件：`src/flag_gems/ops/abs.py`, `src/flag_gems/ops/ceil.py`, `src/flag_gems/ops/add.py`

```python
import logging
import triton
import triton.language as tl
from flag_gems.utils import pointwise_dynamic

logger = logging.getLogger(__name__)

@pointwise_dynamic(promotion_methods=[(0, "DEFAULT")])
@triton.jit
def op_func(x):
    return ...  # Triton 标量逻辑

def op(A):
    logger.debug("GEMS OP")
    return op_func(A)

def op_(A):  # in-place 版本（如果需要）
    logger.debug("GEMS OP_")
    op_func(A, out0=A)
    return A
```

promotion_methods 常见值：
- `(0, "DEFAULT")` — 默认类型提升
- `(0, "INT_TO_FLOAT")` — 整数输入提升为浮点（三角函数等）
- `(0, "COMPLEX_TO_FLOAT")` — 复数输入返回浮点（abs 等）
- `(0, 1, "DEFAULT")` — 二元操作默认提升
- `(0, 1, "ALWAYS_BOOL")` — 输出始终为 bool（比较操作）

**模式 B: 手写 Triton kernel（reduction/scan/index 等）**
适用于：涉及跨元素计算的操作
参考文件：`src/flag_gems/ops/sum.py`, `src/flag_gems/ops/softmax.py`

**模式 C: 多 kernel + autograd.Function（需要反向传播）**
适用于：有前向+反向的操作
参考文件：`src/flag_gems/ops/layernorm.py`, `src/flag_gems/ops/rms_norm.py`

请阅读 2-3 个与目标算子**同类型**的已有实现作为参考。

**重要：跨后端兼容性**
- **禁止**直接调用 `tl.extra.cuda.libdevice`，这在非 NVIDIA 后端上会崩溃
- **必须**使用 `tl_extra_shim` 提供的跨后端兼容函数（如 `tl_extra_shim.nearbyint`, `tl_extra_shim.pow` 等）
- 参考 `src/flag_gems/ops/isnan.py` 和 `src/flag_gems/ops/ceil.py` 的写法
- 如果需要的数学函数在 `tl_extra_shim` 中不存在，使用 Triton 内置的 `tl.math` 或 `tl.` 函数

### Step 3: 实现算子代码

在 `src/flag_gems/ops/{{OPERATOR}}.py` 创建算子实现。

**要求：**
- 遵循已有算子的代码风格
- 必须有 `import logging` 和 `logger = logging.getLogger(__name__)`
- 函数名遵循已有命名规范
- 如果是 pointwise 操作，优先使用 `pointwise_dynamic`
- 对 float16/bfloat16 输入，做 `.to(tl.float32)` 计算后 `.to(x.dtype)` 转回（参考 ceil.py 的写法）

### Step 3.5: 验证真实 Triton 实现 ⚠️

**必须检查**：你的实现必须真正使用 Triton kernel，不能只是调用 torch 函数。

运行以下命令验证：
```bash
grep -E "@triton|def op_func|@pointwise_dynamic" src/flag_gems/ops/{{OPERATOR}}.py
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

### Step 4: 注册算子

1. **在 `src/flag_gems/ops/__init__.py` 中添加 import 和 `__all__` 条目：**
   按字母顺序插入。注意字母顺序是严格的，例如 `sigmoid` < `signbit` < `silu` < `sin`。

2. **在 `src/flag_gems/__init__.py` 的 `_FULL_CONFIG` 中添加注册项：**
   按字母顺序插入，格式为：
   ```python
   ("aten_op_name", function_name),
   ```
   aten op name 需要与 Step 1 中查到的 schema 名一致。

3. **在 `conf/operators.yaml` 中为每个变体注册元数据条目（⚠️ 必须，否则校验不通过）：**

   为你注册的**每一个 ATen 变体**（如 `{{OPERATOR}}`、`{{OPERATOR}}_`、`{{OPERATOR}}.out`）各加一条，
   按 `id` 字母顺序插入。**`labels` 中必须包含 `KernelGen` 标签**（标记本工具生成的 Triton kernel），
   否则完整性校验会失败并触发返工。参考同类算子（如 `abs`、`acosh`、`ceil`）的写法：

   ```yaml
   - id: {{OPERATOR}}
     description: Triton kernel implementation for {{OPERATOR}}.
     for:
       - {{OPERATOR}}
     labels:
       - aten
       - KernelGen        # ⚠️ 必须保留此标签

   - id: {{OPERATOR}}_       # 仅当存在 inplace 变体时
     description: The in-place version of `{{OPERATOR}}()`.
     for:
       - {{OPERATOR}}_
     labels:
       - aten
       - KernelGen

   - id: {{OPERATOR}}_out    # 仅当存在 out 变体时，注意 for 用 `.out` 后缀
     description: A variant of {{OPERATOR}}() that writes the result into the out tensor.
     for:
       - {{OPERATOR}}.out
     labels:
       - aten
       - KernelGen
   ```

   验证 YAML 语法：
   ```bash
   cd {{WORK_DIR}}
   {{PYTHON_PATH}} -c "import yaml; yaml.safe_load(open('conf/operators.yaml'))"
   ```

### Step 5: 编写 accuracy 测试

**在独立的按算子命名的测试文件 `tests/test_{{OPERATOR}}.py` 中编写测试**（这是仓库当前约定，
每个算子一个文件，如 `tests/test_relu.py`、`tests/test_abs.py`），不要写到共享类别文件、`/tmp` 或其他地方。

**先阅读一个同类算子的现有测试文件**（如 `tests/test_relu.py`），了解 import 与工具函数的用法。
注意工具函数通过 `from . import accuracy_utils as utils` 导入，使用时**带 `utils.` 前缀**
（如 `utils.POINTWISE_SHAPES`、`utils.FLOAT_DTYPES`、`utils.to_reference`、`utils.gems_assert_close`）。

⚠️ **完整性校验要求**：`tests/test_{{OPERATOR}}.py` 中**每个 ATen 变体都必须有对应的 `@pytest.mark.<变体名>`**
（如 `@pytest.mark.{{OPERATOR}}`、`@pytest.mark.{{OPERATOR}}_`），缺少会导致校验失败并触发返工。

**一元 pointwise 测试模板**（参考 `tests/test_relu.py`）：

```python
import pytest
import torch

import flag_gems

from . import accuracy_utils as utils


@pytest.mark.{{OPERATOR}}
@pytest.mark.parametrize("shape", utils.POINTWISE_SHAPES)
@pytest.mark.parametrize("dtype", utils.FLOAT_DTYPES)
def test_{{OPERATOR}}(shape, dtype):
    res_inp = torch.randn(shape, dtype=dtype, device=flag_gems.device)
    ref_inp = utils.to_reference(res_inp)

    ref_out = torch.{{OPERATOR}}(ref_inp)
    with flag_gems.use_gems():
        res_out = torch.{{OPERATOR}}(res_inp)

    utils.gems_assert_close(res_out, ref_out, dtype)


@pytest.mark.{{OPERATOR}}_       # 仅当存在 inplace 变体时
@pytest.mark.parametrize("shape", utils.POINTWISE_SHAPES)
@pytest.mark.parametrize("dtype", utils.FLOAT_DTYPES)
def test_{{OPERATOR}}_(shape, dtype):
    res_inp = torch.randn(shape, dtype=dtype, device=flag_gems.device)
    ref_inp = utils.to_reference(res_inp.clone())

    ref_out = ref_inp.{{OPERATOR}}_()
    with flag_gems.use_gems():
        res_out = res_inp.{{OPERATOR}}_()

    utils.gems_assert_close(res_out, ref_out, dtype)
```

**二元 pointwise 测试模板**（参考 `tests/test_add.py` 等）：

```python
@pytest.mark.{{OPERATOR}}
@pytest.mark.parametrize("shape", utils.POINTWISE_SHAPES)
@pytest.mark.parametrize("dtype", utils.FLOAT_DTYPES)
def test_{{OPERATOR}}(shape, dtype):
    inp1 = torch.randn(shape, dtype=dtype, device=flag_gems.device)
    inp2 = torch.randn(shape, dtype=dtype, device=flag_gems.device)
    ref_inp1 = utils.to_reference(inp1)
    ref_inp2 = utils.to_reference(inp2)

    ref_out = torch.{{OPERATOR}}(ref_inp1, ref_inp2)
    with flag_gems.use_gems():
        res_out = torch.{{OPERATOR}}(inp1, inp2)

    utils.gems_assert_close(res_out, ref_out, dtype)
```

<!-- [v2 新增] 测试深度指导 - 基于测试组反馈 2026-04-14 -->
#### 测试深度指导

根据算子的计算复杂度，选择合适的测试深度。不要对所有算子都套用最简单的模板，也不要对简单算子过度测试。

**简单算子**（纯逐元素、无 reduce、无特殊参数）如 abs, ceil, neg, relu, bitwise_not：
- 使用标准 `utils.POINTWISE_SHAPES` + `utils.FLOAT_DTYPES`（或 `utils.INT_DTYPES`）即可
- 使用 `utils.gems_assert_close`（或 `utils.gems_assert_equal`）统一容差
- 1 个测试函数 + 1 个 inplace 测试函数（如果有 inplace 版本）

**中等算子**（涉及 reduce、广播、dim 参数、或多输入）如 sum, softmax, mul, pow, index_put：
- 除标准 shape 外，**额外测试大 reduce 维度 shape**（如 `(1, 8192)`, `(32, 50257)`）
- 如果算子有 `dim` 参数，**测试不同 dim 值**（dim=0, dim=1, dim=-1），不要只测默认值
- 对 reduction 算子，额外测试**极端输入**：全零 tensor、含 `inf`/`-inf` 的 tensor
- 按 dtype 使用**不同容差**：float32 用严格容差 `(rtol=1e-5, atol=1e-5)`，float16 用 `(rtol=1e-3, atol=1e-3)`，bfloat16 用 `(rtol=2e-2, atol=2e-2)`
- 如果算子支持整数类型（如 mul, pow），额外测试 `utils.INT_DTYPES`

**复杂算子**（涉及多步计算、数值稳定性、或模型推理场景）如 layernorm, cross_entropy, nll_loss, multi_margin_loss：
- 使用**模型推理场景 shape**（如 attention shape `(batch, heads, seq, seq)`、embedding shape `(batch, seq, hidden_dim)`）
- 全面测试**极端输入**：全零、全相同值、含 nan/inf、one-hot 分布
- 测试所有 **API 变体**（如 softmax 的 `dtype` 参数、loss 函数的 `reduction` 参数）
- 测试**边界情况**：标量 tensor `()`、零尺寸 tensor `(5, 0, 0)`、单元素 `(1,)`
- 可以组织为多个 TestClass，每个 class 测试一个场景
<!-- [v2 新增结束] -->

**注意**：上面只是模板，你需要根据算子的实际接口和语义调整（输入数据生成方式、断言方式等）。对于精确运算（如 floor, round），应使用 `utils.gems_assert_equal` 而非 `utils.gems_assert_close`。

### Step 6: 运行 accuracy 测试

**必须在工作目录 `{{WORK_DIR}}` 下运行**（pytest.ini 的 `pythonpath = src` 会自动让 Python 导入当前 worktree 的 `flag_gems`）。

使用标准 pytest 命令，用 `-m` 指定算子 mark，**必须加 `--log-cli-level=DEBUG`** 以验证你的算子确实被调用了（你实现的算子中有 `logger.debug("GEMS XXX")` 日志）：

```bash
cd {{WORK_DIR}}
CUDA_VISIBLE_DEVICES={{GPU_ID}} {{PYTHON_PATH}} -m pytest tests/test_{{OPERATOR}}.py -m {{OPERATOR}} -vs --log-cli-level=DEBUG 2>&1
```

如果算子有多个变体（inplace / out），用 `-m` 的 or 表达式一并运行：
```bash
CUDA_VISIBLE_DEVICES={{GPU_ID}} {{PYTHON_PATH}} -m pytest tests/test_{{OPERATOR}}.py -m "{{OPERATOR}} or {{OPERATOR}}_" -vs --log-cli-level=DEBUG
```

**验证算子被调用**：在测试输出中检查是否出现了类似 `GEMS {{OPERATOR}}` 的 DEBUG 日志。如果没有出现，说明你的算子没有被正确注册或调用，需要检查 Step 4 的注册步骤。

**验证导入正确性**：如果需要确认导入的是 worktree 代码，可以运行：
```bash
CUDA_VISIBLE_DEVICES={{GPU_ID}} {{PYTHON_PATH}} -c "import sys; sys.path.insert(0, 'src'); import flag_gems; print(flag_gems.__file__)"
```
输出应包含 `{{WORK_DIR}}/src/flag_gems`。

**如果测试失败：**
1. 分析失败原因（类型不匹配、精度问题、逻辑错误）
2. 如果 DEBUG 日志中没有 `GEMS` 输出，检查算子注册是否正确
3. 修复 `src/flag_gems/ops/{{OPERATOR}}.py` 或测试代码
4. 重新运行测试，直到所有测试通过

### Step 7: 编写 benchmark 并运行

**在独立的按算子命名的 benchmark 文件 `benchmark/test_{{OPERATOR}}.py` 中编写 benchmark**（仓库当前约定，
每个算子一个文件，如 `benchmark/test_relu.py`），不要写到共享 perf 文件。

**先阅读一个同类算子的现有 benchmark 文件**（如 `benchmark/test_relu.py`），了解 `base` 与 `consts` 的用法。
工具通过 `from . import base, consts` 导入，一元 pointwise 用 `base.UnaryPointwiseBenchmark`。

⚠️ **完整性校验要求**：`benchmark/test_{{OPERATOR}}.py` 中**每个 ATen 变体都必须有对应的 `@pytest.mark.<变体名>`**，
缺少会导致校验失败并触发返工。

**一元 pointwise benchmark 模板**（参考 `benchmark/test_relu.py`）：
```python
import pytest
import torch

from . import base, consts


@pytest.mark.{{OPERATOR}}
def test_{{OPERATOR}}():
    bench = base.UnaryPointwiseBenchmark(
        op_name="{{OPERATOR}}", torch_op=torch.{{OPERATOR}}, dtypes=consts.FLOAT_DTYPES
    )
    bench.run()


@pytest.mark.{{OPERATOR}}_       # 仅当存在 inplace 变体时
def test_{{OPERATOR}}_inplace():
    bench = base.UnaryPointwiseBenchmark(
        op_name="{{OPERATOR}}_",
        torch_op=torch.{{OPERATOR}}_,
        dtypes=consts.FLOAT_DTYPES,
        is_inplace=True,
    )
    bench.run()
```

运行 benchmark（同样必须在工作目录下）：
```bash
cd {{WORK_DIR}}
CUDA_VISIBLE_DEVICES={{GPU_ID}} {{PYTHON_PATH}} -m pytest benchmark/test_{{OPERATOR}}.py -m {{OPERATOR}} -vs 2>&1
```

**解析 benchmark 输出**：benchmark 输出格式为：
```
Operator: {{OPERATOR}}  Performance Test (dtype=torch.float16, mode=kernel,level=comprehensive)
SUCCESS    <torch_latency_ms>    <gems_latency_ms>    <speedup>    <gems_gbps>    [<shape>]
SUCCESS    ...
Operator: {{OPERATOR}}  Performance Test (dtype=torch.float32, ...)
SUCCESS    ...
```

请从输出中提取每一行 `SUCCESS` 的数据，按 dtype 分组记录到最终 JSON 中。

**性能优化指导**：
- 如果所有 shape 的加速比都 >= 0.8，**无需优化**，直接输出结果
- 如果有任何 shape 加速比 < 0.8，**必须尝试优化**：
  1. 分析瓶颈：检查 kernel 的 block 大小、num_warps、是否使用了 autotuning
  2. 参考同类型高性能算子的实现（如 `src/flag_gems/ops/add.py`、`src/flag_gems/ops/softmax.py`）
  3. 应用优化技术：
     - 添加 `@triton.autotune` 装饰器，测试不同配置
     - 调整 `BLOCK_SIZE`、`num_warps`
     - 使用 `tl.store` 的 `boundary_check` 参数避免分支
     - 对 reduction 算子优化 reduce 维度的大小
  4. 重新运行 benchmark 验证优化效果
  5. 如果优化后仍未达到 0.8，但比初始版本有提升，可以接受当前最佳结果

### Step 7.5: 提交代码

**当 accuracy 测试通过、benchmark 也已写好并运行后**，将所有改动（实现、测试、benchmark、
`operators.yaml` 及两个 `__init__.py` 注册）一次性提交到当前 worktree 的分支：

```bash
cd {{WORK_DIR}}
git add -A
git commit --author="taooo <gumptao2997@gmail.com>" -m "Add {{OPERATOR}} operator implementation, tests and benchmark"
```

提交前请确认以下文件都已包含在内（缺失会导致完整性校验失败）：
- `src/flag_gems/ops/{{OPERATOR}}.py`（实现）
- `src/flag_gems/ops/__init__.py`、`src/flag_gems/__init__.py`（注册）
- `conf/operators.yaml`（每个变体一条，含 `KernelGen` 标签）
- `tests/test_{{OPERATOR}}.py`、`benchmark/test_{{OPERATOR}}.py`（每个变体都有 `@pytest.mark`）

### Step 8: 输出结果

**【必须】** 在所有步骤完成后，你**必须**输出以下 JSON 格式的最终结果。用 ````json` 和 ```` ` 代码块包裹，这是解析你输出的唯一方式，不输出 JSON 将导致结果丢失：

```json
{
  "operator": "{{OPERATOR}}",
  "status": "success 或 failed",
  "accuracy_passed": true/false,
  "files_created": [
    "src/flag_gems/ops/{{OPERATOR}}.py",
    "tests/test_{{OPERATOR}}.py",
    "benchmark/test_{{OPERATOR}}.py"
  ],
  "files_modified": [
    "src/flag_gems/ops/__init__.py",
    "src/flag_gems/__init__.py",
    "conf/operators.yaml"
  ],
  "aten_ops_registered": ["{{OPERATOR}}", "{{OPERATOR}}_", "{{OPERATOR}}.out"],
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
  "notes": "实现说明或特殊处理"
}
```

**注意**：`benchmark_results.data` 数组中应包含 benchmark 输出中**每一行 SUCCESS** 的数据。如果 benchmark 运行失败或没有输出，`data` 可以为空数组 `[]`。

**⚠️ `aten_ops_registered` 必须准确**：只列出你**实际注册**的 ATen 变体（如仅有 base 就只写 `["{{OPERATOR}}"]`，
不要写出不存在的变体）。完整性校验会用这个字段核对 `operators.yaml` 与 `tests/`、`benchmark/` 中的 `@pytest.mark`，
字段与实际不符会触发不必要的返工。

## 重要约束

1. **正确性优先**：必须通过 accuracy 测试
2. **代码风格**：严格遵循 FlagGems 已有代码风格
3. **标准测试**：测试和 benchmark 必须写入 FlagGems 标准文件中，使用标准 pytest 命令运行
4. **跨后端兼容**：禁止直接调用 `tl.extra.cuda.libdevice`，必须使用 `tl_extra_shim` 或 Triton 内置函数
5. **字母顺序**：所有注册（import、`__all__`、`_FULL_CONFIG`）必须严格按字母顺序插入
6. **最终代码保留**：无论成功失败，都保留修改的代码在 worktree 中
7. **不要删除或修改已有算子的代码和测试**
8. **JSON 结果必须输出**：即使失败也要输出 JSON，标明 status 为 failed
9. **禁止 pip install**：不要运行 `pip install -e .` 或任何安装命令，pytest.ini 已处理导入
10. **工作目录**：所有命令必须在 `{{WORK_DIR}}` 下执行，不要 cd 到其他目录
11. **禁止写临时文件**：不要将测试或代码写到 `/tmp` 或其他临时目录
