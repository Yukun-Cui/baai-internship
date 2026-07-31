# 下划线前缀算子命名规则（摩尔线程特化版）

示例算子：`_cholesky_solve_helper`

摩尔线程特化**复用上游已有的 test / benchmark / operators.yaml**（不新建），
但 kernel 文件、函数名、`_mthreads/ops/__init__.py` 注册仍遵循同一套命名规则。

## 去掉前导下划线的位置（仅复用上游时对照，本 skill 不新建）

| 位置 | 示例 | 摩尔线程是否新建 |
|------|------|-----------------|
| pytest mark（跑上游 test 时 `-m`） | `-m cholesky_solve_helper` | 复用上游 |
| operators.yaml `id` | `id: cholesky_solve_helper` | 不改（通用层已有） |
| benchmark `op_name` | `op_name="cholesky_solve_helper"` | 复用上游 |
| 测试 / benchmark 文件名 | `tests/test_cholesky_solve_helper.py` | 复用上游 |
| 测试函数名 | `def test_cholesky_solve_helper(...)` | 复用上游 |

## 保留前导下划线的位置（本 skill 实际提交的文件）

| 位置 | 示例 |
|------|------|
| kernel 文件名 | `src/flag_gems/runtime/backend/_mthreads/ops/_cholesky_solve_helper.py` |
| 函数名（wrapper） | `_cholesky_solve_helper` |
| `_mthreads/ops/__init__.py` import / `__all__` | `from ._cholesky_solve_helper import _cholesky_solve_helper` |
| 回退目标 default 名 | `from flag_gems.ops._cholesky_solve_helper import _cholesky_solve_helper as default__cholesky_solve_helper` |
| 代码中实际调用 | `torch._cholesky_solve_helper(...)` |

## 尾部下划线（inplace）

尾部 `_` 始终保留：`bernoulli_` → 上游 mark `bernoulli_`、kernel 文件 `bernoulli_.py`、
wrapper `bernoulli_`、分支 `pr/mthreads-bernoulli_`。

## 前导下划线冲突消歧

当上游存在仅相差前导下划线的两个算子（如 `linalg_svd` 与 `_linalg_svd`）时，通用层为了避免
`id` / 文件名 / marker 撞名，会对带下划线的那个做特殊处理（保留前导下划线，且 pytest marker
用 `underscore_` 前缀替代前导下划线，因为 marker 名不能以下划线开头）。

摩尔线程特化的处理：

- **提交的文件**（kernel、wrapper、`_mthreads/ops/__init__.py` import/`__all__`、回退 default 名）
  照常用完整的 `_linalg_svd`（本就保留前导下划线，无需变化）。
- **跑上游 test / benchmark 验证时**，`-m` 的 marker **以上游实际注册为准**，不要想当然写
  `-m _linalg_svd` 或 `-m linalg_svd`。先查上游确认该冲突算子实际用的 marker：

  ```bash
  grep -n "linalg_svd" conf/operators.yaml            # 看 id
  grep -rn "pytest.mark" tests/test__linalg_svd.py    # 看 test 实际 marker
  ```

  以查到的 marker 作为 `-m` 参数（通用层按冲突消歧规范时通常是 `underscore_linalg_svd`，
  但一切以上游实际值为准）。

## 与通用版差异

- 摩尔线程**不涉及** `_FULL_CONFIG`、`conf/operators.yaml` 新增（通用层已注册）
- 唯一注册点是 `_mthreads/ops/__init__.py`（BLAS 类算子在 `capability[0]>=3` 分区内，按字母序）
- fused 算子的 source/impl/canonical 名翻译由 KernelGen worktree 侧决定，本 skill 直接沿用
