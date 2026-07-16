# PR Description Template

## gh 命令

```bash
: "${GH_TOKEN:?set GH_TOKEN first}"

gh pr create \
  --repo flagos-ai/FlagGems-Experimental \
  --head Yukun-Cui:pr/<op> \
  --base master \
  --title "[KernelGen][Nvidia] Add <op> operator with Triton kernel" \
  --body "$(cat <<'EOF'
## Summary
Adds a Triton kernel for `<op>`. <one-line description>.

## Testing
- Parametrized tests over `<parameter dims>` and `<dtypes>`
- Validated against reference on device via `to_reference(inp, True)`
- Tested on: Nvidia, Tianshu, Muxi, Ascend, Hygon

## Performance
Test command: `pytest benchmark/test_<op>.py --level core` (NVIDIA H20)

### <Operator>

| dtype | Size | Torch Latency (ms) | Gems Latency (ms) | Speedup | TFLOPS |
|-------|------|--------------------|-------------------|---------|--------|
| <dtype> | <size> | <torch_ms> | <gems_ms> | <speedup> | <tflops> |

| Operator | Arithmetic Mean Speedup |
|----------|------------------------|
| <Operator> | **<am_speedup>** |

## Multi-backend Testing
| Backend | Accuracy Test | Speedup (mean) | Notes |
|---|---|---|---|
| Nvidia (H20) | PASS (<N> cases) | <am_speedup> | Primary |
| Tianshu | <acc> | <mean_speedup> | <notes> |
| Muxi | <acc> | <mean_speedup> | <notes> |
| Ascend | <acc> | <mean_speedup> | <notes> |
| Hygon | <acc> | <mean_speedup> | <notes> |

## Files Changed
- `src/flag_gems/ops/<op>.py`: Triton kernel implementation
- `tests/test_<op>.py`: Accuracy test
- `benchmark/test_<op>.py`: Performance benchmark
- `src/flag_gems/ops/__init__.py`: Register import and `__all__`
- `src/flag_gems/__init__.py`: Register to `_FULL_CONFIG`
- `conf/operators.yaml`: Add operator entry (kind: <kind>, stage: alpha 5.4)
EOF
)"
```

## JSON 字段映射

`gen_pr_description.py` 输出的 JSON 字段直接映射到模板：

| 模板位置 | JSON 字段 |
|---------|-----------|
| Performance 表格行 | `nvidia_benchmark.rows[]` (operator, dtype, shape, torch_ms, gems_ms, speedup, tflops) |
| Arithmetic Mean | `nvidia_benchmark.operator_means[]`；单 variant 可回退到 `nvidia_benchmark.arithmetic_mean_speedup` |
| Performance case 数 | `nvidia_benchmark.case_count` |
| Multi-backend PASS/FAIL | `domestic_gpu.<backend>.accuracy_passed` / `benchmark_passed` |
| Multi-backend Speedup | `domestic_gpu.<backend>.bench_mean_speedup` |
| Multi-backend case 数 | `domestic_gpu.<backend>.bench_case_count` |
| Multi-backend Notes | `domestic_gpu.<backend>.test_error` / `bench_error`（截短至一句话） |

## 填写规则

- **全部用英文**
- Performance 数据必须来自 CI 日志或 `gen_pr_description.py` 脚本
- Performance 必须按 operator/variant 分 `###` 小节展示；in-place variant 标注 `(in-place)`
- 表格必须包含 `dtype`、`Size`、Torch/Gems latency、Speedup；如果 benchmark 输出含 TFLOPS，必须记录 `TFLOPS` 列
- 国产卡 Speedup (mean) 从 summary JSON 的 `benchmark.data` 计算
- 通过时 Notes 填 `—`，benchmark 未运行填 `N/A`，Speedup 填 `—`
- Notes 中失败原因截短至一句话（如 "CompilationError" 而非完整 traceback）
