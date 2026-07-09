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
{{PYTHON_PATH}} /root/baai-internship/auto_gen/fix_worktree_import.py --pytest tests/TEST_FILE.py -m {{OPERATOR}} -vs --log-cli-level=DEBUG
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

logger = logging.getLogger(__name__)
```

> ⚠️ **关键差异**：燧原后端从架构目录下的 `..utils.pointwise_dynamic` 导入 `pointwise_dynamic`，**不要**用 `from flag_gems.utils import pointwise_dynamic`。其他工具（如 `libentry`、`tune` 相关）也优先看 `{{ARCH}}/utils/` 下是否有本地版本。

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
- 必须有 `import logging` 和 `logger = logging.getLogger(__name__)`
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

### Step 5: 编写 accuracy 测试

**在 FlagGems 标准测试文件中添加测试用例**，不要写到 `/tmp` 或其他地方。

根据算子类型，选择对应的测试文件：
- 一元 pointwise → `tests/test_unary_pointwise_ops.py`
- 二元 pointwise → `tests/test_binary_pointwise_ops.py`
- reduction → `tests/test_reduction_ops.py`
- norm → `tests/test_norm_ops.py`
- 其他 → `tests/test_special_ops.py`

**先阅读对应测试文件**，了解现有测试的模式和使用的工具函数（如 `POINTWISE_SHAPES`, `FLOAT_DTYPES`, `to_reference`, `gems_assert_close`, `gems_assert_equal` 等），然后在文件末尾追加新的测试函数。

> ⚠️ **燧原约束**：测试**不要**使用 `torch.float64`（不支持 fp64）。如果算子涉及整数，用 `torch.int32` 而非 `torch.int64`（燧原不支持 int64），或依赖算子内部的 int64→int32 转换但避免用 int64 作为参考。

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
- 如果算子支持整数类型（如 mul, pow），额外测试 `INT_DTYPES`（注意用 int32）

**复杂算子**（涉及多步计算、数值稳定性、或模型推理场景）如 layernorm, cross_entropy, nll_loss：
- 使用**模型推理场景 shape**（如 attention shape `(batch, heads, seq, seq)`、embedding shape `(batch, seq, hidden_dim)`）
- 全面测试**极端输入**：全零、全相同值、含 nan/inf、one-hot 分布
- 测试所有 **API 变体**（如 softmax 的 `dtype` 参数、loss 函数的 `reduction` 参数）
- 测试**边界情况**：标量 tensor `()`、零尺寸 tensor `(5, 0, 0)`、单元素 `(1,)`

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

**验证算子被调用**：在测试输出中检查是否出现了类似 `GEMS_ENFLAME {{OPERATOR}}` 的 DEBUG 日志。

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
git commit --author="taooo <gumptao2997@gmail.com>" -m "Add {{OPERATOR}} enflame {{ARCH}} specialized operator implementation"
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

**pointwise benchmark 模板**（添加到 `forward_operations` 列表中）：
```python
("{{OPERATOR}}", torch.{{OPERATOR}}, FLOAT_DTYPES),
```

运行 benchmark（同样必须在工作目录下，使用 fix_worktree_import.py）：

```bash
cd {{WORK_DIR}}
CUDA_VISIBLE_DEVICES={{GPU_ID}} {{PYTHON_PATH}} /root/baai-internship/auto_gen/fix_worktree_import.py --pytest benchmark/<benchmark_file>.py -m {{OPERATOR}} -vs
```

> ⚠️ **注意**：`<benchmark_file>.py` 中已有按算子名标记的 `@pytest.mark.xxx`，直接使用 `-m {{OPERATOR}}` 即可筛选。

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
    "src/flag_gems/runtime/backend/_enflame/{{ARCH}}/ops/__init__.py",
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
  "notes": "燧原 {{ARCH}} 特化算子实现"
}
```

**注意**：`benchmark_results.data` 数组中应包含 benchmark 输出中**每一行 SUCCESS** 的数据。如果 benchmark 运行失败或没有输出，`data` 可以为空数组 `[]`。

## 重要约束

1. **正确性优先**：必须通过 accuracy 测试
2. **代码风格**：严格遵循燧原已有算子代码风格（本地 utils import、`GEMS_ENFLAME` logger 前缀）
3. **架构隔离**：只在 `{{ARCH}}/ops/` 下创建和注册，不要动其他架构目录
4. **硬件约束**：不支持 fp64；不支持 int64（需 int64→int32 转换）
5. **标准测试**：测试和 benchmark 必须写入 FlagGems 标准文件中
6. **跨后端兼容**：禁止直接调用 `tl.extra.cuda.libdevice`
7. **字母顺序**：所有注册必须严格按字母顺序插入
8. **最终代码保留**：无论成功失败，都保留修改的代码在 worktree 中
9. **不要删除或修改已有算子代码和测试**（包括通用算子和燧原已有算子）
10. **JSON 结果必须输出**：即使失败也要输出 JSON，标明 status 为 failed
11. **禁止 pip install**：不要运行 `pip install -e .` 或任何安装命令
12. **工作目录**：所有命令必须在 `{{WORK_DIR}}` 下执行
13. **禁止写临时文件**：不要将测试或代码写到 `/tmp` 或其他临时目录
