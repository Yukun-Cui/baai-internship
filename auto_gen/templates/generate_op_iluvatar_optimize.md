# FlagGems 天数(Iluvatar)算子特化优化任务

你需要为 FlagGems 项目**优化**一个天数后端的特化算子。该算子已经过多轮自动生成但持续失败或加速比不达标（< 0.8），本次任务需要根据下方的**算子专属优化指导**采用针对性策略来解决问题。

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

## 天数(Iluvatar)后端说明

**通用算子**已存在于 `src/flag_gems/ops/` 中（在 master 分支上）。

**天数特化算子**需要创建在 `src/flag_gems/runtime/backend/_iluvatar/ops/` 下。

运行时，`runtime.replace_customized_ops()` 会自动用天数特化版本替换通用版本。

## FlagGems 项目结构（天数后端相关）

```
src/flag_gems/
├── __init__.py              # _FULL_CONFIG 注册表（通用算子）
├── ops/                     # 通用算子实现（已存在，不动）
│   ├── __init__.py
│   ├── add.py
│   └── ...
└── runtime/
    └── backend/_iluvatar/
        ├── __init__.py
        ├── tune_configs.yaml
        ├── heuristics_config_utils.py
        ├── op_black_list.yaml
        └── ops/
            ├── __init__.py              # 在此文件注册天数特化算子
            ├── div.py                   # 参考实现（唯一已有特化算子）
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

## ⚠️ 算子专属优化指导（必读）

本算子 `{{OPERATOR}}` 在天数GPU上有已知的特殊问题。**你必须先阅读本节，按照指导实施，不要重复之前失败的方案。**

### 天数硬件原生 API（ixformer）

天数GPU提供了 `ixformer` 原生加速库（已安装在 `/usr/local/corex-4.4.0/lib64/python3/dist-packages/`），对于 attention 和 matmul 类算子，**使用 ixformer 原生 API 比 Triton kernel 性能更好**。

导入方式：
```python
import sys
sys.path.insert(0, '/usr/local/corex-4.4.0/lib64/python3/dist-packages/')
import ixformer
```

可用的关键 API：

**Flash Attention**：
```python
ixformer.flash_attn_func(q, k, v, dropout_p=0.0, softmax_scale=None, causal=False, return_attn_probs=False)
# q: (batch_size, seqlen, nheads, headdim)       torch.float16 / torch.bfloat16
# k: (batch_size, seqlen, nheads_k, headdim)     torch.float16 / torch.bfloat16
# v: (batch_size, seqlen, nheads_k, headdim)     torch.float16 / torch.bfloat16
# 返回: (batch_size, seqlen, nheads, headdim)
```

**融合 Matmul+Bias+Activation**：
```python
ixformer.act_bias_mm(mat1, mat2, bias=None, output=None, scale=1, act_type='none', trans_format='NN')
# mat1: [m, k] 或 [batch, m, k]    torch.float16
# mat2: [k, n] (NN格式) 或 [n, k] (TN格式)    torch.float16
# bias: [n]    torch.float16（当 act_type 不为 None 时 bias 不可为 None）
# act_type: 'silu' / 'gelu' / 'relu' / 'none'
# 返回: [m, n]    torch.float16
```

**矩阵乘法**：
```python
ixformer.mm(mat1, mat2)         # 基础矩阵乘法
ixformer.addmm(bias, mat1, mat2)  # addmm
ixformer.bmm(batch1, batch2)    # 批量矩阵乘法
```

---

### 算子：cross_attention / Cross_Attention

**已知问题**：之前4轮都使用 wrapper 委托给 FlagGems 的 `scaled_dot_product_attention` Triton kernel，但该 Triton kernel 在天数GPU上性能不足（加速比 0.5-0.7），这是底层 Triton kernel 的限制，不是 wrapper 的问题。`Cross_Attention` 之前超时（9600s），但 `cross_attention`（小写）已经成功（加速比 1.09）。

**必须使用的方案**：
- **直接使用基本 torch 操作实现 attention**：`torch.matmul` + `torch.softmax` + `torch.matmul`
- 注意输入格式：FlagGems attention 的 Q/K/V 是 `(batch, heads, seq, dim)` 格式
- 实现中需要 transpose 到 `(batch, seq, heads, dim)` 进行计算，再 transpose 回来
- **以下是已验证成功的 `cross_attention` 实现代码，直接参考**：

```python
import logging
import torch

