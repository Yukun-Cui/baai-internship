# anti_hack

FlagGems / flagbench 算子反作弊检查。用于检测「表面上是 Triton kernel，实际绕过真实计算」的作弊实现，保证提交的算子是真正跑在 Triton kernel 上、而不是偷偷调用第三方库或退化成 eager 计算。

## 三层检测

`anti_hack.py` 提供三层独立的检测手段，可单独或组合使用：

1. **静态 AST 扫描**（`check_code`）——在执行前扫描源码，检测被拉黑的 import 和调用（如 `vllm`、`torch.ops.vllm`、`cupy`、`cublas`、`ctypes`、`torch.ops.aten`）。支持按后端使用不同黑名单（`BACKEND_BLACKLISTS`）。
2. **双执行对比**（`dual_execution_check`）——禁用 `triton.jit`（`disable_triton_jit`）后重跑一次，如果结果与开启 JIT 时完全一致，说明真实计算没有走 Triton kernel，判定为作弊。
3. **GPU profiling 指纹**（`gpu_profiling_check` / `profile_kernel_names`）——通过 profiler 抓取实际 launch 的 CUDA kernel 名称，与期望模式比对；如果一个 CUDA kernel 都没有 launch，判定为作弊。

## 文件说明

| 文件 | 说明 |
|------|------|
| `anti_hack.py` | 核心检测模块。对外主要接口：`check_code(code, backend)`、`dual_execution_check(...)`、`gpu_profiling_check(...)`。 |
| `anti_hack_runner.py` | 批量运行器 `AntiHackRunner`，按算子名推断后端（`get_backend`）、逐个检查（`check_operator`）、批量检查（`batch_check`）并输出报告（`save_report`）。 |

## 依赖说明

本目录是从 flagbench 仓库中抽取的模块，**不是独立可运行的脚本**。`anti_hack_runner.py` 依赖 flagbench 的 sandbox 组件：

```python
from sandbox.anti_hack import check_code as anti_hack_check
from sandbox.verifier.verifier import Verifier, VerifyConfig, VerifyRequest, Source
```

要实际运行，需要在 flagbench 环境（`sandbox` 包可导入、CUDA + Triton + torch 可用）中调用，或把这两个文件放回 flagbench 的 `sandbox/` 下作为参考实现。留在本仓库主要作为反作弊逻辑的可复用参考。

## 用法（在 flagbench 环境中）

```python
from anti_hack import check_code

# 静态扫描：返回 (is_hack, reason)
is_hack, reason = check_code(source_code, backend="vllm13")
if is_hack:
    print("作弊:", reason)
```

```python
from anti_hack_runner import AntiHackRunner

runner = AntiHackRunner(dataset="v2_1", verify_config=cfg)
results = runner.batch_check(operators)
runner.save_report(
    results,
    total_operators=len(operators),
    passed_operators=passed,
    output_path=Path("anti_hack_report.json"),
)
```

## 与其他工具的关系

反作弊检查关注「实现是否真实计算」，与 [triton_check](../triton_check/) 关注的「实现是否使用真正的 Triton kernel」互补，二者常配合使用：triton_check 做合规性静态审查，anti_hack 做执行期的作弊验证。

`skills/flaggems-pr-submit` 的 `check_operator.py` 会通过 `ANTI_HACK_SCRIPT` 环境变量调用本目录的 `anti_hack.py`（默认已指向 `/root/baai-internship/anti_hack/anti_hack.py`）。
