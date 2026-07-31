# 下划线前缀算子命名规则

示例算子：`_cholesky_solve_helper`

> 默认规则（本节）适用于**上游不存在同名裸算子**的前导下划线算子。
> 如果存在仅相差前导下划线的两个算子（如 `linalg_svd` 与 `_linalg_svd`），改用下方
> 「前导下划线冲突消歧」规则。

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

## 前导下划线冲突消歧

命名总原则：
- `operators.yaml` 记录算子信息，实际 API 应与 `id` 一致；
- 每个算子通过自定义 marker 独立测试，API 应与 marker 一致；
- API 默认移除算子名的前导下划线（即上方默认规则）。

**例外**：当两个算子仅相差前导下划线（如 `linalg_svd` 与 `_linalg_svd`）时，去下划线会导致
`id` / 文件名 / API 撞名。此时**保留前导下划线**以区分，并且 **marker 用 `underscore_` 前缀**
替代前导下划线（pytest marker 名不能以下划线开头）。

以 `_linalg_svd`（与已存在的 `linalg_svd` 冲突）为例：

| 位置 | 命名 |
|------|------|
| kernel 文件名 | `src/flag_gems/ops/_linalg_svd.py` |
| 测试文件名 | `tests/test__linalg_svd.py`（`test_` + `_linalg_svd`，故双下划线） |
| benchmark 文件名 | `benchmark/test__linalg_svd.py` |
| 函数名 / API | `_linalg_svd` |
| operators.yaml `id` | `_linalg_svd` |
| benchmark `op_name` | `_linalg_svd` |
| pytest mark | `@pytest.mark.underscore_linalg_svd` |
| 测试函数名 | `def test__linalg_svd(...)` |

对照的裸算子 `linalg_svd` 一切照常（id/API/文件名/mark 均为 `linalg_svd`），两者不再撞名。

> 冲突为**自动探测**：当算子带前导下划线、且 `ops/` 目录已存在裸算子 kernel 文件或
> `operators.yaml` 已有裸 `id` 时，`extract_from_worktree.py` / `check_operator.py` /
> `submit_operator.py` / `check_overload_consistency.py` 都会自动切到冲突消歧命名，
> 无需手动传参。探测逻辑集中在 `scripts/paths.py` 的 `resolve_op_names` / `id_to_mark`。

## 尾部下划线（inplace）

尾部 `_` 始终保留：`bernoulli_` → mark `bernoulli_`、id `bernoulli_`、op_name `bernoulli_`

## 多重载算子命名

当 yaml 为算子的每个重载注册了独立 `id` 时，三者必须完全对齐：

| yaml `id` | pytest mark | benchmark `op_name` |
|------|------|------|
| `reflection_pad3d` | `@pytest.mark.reflection_pad3d` | `op_name="reflection_pad3d"` |
| `reflection_pad3d_out` | `@pytest.mark.reflection_pad3d_out` | `op_name="reflection_pad3d_out"` |
| `eq` | `@pytest.mark.eq` | `op_name="eq"` |
| `eq_scalar` | `@pytest.mark.eq_scalar` | `op_name="eq_scalar"` |

适用于所有重载后缀：`_out`、`_scalar`、`_tensor`、`_mode`、`_backward` 等。是否拆分为独立条目以 yaml 实际配置为准——如果 yaml 中该重载没有独立 `id`，则 benchmark 可复用主算子的 mark。