logger = logging.getLogger("flag_gems." + __name__)

def cross_attention(query, key, value, attn_mask=None, dropout_p=0.0, is_causal=False, scale=None, enable_gqa=False):
    logger.debug("ILUVATAR GEMS CROSS_ATTENTION")
    if scale is None:
        softmax_scale = 1.0 / (query.shape[-1] ** 0.5)
    else:
        softmax_scale = scale
    # (batch, heads, seq, dim) -> (batch, seq, heads, dim)
    q = query.transpose(1, 2).contiguous()
    k = key.transpose(1, 2).contiguous()
    v = value.transpose(1, 2).contiguous()
    attn_weights = torch.matmul(q, k.transpose(-2, -1)) * softmax_scale
    if is_causal:
        mask = torch.triu(torch.ones(attn_weights.shape[-2], attn_weights.shape[-1], device=attn_weights.device, dtype=torch.bool), diagonal=1)
        attn_weights = attn_weights.masked_fill(mask, float("-inf"))
    attn_weights = torch.softmax(attn_weights, dim=-1)
    out = torch.matmul(attn_weights, v)
    return out.transpose(1, 2).contiguous()
```

**对于 `Cross_Attention`**：函数名改为大写即可，逻辑完全一致。注册时按照 `Cross_Attention` 名称注册。

**禁止使用的方案**：
- ❌ 调用 `flag_gems.ops.attention` 或 `scaled_dot_product_attention`（Triton kernel 在天数上性能不足）
- ❌ 使用 Triton 手写 attention kernel

**Benchmark baseline 策略**：
使用手写的等价 PyTorch 操作序列作为 baseline：
```python
def torch_cross_attention(q, k, v, softmax_scale=None):
    """手写 baseline：使用基本 torch 操作实现 cross attention"""
    if softmax_scale is None:
        softmax_scale = q.shape[-1] ** (-0.5)
    attn_weights = torch.matmul(q, k.transpose(-2, -1)) * softmax_scale
    attn_weights = torch.softmax(attn_weights, dim=-1)
    return torch.matmul(attn_weights, v)
```

---

### 算子：FlashDecoding

**已知问题**：之前使用 `ixformer.flash_attn_func` 实现，精度测试通过但加速比仅 0.32。根因分析：FlashDecoding 的 q_seq_len=1（解码阶段），本质上是**批量向量乘矩阵**（batched matrix-vector multiply），`torch.matmul` 在这种场景下已经是最优实现。`ixformer.flash_attn_func` 是为长序列设计的，在 q_seq_len=1 时有大量不必要的开销，反而比 `torch.matmul` 慢 3 倍。

**必须使用的方案**：
- **直接使用 `torch.matmul` + `torch.softmax` 实现 FlashDecoding**（和 cross_attention 类似的方案）
- q_seq_len=1 时这就是最优实现，不需要 flash attention
- 实现参考代码：
```python
import logging
import torch

logger = logging.getLogger("flag_gems." + __name__)

def flash_decoding_forward(q, k, v, out=None, alibi_slopes=None, p_dropout=0.0,
                           softmax_scale=None, is_causal=False, **kwargs):
    logger.debug("ILUVATAR GEMS FLASHDECODING")
    if softmax_scale is None:
        softmax_scale = 1.0 / (q.shape[-1] ** 0.5)
    # q: (batch, q_seq, heads, dim) -> (batch, heads, q_seq, dim)
    q_t = q.transpose(1, 2).contiguous()
    k_t = k.transpose(1, 2).contiguous()
    v_t = v.transpose(1, 2).contiguous()
    attn = torch.matmul(q_t, k_t.transpose(-2, -1)) * softmax_scale
    if is_causal:
        mask = torch.triu(torch.ones(attn.shape[-2], attn.shape[-1],
                          device=attn.device, dtype=torch.bool), diagonal=1)
        attn = attn.masked_fill(mask, float("-inf"))
    attn = torch.softmax(attn, dim=-1)
    out = torch.matmul(attn, v_t)
    out = out.transpose(1, 2).contiguous()  # -> (batch, q_seq, heads, dim)
    return out, q, k, v, None, None, None, None
