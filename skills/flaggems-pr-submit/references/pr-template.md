# PR Description Template

## gh 命令

```bash
: "${GH_TOKEN:?set GH_TOKEN first}"

gh pr create \
  --repo flagos-ai/FlagGems-Experimental \
  --head Yukun-Cui:pr/<op> \
  --base infra-ci \
  --title "[KernelGen][Nvidia] Add <op> operator with Triton kernel" \
  --body "$(cat <<'EOF'
## Summary
Adds a Triton kernel for `<op>`. <one-line description>.

## Testing
- Parametrized tests over `<parameter dims>` and `<dtypes>`
- Validated against reference on device via `to_reference(inp, True)`
- Tested on: Nvidia H20

## Performance
Test command: `pytest benchmark/test_<op>.py --level core`

### <Operator>

| dtype | Size | Torch Latency (ms) | Gems Latency (ms) | Speedup | TFLOPS |
|-------|------|--------------------|-------------------|---------|--------|
| <dtype> | <size> | <torch_ms> | <gems_ms> | <speedup> | <tflops> |

| Operator | Arithmetic Mean Speedup |
|----------|------------------------|
| <Operator> | **<am_speedup>** |

## Files Changed
- `src/flag_gems/ops/<op>.py`: Triton kernel implementation
- `tests/test_<op>.py`: Accuracy test
- `benchmark/test_<op>.py`: Performance benchmark
- `src/flag_gems/ops/__init__.py`: Register import and `__all__`
- `src/flag_gems/__init__.py`: Register to `_FULL_CONFIG`
- `conf/operators.yaml`: Add operator entry (kind: <kind>, stage: alpha 5.5)
EOF
)"
```

## JSON 字段映射

`gen_pr_description.py` 输出的 JSON 字段直接映射到模板：

| 模板位置 | JSON 字段 |
|---------|-----------|
| Performance 表格行 | `nvidia_benchmark.rows[]` (operator, dtype, shape, torch_ms, gems_ms, speedup, tflops) |
| Arithmetic Mean | `nvidia_benchmark.operator_means[]`（算术平均）；单 variant 可回退到 `nvidia_benchmark.arithmetic_mean_speedup` |
| Performance case 数 | `nvidia_benchmark.case_count` |

PR body 只报 Nvidia H20 数据，不含 Multi-backend Testing 段。

## 填写规则

- **全部用英文**
- Performance 数据必须来自 CI 日志或 `gen_pr_description.py` 脚本
- Performance 必须按 operator/variant 分 `###` 小节展示；in-place variant 标注 `(in-place)`
- 表格必须包含 `dtype`、`Size`、Torch/Gems latency、Speedup；如果 benchmark 输出含 TFLOPS，必须记录 `TFLOPS` 列

## 共享测试/benchmark 文件

`a` 和 `_a` 共用 `tests/test_a.py` / `benchmark/test_a.py`（见 `naming.md`），所以
`Files Changed` 里写的是去掉前导下划线的文件名，哪怕算子本身带下划线。
`submit_operator.py` 自动用 `-m <mark>` 只跑本算子的 case，PR 里的性能数字不会
混入同住算子的行。
