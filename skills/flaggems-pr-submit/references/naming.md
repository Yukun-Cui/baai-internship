# 下划线前缀算子命名规则

示例算子：`_cholesky_solve_helper`

## 去掉前导下划线的位置

| 位置 | 示例 |
|------|------|
| pytest mark | `@pytest.mark.cholesky_solve_helper` |
| operators.yaml `id` | `id: cholesky_solve_helper` |
| benchmark `op_name` | `op_name="cholesky_solve_helper"` |
| 测试文件名 | `tests/test_cholesky_solve_helper.py` |
| benchmark 文件名 | `benchmark/test_cholesky_solve_helper.py` |
| 测试函数名 | `def test_cholesky_solve_helper(...)` |

## 保留前导下划线的位置

| 位置 | 示例 |
|------|------|
| kernel 文件名 | `src/flag_gems/ops/_cholesky_solve_helper.py` |
| 函数名 | `_cholesky_solve_helper` |
| Import / `__all__` | `from flag_gems.ops._cholesky_solve_helper import _cholesky_solve_helper` |
| `_FULL_CONFIG` aten name | `("_cholesky_solve_helper", _cholesky_solve_helper)` |
| operators.yaml `for` | `- _cholesky_solve_helper` |
| 代码中实际调用 | `torch._cholesky_solve_helper(...)` |

## 尾部下划线（inplace）

尾部 `_` 始终保留：`bernoulli_` → mark `bernoulli_`、id `bernoulli_`、op_name `bernoulli_`