```

**禁止使用的方案**：
- ❌ 使用 `ixformer.flash_attn_func`（在 q_seq_len=1 时比 torch.matmul 慢 3 倍）
- ❌ 使用 FlagGems 的 Triton attention kernel

**Benchmark baseline 策略**：
使用相同的 `torch.matmul` 操作序列作为 baseline。由于实现本身就是基于 torch.matmul，加速比预期接近 1.0。

---

### 算子：Matmul_Bias_Activation

**已知问题**：之前使用 Triton matmul kernel，但 autotune 配置不适配天数GPU架构，加速比仅 0.14-0.51。Triton 的 matmul 在天数上难以与 cuBLAS 级别的原生库竞争。

**必须使用的方案**：
- 使用 `ixformer.act_bias_mm(mat1, mat2, bias, act_type="gelu")` 实现融合的 matmul+bias+activation
- 支持的 activation 类型：`'silu'`, `'gelu'`, `'relu'`, `'none'`
- 仅支持 `float16`，对于 `float32` 输入需要先转换
- 当不需要 activation 时使用 `act_type='none'`，此时 bias 可以为 None

**禁止使用的方案**：
- ❌ 使用 Triton 手写 matmul kernel（性能远不如 ixformer 原生）
- ❌ 使用 `torch.nn.functional.linear` 作为 fallback

**Benchmark baseline 策略**：
```python
def torch_matmul_bias_activation(mat1, mat2, bias=None, act_type='gelu'):
    """手写 baseline"""
    out = torch.mm(mat1, mat2)
    if bias is not None:
        out = out + bias
    if act_type == 'gelu':
        out = torch.nn.functional.gelu(out)
    elif act_type == 'relu':
        out = torch.nn.functional.relu(out)
    elif act_type == 'silu':
        out = torch.nn.functional.silu(out)
    return out
```

---

### 算子：_fused_adam_

**已知问题**：`torch._fused_adam_` 在天数设备上不可用（报 `CUDA error: invalid device function`）。之前的实现虽然 Triton kernel 能工作，但 benchmark 无法获取 torch baseline，导致 speedup 数据为空或无意义。

**必须使用的方案**：
- 使用 Triton kernel 实现 Adam 优化器的核心逻辑（参数更新、动量、方差估计）
- 支持基本 Adam：bias correction、weight decay
- 测试可以放宽精度要求（float16 下 rtol=1e-2, atol=1e-2）

**Benchmark baseline 策略**：
使用手写的 PyTorch 等价操作序列作为 baseline（**不要**调用 `torch._fused_adam_`）：
```python
def torch_adam_baseline(params, grads, exp_avgs, exp_avg_sqs, step, lr, beta1, beta2, eps, weight_decay):
    """手写 Adam baseline，使用基本 torch 操作"""
    for p, g, m, v in zip(params, grads, exp_avgs, exp_avg_sqs):
        if weight_decay != 0:
            g = g + weight_decay * p
        m.mul_(beta1).add_(g, alpha=1 - beta1)
        v.mul_(beta2).addcmul_(g, g, value=1 - beta2)
        bias_correction1 = 1 - beta1 ** step
        bias_correction2 = 1 - beta2 ** step
        step_size = lr / bias_correction1
        denom = (v.sqrt() / (bias_correction2 ** 0.5)).add_(eps)
        p.addcdiv_(m, denom, value=-step_size)
```

---

### 算子：_nested_view_from_buffer_copy

**已知问题**：之前的实现误以为天数GPU上会 segfault，实际测试发现 `torch._nested_view_from_buffer_copy` **在天数GPU上完全正常工作**（PyTorch 2.7.1 + CoreX 4.4.0）。之前的 segfault 是由于传入的参数不正确（如 offsets 超出 buffer 范围）。因此之前所有 CPU fallback、clone+reshape 方案都是不必要的。

**必须使用的方案**：
- **直接调用 `torch._nested_view_from_buffer_copy`**，这在天数GPU上正常工作且性能极好（~0.02ms）
- 实现一个简单的 wrapper，添加 ILUVATAR GEMS 日志标记，然后委托给 torch 原生实现
- 示例实现：
```python
import logging
import torch
logger = logging.getLogger("flag_gems." + __name__)

