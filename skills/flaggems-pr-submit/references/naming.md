# 下划线前缀算子命名规则

示例算子：`_cholesky_solve_helper`

> 默认规则（本节）适用于**上游不存在同名裸算子**的前导下划线算子。
> 如果存在仅相差前导下划线的两个算子（如 `linalg_svd` 与 `_linalg_svd`），改用下方
> 「前导下划线冲突消歧」规则。

## 去掉前导下划线的位置

**重要：kernel 文件名也在去掉之列**（2026-10 更新）。只要 pytorch 原生中**不存在**
同名裸算子（即不会与裸名撞名），实现文件就用裸名：`src/flag_gems/ops/fw_primal_copy.py`。
原因见下方「kernel 文件名裸名化的原因（CI marker 派生）」。

| 位置 | 示例 |
|------|------|
| **kernel 文件名** | `src/flag_gems/ops/cholesky_solve_helper.py`（**裸名**） |
| pytest mark | `@pytest.mark.cholesky_solve_helper` |
| operators.yaml `id` | `id: cholesky_solve_helper` |
| benchmark `op_name` | `op_name="cholesky_solve_helper"` |
| 测试文件名 | `tests/test_cholesky_solve_helper.py` |
| benchmark 文件名 | `benchmark/test_cholesky_solve_helper.py` |
| 测试函数名 | `def test_cholesky_solve_helper(...)` |

仍保留下划线的位置（ATen schema 名与注册键，与文件名无关）：

| 位置 | 示例 |
|------|------|
| operators.yaml `for` | `- _cholesky_solve_helper` |
| `_FULL_CONFIG` aten name | `("_cholesky_solve_helper", _cholesky_solve_helper)` |
| wrapper 函数名 / `__all__` / import 的函数部分 | `_cholesky_solve_helper` |
| 代码中实际调用 | `torch._cholesky_solve_helper(...)` |

master 先例：`values.py`（id `values` / for `_values`）、`neg_view_copy.py`
（id `neg_view_copy` / for `_neg_view_copy`）、`indices_copy.py`（#7222）。

## kernel 文件名裸名化的原因（CI marker 派生）

CI 的 `tools/ci_checks/derive_changed_operators.py` 按**实现文件 stem** 派生 pytest
marker，规则（#6359 约定）：

1. stem 不以 `_` 开头 → marker = stem；
2. stem 以 `_` 开头 → 剥掉下划线；若剥掉后的名字**存在于 operators.yaml 的 id 集合**
   （含本 PR 新增的条目，CI 在 merge 后的 checkout 上运行）→ marker 加 `underscore_` 前缀。

由此产生死锁：若 kernel 文件叫 `_fw_primal_copy.py` 且 yaml id 用裸名
`fw_primal_copy`（merge 后 yaml 含该 id），derive 会输出
`underscore_fw_primal_copy`，而测试里声明的是裸 mark → `pytest -m` 选 0 个用例 →
`python-op` CI 失败（exit 1，日志特征：`Running 0 items in this shard`）。

把 kernel 文件改名为裸名（`fw_primal_copy.py`）后，stem 精确匹配 yaml id，
derive 输出裸名 marker，与测试 mark、benchmark `op_name`、yaml id 四者对齐。
**wrapper 函数名 / `_FULL_CONFIG` 的 aten 注册键 / yaml `for` 仍保留 ATen 原名**
（如 `("_fw_primal_copy", _fw_primal_copy)`）——它们是 schema/注册层的名字，
与文件名无关。

> 排查此类失败的特征：CI `python-op` 日志出现
> `Running marker-selected tests for changed operators: underscore_xxx`
> 且紧跟 `Running 0 items in this shard`。本地验证：
> `python3 tools/ci_checks/derive_changed_operators.py --ops-only --changed-files "src/flag_gems/ops/<stem>.py"`
> 的输出必须与测试文件里声明的 mark 一致。

## 测试/benchmark 文件名永不带前导下划线