def _nested_view_from_buffer_copy(self, nested_size, nested_strides, offsets):
    logger.debug("ILUVATAR GEMS _NESTED_VIEW_FROM_BUFFER_COPY")
    return torch._nested_view_from_buffer_copy(self, nested_size, nested_strides, offsets)
```

**禁止使用的方案**：
- ❌ CPU fallback（之前因为误判 segfault 使用的方案，性能极差）
- ❌ clone + reshape（不必要的替代方案）
- ❌ `bench.metrics = ["latency"]` 模式（不需要了，torch 原生可以正常作为 baseline）

**Benchmark baseline 策略**：
- 直接使用 `torch._nested_view_from_buffer_copy` 作为 baseline（标准做法）
- 加速比预期接近 1.0
- **测试参数注意**：确保 offsets 不超出 buffer 大小，nested_size 和 nested_strides 匹配。示例：
```python
buf = torch.randn(5000, device=device)
nested_size = torch.tensor([[50, 50], [50, 50]])
nested_strides = torch.tensor([[50, 1], [50, 1]])
offsets = torch.tensor([0, 2500])
```

---

### 算子：convolution

**已知问题**：之前的实现只对 1x1 卷积使用 Triton，一般卷积委托给 torch，但 Triton 的 1x1 卷积在天数上也不够快（加速比 0.68）。

**必须使用的方案**：
- **直接委托给 `torch.conv2d` / `torch.conv1d` / `torch.conv3d`**（torch 原生卷积在天数GPU上已经使用了硬件加速的 cuDNN 等价实现，性能接近最优）
- 不要试图用 Triton 重写通用卷积（Triton 不适合做通用卷积，需要 im2col 等复杂操作）
- 实现中添加 ILUVATAR GEMS 日志标记即可

**Benchmark baseline 策略**：
- 直接使用 `torch.convolution` 作为 baseline（标准做法）
- 由于实现本身就是委托 torch，加速比预期接近 1.0

---

### 算子：linalg_vander / special_erfc / grid_sampler_2d / _convert_weight_to_int4pack_for_cpu / __ixor__ / Paged_Attention / KV_Cache_Update

**已知问题**：这些算子在天数上C列记录为"成功"但没有输出加速比数值，说明之前的测试脚本跑通了但 benchmark 没有正确运行或记录。E列为空因为没有被选入特化列表。

**必须使用的方案**：
- 这些算子大部分是标准 PyTorch 算子，在天数上能正常运行
- 实现方式：创建一个简单的 wrapper，委托给 torch 原生实现，添加 ILUVATAR GEMS 日志标记
- **重点是确保 benchmark 能正确运行并输出 speedup 数据**
- 使用标准的 benchmark 框架，`torch.xxx` 作为 baseline

**注意事项**：
- `_convert_weight_to_int4pack_for_cpu` 是 CPU 算子，benchmark 在 CPU 上运行即可
- `Paged_Attention` 和 `KV_Cache_Update` 是推理场景算子，查看 `tests/test_attention_ops.py` 中的已有测试模式
- `__ixor__` 是位运算，测试用整数类型

---

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

**注意**：查看 `src/flag_gems/runtime/backend/_iluvatar/ops/` 中是否已有同类型算子的天数特化代码，优先参考。

### Step 2: 阅读现有关键参考代码

天数特化算子的常用模式（参考已有实现 `div.py`）：

1. **Import 规范**：
```python
import logging
import torch
import triton
import triton.language as tl

from flag_gems import runtime
from flag_gems.runtime import torch_device_fn
from flag_gems.utils import libentry, pointwise_dynamic, tl_extra_shim

logger = logging.getLogger("flag_gems." + __name__)
```

2. **使用 `torch_device_fn.device()` 管理设备**：
```python
with torch_device_fn.device(mat1.device):
    my_kernel[grid](...)
```

3. **Logger 使用 `"ILUVATAR"` 前缀**：
```python
logger.debug("ILUVATAR GEMS DIV")
```

4. **使用 `libentry` 装饰器**（用于 tuner 控制）：
```python
@libentry()
@triton.jit
def my_kernel(...):
```

5. **使用 `runtime.get_tuned_config()` 获取 tune 配置**：
```python
@libtuner(
    configs=runtime.get_tuned_config("op_name"),
    key=["M", "N", "K"],
)
```

6. **通用点式操作使用 `pointwise_dynamic`**（如 div）：
```python
@pointwise_dynamic(promotion_methods=[(0, 1, "INT_TO_FLOAT")])
@triton.jit
def my_pointwise_op(x, y):
    ...
```

7. **需要使用跨后端兼容函数时，使用 `tl_extra_shim`**：
```python
div_rn = tl_extra_shim.div_rn
div_rz = tl_extra_shim.div_rz
```

### Step 3: 实现天数特化算子代码

在 `src/flag_gems/runtime/backend/_iluvatar/ops/{{OPERATOR}}.py` 创建算子实现。

**要求：**
- 参考已有天数算子的代码风格（唯一参考：`div.py`）
- 必须有 `import logging` 和 `logger = logging.getLogger("flag_gems." + __name__)`
- 函数名遵循已有天数命名规范
- Logger 使用 `"ILUVATAR GEMS ..."` 前缀
- **禁止**直接调用 `tl.extra.cuda.libdevice`，这在非 NVIDIA 后端上会崩溃
- **必须**使用 `tl_extra_shim` 提供的跨后端兼容函数（如需要）
- 天数使用标准 Triton API，**不需要** `tle.program_id()`，直接使用 `tl.program_id()` 即可

### Step 3.5: 验证实现有效性 ⚠️

**必须检查**：你的实现必须使用真正的加速计算后端，不能只是简单调用 torch 函数。

运行以下命令验证：
```bash
grep -E "@triton|def .*_func|@pointwise_dynamic|@libentry|ixformer\." src/flag_gems/runtime/backend/_iluvatar/ops/{{OPERATOR}}.py
```

如果输出为空或只有 import，说明你没有使用加速实现，需要重写。

**禁止**：
- 只有 import 但不使用任何加速后端
- 对于 attention/matmul 类算子：调用 FlagGems 通用 `scaled_dot_product_attention`（在天数上性能不足）

**允许**（按优先级排序）：
1. 调用 `ixformer` 原生 API（attention、matmul类算子的首选方案）
2. 使用 `pointwise_dynamic` 装饰器
3. 手写 `@triton.jit` kernel
4. 调用 `tl.` 或 `tl_extra_shim` 函数
5. 对于 convolution：委托给 `torch.conv2d` 等（天数上已有硬件加速）

如果验证失败，**必须重写**算子实现，不能跳过此步骤。

### Step 4: 注册天数特化算子

**仅需**在 `src/flag_gems/runtime/backend/_iluvatar/ops/__init__.py` 中注册：

```python
from .{{OPERATOR}} import op_func_name

__all__ = [
    ...
    "op_func_name",
]
```

按字母顺序插入。

**注意**：**不需要**修改 `src/flag_gems/ops/__init__.py`，也**不需要**修改 `src/flag_gems/__init__.py` 的 `_FULL_CONFIG`。天数后端通过 `runtime.replace_customized_ops()` 自动替换。

### Step 5: 编写 accuracy 测试

**在 FlagGems 标准测试文件中添加测试用例**，不要写到 `/tmp` 或其他地方。

根据算子类型，选择对应的测试文件：
- 一元 pointwise → `tests/test_unary_pointwise_ops.py`
- 二元 pointwise → `tests/test_binary_pointwise_ops.py`
- reduction → `tests/test_reduction_ops.py`
- norm → `tests/test_norm_ops.py`
- 其他 → `tests/test_special_ops.py`

**先阅读对应测试文件**，了解现有测试的模式和使用的工具函数（如 `POINTWISE_SHAPES`, `FLOAT_DTYPES`, `to_reference`, `gems_assert_close`, `gems_assert_equal` 等），然后在文件末尾追加新的测试函数。

### ⚠️ 天数特有：pytest marker 大小写校验

在写测试函数时，**pytest marker 名称必须与代码中完全一致**。天数环境中 CSV 记录的命令可能存在大小写不匹配（如 `-m And` vs 实际 marker `and_op`），导致所有测试被跳过。

**在运行测试前，必须确认 marker 名称**：
```bash
grep "@pytest.mark.*{{OPERATOR}}" tests/TEST_FILE.py
```

确保 `-m` 参数与 grep 输出的 marker 名称**完全一致**（包括大小写和下划线）。

### ⚠️ 天数特有：杀残留进程

在运行测试前，清理**本 GPU 上**可能残留的卡死 Python 进程。**禁止使用 `killall -9 python`**，因为多任务并发时会杀掉其他 GPU 上正在运行的进程。

只杀占用当前 GPU {{GPU_ID}} 的残留进程：
```bash
# 只杀占用当前 GPU 的残留 python 进程，不影响其他 GPU 上的任务
for pid in $(ixsmi pmon -d 1 -i {{GPU_ID}} 2>/dev/null | awk 'NR>2 && $2!="-" {print $2}' | sort -u); do
    # 不杀 CC 自身进程树
    if [ "$pid" != "$$" ] && [ "$pid" != "$PPID" ]; then
        kill -9 "$pid" 2>/dev/null || true
    fi