**测试和 benchmark 文件名不参与下面的冲突消歧**：无论是否与裸算子冲突，
文件名一律是 `tests/test_<去掉前导下划线>.py` 和 `benchmark/test_<同>.py`。
所以 `a` 和 `_a` **共用** `tests/test_a.py` 与 `benchmark/test_a.py`。

写入规则：**文件已存在就续写**（保留原有全部内容，新 case 追加到末尾，重名
def/class 跳过，import 合并），不存在才新建。`extract_from_worktree.py` 的
`write_or_append()` 自动处理。

两个算子在同一文件里靠各自的 mark 区分，互不干扰：

```bash
pytest tests/test_a.py -m a              # 只跑裸算子的 case
pytest tests/test_a.py -m underscore_a   # 只跑私名算子的 case
```

因此 `check_operator.py` / `submit_operator.py` / `gen_pr_description.py` 在共享
文件上全部按 `-m <mark>` 或 mark 范围工作：检查只看自己 mark 的函数（邻居算子
的存量代码不属于本 PR diff，不报错），本地测试和 benchmark 也只跑自己的 case
（否则 benchmark 数据会混进邻居的行）。

> 共享的好处：两个算子同输入可比，能直接证明私有版没有额外开销；也免掉
> reviewer 反复要求合并 "redundant underscore" 文件。

## 保留前导下划线的位置

| 位置 | 示例 |
|------|------|
| 函数名 | `_cholesky_solve_helper` |
| Import 的函数部分 / `__all__` | `from flag_gems.ops.cholesky_solve_helper import _cholesky_solve_helper`（**模块路径用裸名文件**） |
| `_FULL_CONFIG` aten name | `("_cholesky_solve_helper", _cholesky_solve_helper)` |
| operators.yaml `for` | `- _cholesky_solve_helper` |
| 代码中实际调用 | `torch._cholesky_solve_helper(...)` |

（kernel **文件名**已移入上方「去掉前导下划线」表——无裸名孪生时用裸名文件 `cholesky_solve_helper.py`。）

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
| 测试文件名 | `tests/test_linalg_svd.py`（**与裸算子共用**，不带前导下划线） |
| benchmark 文件名 | `benchmark/test_linalg_svd.py`（**与裸算子共用**） |
| 函数名 / API | `_linalg_svd` |
| operators.yaml `id` | `_linalg_svd` |
| benchmark `op_name` | `_linalg_svd` |
| pytest mark | `@pytest.mark.underscore_linalg_svd` |
| 测试函数名 | `def test__linalg_svd(...)` |

对照的裸算子 `linalg_svd` 的 id/API/mark 均为 `linalg_svd`，两者只在**文件名**
上重合（同住 `test_linalg_svd.py`），其余都不撞名；文件内按 mark 区分。

> 冲突为**自动探测**：当算子带前导下划线、且 `ops/` 目录已存在裸算子 kernel 文件或
> `operators.yaml` 已有裸 `id` 时，`extract_from_worktree.py` / `check_operator.py` /
> `submit_operator.py` / `check_overload_consistency.py` 都会自动切到冲突消歧命名，
> 无需手动传参。探测逻辑集中在 `scripts/paths.py` 的 `resolve_op_names` / `id_to_mark`；
> 测试/benchmark 文件名走 `test_file_id`（恒去前导下划线，不受冲突影响）。
>
> 注意：冲突对里**裸算子与下划线算子都要在 master 落地**，例外条件才成立。若提交
> 下划线版时裸名版尚未合并（master 的 yaml 里没有裸 id），CI 的 derive 会退回裸
> marker（剥下划线、无 `underscore_` 前缀）——此时共享测试文件必须同时携带
> 函数级裸 mark（见下方「共享测试文件的 pytestmark 双声明」）。

### 共享测试文件的 pytestmark 双声明（bare/underscore 两个 mark）