done
```

如果 `ixsmi pmon` 不可用，可以跳过此步骤。残留的 CUDA 上下文会阻塞 GPU，但不应用全局 kill 解决。

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

#### 天数特有：杀占用当前 GPU 的残留进程（可选）

```bash
# 只杀占用当前 GPU 的残留 python 进程（不影响其他并发任务）
for pid in $(ixsmi pmon -d 1 -i {{GPU_ID}} 2>/dev/null | awk 'NR>2 && $2!="-" {print $2}' | sort -u); do
    if [ "$pid" != "$$" ] && [ "$pid" != "$PPID" ]; then
        kill -9 "$pid" 2>/dev/null || true
    fi
done
```

#### 确认 marker 名称（必须先执行）

```bash
grep "@pytest.mark.*{{OPERATOR}}" tests/TEST_FILE.py
```

#### 运行测试

**正确运行测试的方式**（使用 fix_worktree_import.py 的 `--pytest` 模式）：

```bash
cd {{WORK_DIR}}
CUDA_VISIBLE_DEVICES={{GPU_ID}} {{PYTHON_PATH}} /root/baai-internship/auto_gen/fix_worktree_import.py --pytest tests/TEST_FILE.py -m {{OPERATOR}} -vs --log-cli-level=DEBUG
```

请将 `TEST_FILE.py` 替换为对应的测试文件名（如 `test_binary_pointwise_ops.py`）。

**验证算子被调用**：在测试输出中检查是否出现了类似 `ILUVATAR GEMS {{OPERATOR}}` 的 DEBUG 日志。

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
git commit -m "Add {{OPERATOR}} iluvatar specialized operator implementation"
```

**【禁止 AI 署名】** commit message **只能**包含上面 `-m` 指定的内容。**严禁**添加任何形式的
AI 署名或生成标记，包括但不限于 `Co-Authored-By: Claude ...`、`Generated with Claude Code`、
`🤖` 等 trailer。提交后请用 `git log -1 --format=%B` 复查，确认 message 中不含任何此类内容。

**必须在运行 benchmark 之前提交**，确保代码变更不会丢失。

### Step 7: 编写 benchmark 并运行

**在 FlagGems 标准 benchmark 文件中添加 benchmark 条目**。

根据算子类型，选择对应的 benchmark 文件：
- 一元 pointwise → `benchmark/test_unary_pointwise_perf.py`
- 二元 pointwise → `benchmark/test_binary_pointwise_perf.py`
- reduction → `benchmark/test_reduction_perf.py`
- 其他 → `benchmark/test_special_perf.py`

**先阅读对应 benchmark 文件**，了解 `forward_operations` 列表的格式，然后将新算子追加到列表末尾。

#### ⚠️ 自定义 Baseline 策略（本模板的关键改进）

本次优化的算子中，有些算子的 torch 原生 API 在天数上不可用或会 segfault。**必须根据上方的"算子专属优化指导"中给出的 Benchmark baseline 策略来编写 benchmark**。

**方案 A：提供自定义 torch_op 函数作为 baseline**（适用于 `_fused_adam_`、`cross_attention`、`Cross_Attention`、`FlashDecoding`、`Matmul_Bias_Activation`）

在 benchmark 文件中定义一个手写的等价 PyTorch 函数作为 baseline：
```python
# 在 benchmark 文件中定义自定义 baseline 函数
def torch_my_op_baseline(x, y, ...):
    """使用基本 torch 操作实现等价功能，作为 benchmark baseline"""
    # ... 见上方各算子的具体 baseline 代码
    return result

# 在 forward_operations 中使用自定义函数替代 torch.xxx：
forward_operations = [
    ("{{OPERATOR}}", torch_my_op_baseline, [torch.float16]),
]
```

**方案 B：只测量 FlagGems 绝对延迟**（适用于 `_nested_view_from_buffer_copy` 等 baseline 会 segfault 的算子）

```python
bench.metrics = ["latency"]  # 不测量 baseline，只测 FlagGems 延迟
bench.set_gems(my_gems_op)    # 设置 FlagGems 实现函数
```

在这种情况下，输出 JSON 的 speedup 字段设为 **1.0**（自比较）。

**方案 C：标准 benchmark**（适用于 `convolution` 等 torch baseline 可用的算子）

使用默认的 `torch.xxx` 作为 baseline，无需特殊处理。

---

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

**⚠️ benchmark data 不能为空**：如果 benchmark 运行完毕但 `data` 数组为空（没有任何 SUCCESS 行），这算作**失败**。你必须排查原因并修复，确保至少有一组有效的 speedup 数据。常见原因：
- baseline 函数在天数上崩溃 → 使用上方的自定义 baseline 策略
- benchmark 文件中的 marker 名称不匹配 → 检查 `@pytest.mark.xxx`
- benchmark 函数签名与算子接口不匹配 → 仔细对照算子的输入输出

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
    "src/flag_gems/runtime/backend/_iluvatar/ops/{{OPERATOR}}.py"
  ],
  "files_modified": [
    "src/flag_gems/runtime/backend/_iluvatar/ops/__init__.py",
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
  "notes": "天数特化算子实现"
}
```

**注意**：`benchmark_results.data` 数组中应包含 benchmark 输出中**每一行 SUCCESS** 的数据。**`data` 数组不能为空**——如果为空说明 benchmark 没有产生有效数据，必须排查修复。对于 baseline 不可用的算子，使用上方"自定义 Baseline 策略"中的方案。

## 重要约束

1. **正确性优先**：必须通过 accuracy 测试
2. **代码风格**：严格遵循天数已有算子代码风格（参考 `div.py`）
3. **标准测试**：测试和 benchmark 必须写入 FlagGems 标准文件中
4. **跨后端兼容**：禁止直接调用 `tl.extra.cuda.libdevice`，必须使用 `tl_extra_shim` 或 Triton 内置函数
5. **字母顺序**：所有注册必须严格按字母顺序插入
6. **最终代码保留**：无论成功失败，都保留修改的代码在 worktree 中
7. **不要删除或修改已有算子代码和测试**（包括通用算子和天数已有算子）
8. **JSON 结果必须输出**：即使失败也要输出 JSON，标明 status 为 failed
9. **禁止 pip install**：不要运行 `pip install -e .` 或任何安装命令
10. **工作目录**：所有命令必须在 `{{WORK_DIR}}` 下执行
11. **禁止写临时文件**：不要将测试或代码写到 `/tmp` 或其他临时目录
12. **天数标准 Triton API**：使用 `tl.program_id()` 而非 `tle.program_id()`，不需要 import triton_lang_extension
13. **测试前杀残留进程**：仅清理占用当前 GPU 的残留进程，**禁止** `killall -9 python`（会杀掉其他并发任务）
14. **确认 marker 大小写**：运行测试前先用 grep 确认 pytest marker 名称
15. **benchmark data 不能为空**：`benchmark_results.data` 必须包含至少一组有效的 speedup 数据。如果 torch baseline 不可用，必须使用自定义 baseline 函数或 `bench.metrics = ["latency"]` 模式
16. **优先使用 ixformer 原生 API**：对于 attention、matmul 类算子，`ixformer` 原生 API 性能远优于 Triton kernel，必须优先使用
17. **遵循算子专属优化指导**：上方"算子专属优化指导"中给出的方案是经过多轮验证的最优策略，不要重复之前已失败的方案