当 bare 与 `_` 前缀两个算子**共用同一个测试/benchmark 文件**（`tests/test_a.py` 同住
`a` 与 `_a` 两套用例）时，文件**前半部分（import 之后）必须声明模块级双 mark**：

```python
pytestmark = [
    pytest.mark.a,
    pytest.mark.underscore_a,
]
```

原因（两条独立约束，缺一不可）：

1. **CI 的 `check_operator_markers` / `check-kernelgen-tests` 只认函数级
   `@pytest.mark.<marker>` 装饰器**，模块级 `pytestmark` 列表不算数。裸算子侧的
   用例必须有函数级裸 mark，下划线侧同理。
2. **derive marker 的口径随合并状态漂移**：bare 版合并前，derive 对 `_a.py` 输出裸
   marker `a`（stripped 不在 yaml）；bare 版合并后，yaml 里有了 `a`，derive 输出
   `underscore_a`。双声明让 `pytest -m a` 与 `pytest -m underscore_a`
   在两种状态下都能选中各自的用例。

先例：`tests/test_indices_copy.py`（`indices_copy` + `underscore_indices_copy`）、
`tests/test_indices.py`（#7325 `indices` + #7293 `_indices`）。

### 追加写入（共享文件以 master 现状为底）

若共享 test/benchmark 文件在 master 上已存在（裸算子先合并），下划线 PR 必须**追加**
而非覆盖：

- 以 `gh api repos/<owner>/<repo>/contents/<path>` 拉取 master 当前文件为底，在末尾
  追加本算子的用例；
- benchmark 类名加前缀避免撞名（如 `IndicesCopyBenchmark` →
  `UnderscoreIndicesCopyBenchmark`，含继承关系）；
- master 辅助函数可能带与本算子语义冲突的行为（例：master 的 `_make_coo` 为公开
  `indices` 服务而末尾 `.coalesce()`，会破坏 `_indices` 的「uncoalesced 输入」用例）
  ——冲突用例需就地构造自己的输入，不强行复用共享 helper，并注释原因。

### 共享注册文件以「master 原文 + 追加」重建（绝不跑 sorter --fix 生成）

`_FULL_CONFIG` / `__all__` / `operators.yaml` 等**共享注册文件**若因 base 陈旧产生
无关 diff，重建方式是：

1. 从 GitHub API 拉取 master 当前原文（`contents` + `git/blobs`）；
2. 用脚本在 casefold 排序的正确位置**仅插入本算子的行**（`_FULL_CONFIG` 的键、
   `__all__` 条目、yaml 条目），上下相邻行完全来自 master 原文；
3. 用 `tools/ci_checks/sort_exports.py --check`、`check_init_exports.py`、
   `isort 5.12 --profile black -o packaging --check-only`、`black --check` 验证 0 错误。

**禁止用 `sort_exports.py --fix` 的输出作为最终内容**：它会全量重写
`_FULL_CONFIG`/`operators.yaml` 并**丢弃 master 已有的行内注释**（如 `_pin_memory`、
`aten::dim`、`nested_to_padded_tensor`、`pin_memory` 四处的说明注释），还会重排
`from packaging import version` 等 import，制造大量无关 diff（真实案例：PR #7225
reviewer 指出 `nested_to_padded_tensor` 条目被"移动"）。`--fix` 只用于本地预演
检查它会改什么，落地永远用「原文 + 精确插入」。

排序键备忘：`_FULL_CONFIG` 与 `__all__` 按 `str.casefold()`；注意裸名与下划线名
混排（`'_'` 的 ASCII 小于字母，但裸名 `fw_primal_copy` 无下划线，排在裸名 `fused_sgd_`
之后），插入点用 `sorted(ids+[new], key=str.casefold)` 的后继元素作 anchor。
本地校验 isort 必须用与 CI 相同的 5.12.0（6.x 行为不同）：
`pip install isort==5.12.0 --target /tmp/isort512 && PYTHONPATH=/tmp/isort512 python3 -m isort ...`。

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
