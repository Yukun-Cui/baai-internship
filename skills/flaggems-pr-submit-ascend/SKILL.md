---
name: flaggems-pr-submit-ascend
description: >
  This skill should be used when submitting FlagGems **Ascend (昇腾)** specialized operator PRs,
  reviewing Ascend operator code before submission, or when the user mentions "提昇腾PR",
  "提交昇腾算子", "Ascend PR", "昇腾特化". It automates code review, validates completeness
  and compliance, runs pre-commit and worktree tests, and directly submits PR to upstream
  with full description including speedup data. Ascend ops live under
  `src/flag_gems/runtime/backend/_ascend/ops/` and use the vendor backend registration system.
---

# FlagGems 昇腾特化算子 PR 提交 Skill

This skill guides the complete workflow for submitting FlagGems **Ascend (昇腾)** specialized
operator PRs: code review, compliance validation, pre-commit checks, worktree testing, and
direct submission to upstream (push to fork then immediately create upstream PR with full
description and speedup data).

**与 NVIDIA 通用算子 PR 的关键差异：**
- Kernel 路径: `src/flag_gems/runtime/backend/_ascend/ops/<op>.py`（不是 `src/flag_gems/ops/`）
- 注册方式: 只需修改 `_ascend/ops/__init__.py`（不需要 `src/flag_gems/__init__.py` 的 `_FULL_CONFIG`）
- 提交文件: 5 个（不是 6 个，少一个顶层 `__init__.py`）
- PR 标签: `[KernelGen][Ascend]`（不是 `[Nvidia]`）
- 测试环境: `ASCEND_VISIBLE_DEVICES` + `npu-smi info` + `--ref cpu`
- Fork: 你自己的 FlagGems fork（见 Configuration 的 `FLAGGEMS_FORK_OWNER`）

## CRITICAL: Enforcement Rules

**以下规则为强制执行项，违反会导致 PR 被拒：**

1. **先跑脚本，再 commit** — 每次 commit 前必须运行 `check_operator.py` 并确认 0 errors
2. **dtype 默认用常量** — 测试用 `utils.FLOAT_DTYPES`，benchmark 用 `consts.FLOAT_DTYPES`
   - **例外：底层 CUDA 不支持全部 dtype 时**（如 cholesky_cusolver 不支持 Half/BFloat16），
     可以硬编码 `[torch.float32]`，但**必须加注释说明原因**，格式如下：
     ```python
     # cholesky_cusolver only supports float32+; Half/BFloat16 raise RuntimeError
     @pytest.mark.parametrize("dtype", [torch.float32])
     ```
   - **以下算子类型通常不支持 Half/BFloat16（默认用 float32）：**
     - `linalg.*`（eig、eigvals、inv、cholesky、svd 等线性代数算子）
     - `special.*`（bessel_j1、airy_ai、gammaincc 等特殊函数）
     - `igamma` / `igammac`
     - `cdist` / `_euclidean_dist`
     - 仿射变换类（affine_grid 等，kernel 内部强制 float32 计算）
   - **如果不确定，默认用 `[torch.float32]` 更安全**，而不是冒险用 `FLOAT_DTYPES`
   - 使用硬编码 `[torch.float32]` 时，benchmark 文件不再需要 `import consts`，只导入 `base`
3. **下划线命名** — 前导 `_` 的算子，mark/yaml id/文件名 去掉下划线，其余保留
4. **不导出 triton kernel** — `__all__` 和 ops/__init__.py 只导出 wrapper 函数
5. **`_ascend/ops/__init__.py` 导出映射到 wrapper** — 不是 triton kernel 函数
6. **yaml 条目唯一** — 不允许重复 id
7. **PR 描述用英文** — 必须遵循下方 PR Description 模板，全部用英文撰写
8. **测试/benchmark 禁止调用私有 API 做辅助计算** — `torch._xxx` 在不同 PyTorch 版本中可能不存在。
   - **禁止**：用 `torch._cholesky_solve_helper` 等私有 API 做参考计算
   - **允许**：调用被测算子本身的 aten dispatch（如 `torch._euclidean_dist`），因为这是我们要覆盖的 aten op
   - 原则：aten dispatch 会自动路由到我们的 kernel，参考计算应使用公开 API
9. **每个 PR 分支只包含一个 aten 算子** — 例如 `igammac` 和 `igammac_` 不可一起提交，必须分开。
   提交前必须运行 `git diff --name-only upstream/master..HEAD` 确认没有混入其他算子的文件
10. **使用规范命名** — 提交前必须查询 `规范名.xlsx` 获取算子的规范名称
11. **回填 PR 链接** — PR 创建后必须将链接回填到 `规范名.xlsx` 的代码路径列
12. **dtype 预检测** — 在写测试前，必须检查该算子的 PyTorch 参考实现是否支持 Half/BFloat16。
   很多底层 CUDA 算子（如 `bessel_j1_cuda`, `igammac_cuda`, `airy_ai_cuda`, `cdist_cuda`,
   `linalg_eig`, `linalg.inv` 等）不支持低精度。检测方法：在 worktree kernel 源码或
   PyTorch 文档中确认，或直接在 CI 前本地跑一次 `torch.<op>(torch.randn(..., dtype=torch.float16))`。
   **如果不确定，默认用 `[torch.float32]` 更安全**
13. **gems_assert_close API** — 签名为 `gems_assert_close(res, ref, dtype, equal_nan=False, reduce_dim=1, atol=1e-4)`。
   **不接受 `rtol` 参数**。不要传 `rtol`，否则会 `TypeError: unexpected keyword argument`
14. **非 pointwise 算子的 benchmark 必须从 worktree 提取** — CI 用 `--level core` 运行 benchmark 时，
   `set_shapes` 会从 yaml 文件加载 shapes，覆盖 `GenericBenchmark(shapes=[...])` 中传入的参数。
   非 pointwise 算子（需要特殊输入格式如 matrix pair、4D NCHW 等）的正确做法是：
   **从 worktree 提取原始 Benchmark 子类**（通常在 `benchmark/test_special_perf.py` 中），
   它们通过覆盖 `set_shapes` 方法避免被 CI 覆盖：
   ```python
   CUSTOM_SHAPES = [((64, 128), (64, 128)), ((128, 256), (128, 256))]

   class MyOpBenchmark(base.Benchmark):
       def set_shapes(self, shape_file_path=None):
           self.shapes = CUSTOM_SHAPES  # 覆盖 set_shapes 防止 CI 替换

       def get_input_iter(self, cur_dtype):
           for (n1, d), (n2, d2) in self.shapes:
               x1 = torch.randn(n1, d, dtype=cur_dtype, device=self.device)
               x2 = torch.randn(n2, d2, dtype=cur_dtype, device=self.device)
               yield x1, x2
   ```
   参考上游已 merge 的 `benchmark/test_grid_sample.py`（也用同样的模式）。
   **只有 UnaryPointwiseBenchmark / BinaryPointwiseBenchmark 可以直接使用**，其他一律从 worktree 提取。
   **不要使用 `GenericBenchmark` + 自定义 `input_fn`**（CI 会覆盖 shapes 导致解包崩溃）。
15. **benchmark op_name 必须与 pytest mark 完全一致** — 例如 `@pytest.mark.igammac_` 对应
   `op_name="igammac_"`，而不是 `op_name="igammac"`。不一致会导致上游 CI 匹配失败
16. **无意义的别名封装** — 不要写 `_j1 = tl_extra_shim.j1` 这样的包装，直接使用原函数即可
17. **禁止 Co-Authored-By** — commit message 中不得包含 `Co-Authored-By`，否则 CLA 协议 CI 不过
18. **kernel 文件首行必须有 KernelGen 注释** — 所有 kernel 文件第一行必须是：
   `# Generated by KernelGen: https://github.com/flagos-ai/KernelGen`
   如果 worktree 原版没有此行，提交时添加
19. **PR 代码必须与 worktree 原版一致** — kernel、test、benchmark 文件必须从 worktree 提取，
   **不允许重写测试逻辑**。test 文件从 worktree 的测试文件（如 `test_unary_pointwise_ops.py`、
   `test_special_ops.py` 等）中提取对应函数，保持原有的比较逻辑、atol 值、排序方式等。
   仅允许做以下改动：
   - 从共享测试文件拆分到独立文件时调整 import
   - pre-commit 自动格式化（black/isort）
   - 修复 flake8 报错（如 F401 unused import）
   提交前用 `diff` 对比 worktree 和 PR 分支，确认只有格式差异
20. **提交前在 worktree 测试并获取加速比** — PR 描述 Performance 表格中必须填入实测加速比，
   测试命令：`python -m pytest benchmark/test_<op_perf_file>.py -m <op> -vs`
21. **无效 if/else 分支清理** — 如果 pointwise_dynamic 已经处理了类型分发，不需要手动
   `isinstance(A, torch.Tensor)` 判断。多余的分支必须清理
22. **block_size 等超参避免 hardcode** — 应使用 `@triton.autotune` 自动调整。如果确实
   hardcode 了，需要在 `pr状态记录.md` 的"Hardcode 超参记录"中说明原因
23. **测试 case 参数使用公共变量** — 优先使用 `utils.FLOAT_DTYPES`、`utils.POINTWISE_SHAPES` 等。
   即使 worktree 原版用了手写 shapes（如 `[(2, 3), (128, 256)]`），提交时也应替换为公共常量。
   如果需要自定义参数，必须加注释说明原因
24. **所有异常记录到 pr状态记录.md** — 包括本地通过但 CI 精度不过的情况、hardcode 超参等
25. **未注册/未测试的函数必须删除** — 如果 kernel 文件中定义了函数（如 inplace 版本 `<op>_`），
   但该函数没有在 `_ascend/ops/__init__.py` 注册、没有在 `__all__` 导出、没有对应测试，则必须删除。
   每个 PR 只提交一个 aten 算子（规则 9），kernel 文件中只应包含该算子需要的函数
26. **核心计算必须使用 Triton kernel（禁止 torch 计算）** — kernel 文件中的核心数学运算
   必须由 `@triton.jit` 函数或 FlagGems 工具（如 `@pointwise_dynamic` + `@triton.jit`）完成。

   **禁止**：在 kernel 的核心计算路径中使用 `torch` 计算函数（`torch.matmul`, `torch.mm`,
   `torch.add`, `torch.softmax`, `torch.nn.functional.*` 等）。如果 torch 计算操作是算子的
   **主要计算逻辑**，则判定为不合格。

   **允许的 torch 操作**（辅助操作，不涉及核心计算）：
   - 内存分配：`torch.empty`, `torch.zeros`, `torch.ones`, `torch.full` 及 `*_like` 系列
   - Tensor 属性/形状：`.shape`, `.stride()`, `.numel()`, `.dtype`, `.device`, `.ndim`
   - 形状操作：`.reshape`, `.view`, `.contiguous()`, `.expand`, `.permute`, `.transpose`
   - 类型转换：`.to()`, `.float()`, `.half()`
   - 复数辅助：`torch.view_as_real`, `torch.view_as_complex`
   - 设备管理：`.to(device)`
   - 类型推断：`torch.promote_types`, `torch.result_type`

   **允许的内部调用**：
   - 调用 `flag_gems` 模块内的函数（如 `flag_gems.utils.pointwise_dynamic`, `flag_gems.ops.*`）
   - 调用其他已实现的 FlagGems 算子（组合算子模式）

   **`@use_tl_extra` 模式说明**：
   ```python
   @use_tl_extra
   @triton.jit
   def lgamma(x):
       pass
   ```
   这是合法的。`pass` 是占位符，`@use_tl_extra` 装饰器在 JIT 时用 `tl.math.lgamma` 替换函数体。
   只要该函数在 kernel 中被实际调用就应保留；如果未被调用则必须删除（如未使用的 `exp`/`pow` 桩函数）
27. **连续提交多个 PR 必须限速** — 每提交完一个 PR 等 1-2 分钟再提交下一个，不要短时间内连着交。
   短时间涌入多个 PR 会让 CI 调度把一部分任务挤掉（排队被抢占或根本不触发），PR 看起来没跑全流水线，
   只能手动重跑。批量提交结束后逐个确认每个 PR 的 CI 任务都真的起来了（`gh pr checks <PR> --repo <upstream>`），
   缺的手动重触发。

## Configuration

所有环境相关的路径、仓库和身份都通过环境变量配置，脚本内不写死。
Bash 脚本从 `scripts/config.sh` 读取这些变量；Python 脚本直接读环境变量。

**开始工作前先确认配置**（建议放进 shell profile 或每次 export）：

| 变量 | 必需 | 说明 |
|------|------|------|
| `FLAGGEMS_REPO` | 是 | FlagGems 仓库路径（也可每次传 `--repo-dir`） |
| `FLAGGEMS_SUMMARY_JSON` | benchmark 步骤需要 | auto_gen 结果 `summary.json` 路径 |
| `FLAGGEMS_NORM_XLSX` | Phase 0 / 回填需要 | 规范名表，列：`算子名`, `算子名（规范命名）`, `代码路径` |
| `FLAGGEMS_PR_XLSX` | Phase 0 需要 | 待提交算子表，列：`算子名称`(含 `aten::` 前缀), `加速比` |
| `FLAGGEMS_FORK_OWNER` | 否 | fork 的 GitHub owner；默认从 fork remote URL 推导 |
| `FLAGGEMS_GIT_NAME` / `FLAGGEMS_GIT_EMAIL` | 否 | 期望的提交身份，**仅校验不改写** `git config` |
| `FLAGGEMS_CONDA_ENV` | 否 | 非空且有 conda 时，运行 registry 脚本前激活该环境 |
| `FLAGGEMS_PYTHON` | 否 | python 解释器，默认 `python3` |

有默认值、通常不用改：

| 变量 | 默认值 |
|------|--------|
| `FLAGGEMS_ASCEND_OPS` | `src/flag_gems/runtime/backend/_ascend/ops` |
| `FLAGGEMS_UPSTREAM_REMOTE` / `FLAGGEMS_UPSTREAM_REPO` | `upstream` / `flagos-ai/FlagGems` |
| `FLAGGEMS_FORK_REMOTE` | `fork` |
| `FLAGGEMS_BASE_BRANCH` | `master` |
| `FLAGGEMS_BRANCH_PREFIX` | `pr/ascend-` |
| `FLAGGEMS_TITLE_PREFIX` | `[KernelGen][Ascend]` |
| `FLAGGEMS_OP_STAGE` | `alpha 5.1` |

配置示例：

```bash
export FLAGGEMS_REPO=/path/to/FlagGems
export FLAGGEMS_SUMMARY_JSON=/path/to/auto_gen/results/ascend/summary.json
export FLAGGEMS_NORM_XLSX=/path/to/规范名.xlsx
export FLAGGEMS_PR_XLSX=/path/to/第一批pr算子.xlsx
```

**前置依赖：**
- `gh` CLI 且已 `gh auth login`（创建 PR 用；未安装时 `create_pr.sh --dry-run` 仍可生成 PR body）
- `pandas` + `openpyxl`（`operator_registry.py` 用）
- git remote：一个指向 upstream，一个指向你的 fork（默认名 `upstream` / `fork`）

Worktrees 位于 `${FLAGGEMS_REPO}/.worktrees/gen-<op>`。
本 skill 的脚本路径在下文写作 `<skill>/scripts/`，即本文件同级的 `scripts/` 目录。

## Complete Workflow

For each operator, execute these phases in order:

### Naming Convention (Critical)

**Underscore-prefixed operators** (e.g., `_cholesky_solve_helper`, `_assert_async`):

**去掉前导下划线的位置（参考上游 `_assert_async` 的做法）：**
- **pytest mark**: `@pytest.mark.cholesky_solve_helper`
- **operators.yaml `id`**: `id: cholesky_solve_helper`
- **benchmark `op_name`**: `op_name="cholesky_solve_helper"`
- **测试/benchmark 文件名**: `tests/test_cholesky_solve_helper.py`、`benchmark/test_cholesky_solve_helper.py`
- **测试函数名**: `def test_cholesky_solve_helper(...)`

**保留前导下划线的位置：**
- **kernel 文件名**: `<ascend-ops>/_cholesky_solve_helper.py`（`<ascend-ops>` = `$FLAGGEMS_ASCEND_OPS`）
- **函数名**: `_cholesky_solve_helper`
- **Import/__all__**: 在 `_ascend/ops/__init__.py` 中 `from ._cholesky_solve_helper import _cholesky_solve_helper`
- **operators.yaml `for`**: `- _cholesky_solve_helper`
- **代码中实际调用**: `torch._cholesky_solve_helper(...)`

### Phase 0: Name Lookup (MUST DO FIRST)

用 `operator_registry.py` 查询算子信息，确认规范名和加速比。
需要 `pandas` + `openpyxl`，以及 `FLAGGEMS_NORM_XLSX` / `FLAGGEMS_PR_XLSX` 已配置。
如果依赖装在 conda 环境里，设 `FLAGGEMS_CONDA_ENV=<env>` 让脚本自动激活。

```bash
python <skill>/scripts/operator_registry.py lookup <operator_name>
```

输出示例：
```
算子名:     _cholesky_solve_helper
规范名:     _cholesky_solve_helper
加速比:     15.1576
PR链接:     (未提交)
规范名表行: 120
```

**规范名影响以下位置：**
- `conf/operators.yaml` 的 `id` 字段 → 使用规范名（去掉前导下划线后的版本）
- pytest mark → 使用规范名（去掉前导下划线后的版本）
- PR title 中的算子名 → 使用规范名
- benchmark `op_name` → 使用规范名（去掉前导下划线后的版本）

**大部分 aten 算子规范名和原名相同**，仅少数 fused 算子需要转 PascalCase（如 `moe_combine` → `MoeCombine`）。

### Phase 1: Preparation

1. Identify the operator name and locate its worktree source:
   ```
   .worktrees/gen-<op>/src/flag_gems/runtime/backend/_ascend/ops/<op>.py
   ```

2. Verify the operator does NOT already exist upstream:
   ```bash
   git show upstream/master:src/flag_gems/runtime/backend/_ascend/ops/<op>.py  # should fail
   grep "id: <op>" conf/operators.yaml  # on upstream/master, should not match
   ```

3. Create a clean branch from upstream/master:
   ```bash
   cd "$FLAGGEMS_REPO"
   git fetch upstream
   git checkout -b pr/ascend-<op> upstream/master
   ```
   **Never use cherry-pick or rebase** — upstream structure has diverged too much.

### Phase 1.5: Worktree Test & Speedup (MUST DO — 阻塞项)

**此步骤是 Phase 5 创建 PR 的前置条件。没有 worktree 测试通过记录和加速比数据，不允许进入 Phase 5。**

在 worktree 中运行测试和 benchmark，确认算子可用并获取加速比：

```bash
cd "$FLAGGEMS_REPO/.worktrees/gen-<op>"

# 使用空闲 NPU（先 npu-smi info 检查）
export ASCEND_VISIBLE_DEVICES=<空闲NPU编号>
export TRITON_ALL_BLOCKS_PARALLEL=1

# 1. 运行精度测试（必须全部 PASS）
# 昇腾需要 --ref cpu，因为 NPU 是 PrivateUse1 设备
python -m pytest tests/<test_file>.py -m <op> -vs --ref cpu

# 2. 运行 benchmark 获取加速比（记录输出中的 Speedup 列）
python -m pytest benchmark/<bench_file>.py -m <op> -s
```

**查找测试位置：**
```bash
grep -rn "def test_accuracy_<op>" .worktrees/gen-<op>/tests/
grep -rn "@pytest.mark.<op>" .worktrees/gen-<op>/benchmark/
```

记录 benchmark 输出的 Speedup 值，后续填入 PR 描述的 Performance 表格。

**昇腾特有注意事项：**
- `npu-smi info` 查看 NPU 状态（不是 `nvidia-smi`）
- `ASCEND_VISIBLE_DEVICES`（不是 `CUDA_VISIBLE_DEVICES`）
- `TRITON_ALL_BLOCKS_PARALLEL=1` 确保 Triton kernel 在 NPU 上正确并行
- 精度测试必须加 `--ref cpu`，benchmark 不加

**Benchmark 数据来源：**
如果 worktree 测试已在远程服务器完成，benchmark 结果保存在 `$FLAGGEMS_SUMMARY_JSON`
（典型路径形如 `<auto_gen>/results/ascend/summary.json`）：
```bash
echo "$FLAGGEMS_SUMMARY_JSON"
```
用 Python 提取对应算子的 `benchmark_results.data` 字段即可获取加速比数据，无需重新跑 benchmark。

### Phase 2: Code Preparation (5 files)

Prepare these 5 files for each Ascend operator:

#### 2.1 Kernel file: `src/flag_gems/runtime/backend/_ascend/ops/<op>.py`
- Copy from worktree: `.worktrees/gen-<op>/src/flag_gems/runtime/backend/_ascend/ops/<op>.py`
- **确保第一行是** `# Generated by KernelGen: https://github.com/flagos-ai/KernelGen`
- **Review checklist:**
  - Uses `logging` module, not `print()`
  - No duplicate function definitions
  - No unused `import torch` (pure triton kernels don't need it)
  - Functions follow naming convention (snake_case)
  - No meaningless wrappers (如 `_j1 = tl_extra_shim.j1`，直接内联调用)
  - No unnecessary if/else branches (如 pointwise_dynamic 已处理类型分发则不需要 isinstance 判断)
  - block_size 等超参应使用 autotune，hardcode 需要记录原因
  - If using `tl.extra.cuda.libdevice`, note potential cross-backend compatibility issue

#### 2.2 Register in `src/flag_gems/runtime/backend/_ascend/ops/__init__.py`
- Add import line in **alphabetical order**:
  ```python
  from .<op> import <func>
  ```
- Add exported names to `__all__` list in **alphabetical order**
- **注意**：昇腾使用 vendor backend 系统，不需要修改 `src/flag_gems/__init__.py` 的 `_FULL_CONFIG`

#### 2.3 Test file: `tests/test_<op>.py`
- **CRITICAL: 先检查 upstream 是否已有同名文件！**
  ```bash
  git show upstream/master:tests/test_<op>.py 2>/dev/null
  ```
  - **如果已有**（如 `bernoulli_` 已占用 `test_bernoulli.py`）→ **追加模式**：保留原文件所有内容，将新测试追加到文件末尾
  - **如果不存在** → 创建新的独立文件
- **追加模式时的规则：**
  - 保留原文件中所有已有代码（其他算子的测试）不动
  - 新增的测试追加到文件末尾
  - shapes/dtypes 参数应与同文件已有测试保持一致（如已有测试用 `utils.DISTRIBUTION_SHAPES`，新测试也应使用）
  - 不要自定义 shapes 列表（如 `BERNOULLI_SHAPES = [...]`），除非有明确理由
- **CRITICAL: 从 worktree 提取原始测试代码，不允许重写**
  1. 在 worktree 中找到对应测试函数：
     ```bash
     grep -rn "def test_accuracy_<op>" .worktrees/gen-<op>/tests/
     ```
  2. 提取该函数的完整代码（包括参数化装饰器、比较逻辑、atol 值等）
  3. 仅做以下改动：
     - 调整 import 为独立文件格式（`from . import accuracy_utils as utils`）
     - 函数名从 `test_accuracy_<op>` 改为 `test_<op>`
     - 去掉 vendor-specific 分支（如 `if flag_gems.vendor_name == "kunlunxin"`）
     - **追加模式时**：确保与同文件已有测试使用相同的 shapes/dtypes 常量
  4. **不改变**：比较逻辑（排序/abs/atol 值）、参数化方式、输入构造方式
- 提取后用 diff 验证：核心逻辑必须与 worktree 一致
- Template (仅当 worktree 中无测试时使用):
  ```python
  import pytest
  import torch

  import flag_gems

  from . import accuracy_utils as utils


  @pytest.mark.<op>
  @pytest.mark.parametrize("shape", utils.POINTWISE_SHAPES)
  @pytest.mark.parametrize("dtype", utils.FLOAT_DTYPES)
  def test_<op>(shape, dtype):
      inp = torch.randn(shape, dtype=dtype, device=flag_gems.device)
      ref_inp = utils.to_reference(inp)

      ref_out = torch.<op>(ref_inp)
      with flag_gems.use_gems():
          res_out = torch.<op>(inp)

      utils.gems_assert_close(res_out, ref_out, dtype)
  ```
- **Key rules:**
  - Relative import: `from . import accuracy_utils as utils`
  - pytest mark MUST match operator ID (not file name): `@pytest.mark.<op_id>`
    - For underscore-prefixed ops: strip the underscore in mark (e.g., `@pytest.mark.cholesky_solve_helper`)
  - Use `utils.to_reference` for golden reference
  - Use `gems_assert_close` (float) or `gems_assert_equal` (exact)
    - `gems_assert_close(res, ref, dtype, equal_nan=False, reduce_dim=1, atol=1e-4)`
    - **NO `rtol` parameter** — only `atol` is accepted
  - **No print()** — ever

#### 2.4 Benchmark file: `benchmark/test_<op>.py`
- **CRITICAL: 先检查 upstream 是否已有同名文件！**（与 test file 同理）
  ```bash
  git show upstream/master:benchmark/test_<op>.py 2>/dev/null
  ```
  - **如果已有** → **追加模式**：保留原文件，将新 benchmark 追加到末尾
  - **如果不存在** → 创建新的独立文件
- **追加模式时的规则：**
  - 保留原文件所有已有代码不动
  - `input_fn` 函数必须用描述性命名避免冲突（如 `bernoulli_input_fn`、`bernoulli_p_input_fn`，不要用泛型的 `input_fn`）
  - **代码组织顺序**：每个 `input_fn` 紧跟其对应的 `test_perf_*` 函数，不要把多个 `input_fn` 堆在一起
  - dtypes 使用 `consts.FLOAT_DTYPES`（与同文件已有代码保持一致）
- **Must be an independent file** (when no existing file)
- Template:
  ```python
  import pytest
  import torch

  from . import base, consts


  @pytest.mark.<op>
  def test_<op>():
      bench = base.UnaryPointwiseBenchmark(
          op_name="<op>",
          torch_op=torch.<op>,
          dtypes=consts.FLOAT_DTYPES,
      )
      bench.run()
  ```
- Choose benchmark class by operator type:
  - Unary pointwise → `base.UnaryPointwiseBenchmark`
  - Binary pointwise → `base.BinaryPointwiseBenchmark`
  - Reduction → `base.UnaryReductionBenchmark`
  - Linalg/custom input → **从 worktree 提取自定义 `Benchmark` 子类**
    - 在 worktree 的 `benchmark/test_special_perf.py` 中找到对应类
    - 关键：必须覆盖 `set_shapes` 方法，防止 CI `--level core` 覆盖 shapes
    - **不要使用 `GenericBenchmark` + 自定义 `input_fn`**（CI 会覆盖 shapes 导致崩溃）
    - 参考上游已 merge 的 `benchmark/test_grid_sample.py`
  - BLAS → `base.BlasBenchmark`
- **dtypes must use `consts.FLOAT_DTYPES`** — unless CUDA doesn't support Half (then hardcode `[torch.float32]` with comment)
- **Never write a custom benchmark framework**

#### 2.5 operators.yaml entry
- Insert in `conf/operators.yaml` in **alphabetical order** by `id`:
  ```yaml
  - id: <op>
    description: |
      <one-line description from PyTorch docs>
    for:
      - <aten_op_name>
    labels:
      - aten
      - KernelGen
      - pointwise  # or reduction, etc.
    kind:
      - Math  # or Reduction/NeuralNetwork/LinearAlg/Tensor
    stages:
      - alpha: '5.1'
  ```

### Phase 3: Automated Validation

Run the validation script to catch issues before pre-commit:

```bash
python <skill>/scripts/check_operator.py <op> --repo-dir "$FLAGGEMS_REPO"
```

The script checks:
- All 5 files exist (kernel, _ascend/__init__, test, benchmark, yaml)
- Registration in `_ascend/ops/__init__.py`
- operators.yaml entry completeness
- Duplicate function definitions
- print() usage
- Import conventions
- Upstream conflict
- Code quality (line length, trailing whitespace, EOF newline)

**All errors must be fixed before proceeding.** Warnings should be reviewed.

### Phase 4: Pre-commit

Run pre-commit on all changed files:

```bash
cd "$FLAGGEMS_REPO"
pre-commit run --files \
  src/flag_gems/runtime/backend/_ascend/ops/<op>.py \
  src/flag_gems/runtime/backend/_ascend/ops/__init__.py \
  tests/test_<op>.py \
  benchmark/test_<op>.py \
  conf/operators.yaml
```

**Common auto-fix cycle:**
1. Pre-commit may auto-fix formatting (black, isort, end-of-file-fixer, trailing-whitespace)
2. After auto-fix, re-stage the modified files
3. Run pre-commit again to verify all hooks pass
4. Repeat if flake8 still reports issues (F401 unused imports must be manually fixed)

### Phase 5: Commit & Push & Create PR (一步到位)

**此阶段将代码推送到 fork 并直接创建上游 PR，不再等待手动 review。**
**前提：Phase 1.5 的 worktree 测试必须已完成，加速比数据必须已获取。**

```bash
cd "$FLAGGEMS_REPO"

# 1. Stage ONLY the specific files — NEVER use git add -A or git add .
git add src/flag_gems/runtime/backend/_ascend/ops/<op>.py \
        src/flag_gems/runtime/backend/_ascend/ops/__init__.py \
        tests/test_<op>.py \
        benchmark/test_<op>.py \
        conf/operators.yaml

# 2. Commit (NO Co-Authored-By)
git commit -m "[KernelGen][Ascend] Add <op> operator with Triton kernel"

# 3. Push to fork (remote name: fork)
git push fork pr/ascend-<op>

# 4. 直接创建上游 PR（使用下方模板，必须填好描述）
```

**Critical git rules:**
- **NEVER `git add -A` or `git add .`** — repo has 687 worktrees and backup dirs
- **NEVER add Co-Authored-By** — will cause CLA check CI failure
- **NEVER commit `.gitignore` changes** — `.worktrees` 等本地忽略规则不属于算子 PR
- **验证 commit author** — commit 前必须确认 `git config user.name/email` 对应提 PR 所用的 GitHub 账号
  （CLA 检查以此为准）。脚本只校验、**绝不自动改写** `git config`；不匹配时由你手动决定怎么改。
  ```bash
  # 检查
  git config user.name && git config user.email
  # 如需固定期望身份，设置后脚本会据此校验
  export FLAGGEMS_GIT_NAME="<your-name>"
  export FLAGGEMS_GIT_EMAIL="<your-email>"
  ```
- Stage files individually by name
- Branch name: `pr/ascend-<op>`
- Push 到 fork remote（默认名 `fork`），不是 `upstream`

### Phase 6: Create Upstream PR (MUST fill description)

**必须在创建 PR 时填好完整的英文描述，包含加速比数据。不允许先创建空描述 PR 再补充。**

PR Description Template (MUST use English, reference: PR #3046):

```bash
gh pr create \
  --repo flagos-ai/FlagGems \
  --head "${FLAGGEMS_FORK_OWNER}:pr/ascend-<op>" \
  --base master \
  --title "[KernelGen][Ascend] Add <op> operator with Triton kernel" \
  --body "$(cat <<'EOF'
# [KernelGen][Ascend] Add <op> operator with Triton kernel

## Summary
Add `<op>` operator Triton kernel implementation for Ascend backend. <one-line description from PyTorch docs>.

## Testing
- Parametrized tests for <parameter dimensions (shape/dtype/special params)>
- Validated against PyTorch CPU-FP64 reference (`utils.to_reference` with `--ref cpu`)
- <if dtype restricted, explain: e.g., "Only float32 tested (NPU backend does not support Half)">

## Performance
| Configuration | Triton (μs) | Torch (μs) | Speedup |
|---|---|---|---|
| <shape1> | <triton_latency> | <torch_latency> | <speedup>x |

## Files Changed
- `src/flag_gems/runtime/backend/_ascend/ops/<op>.py`: Triton kernel implementation (Ascend)
- `src/flag_gems/runtime/backend/_ascend/ops/__init__.py`: Register import and `__all__`
- `tests/test_<op_id>.py`: Accuracy tests
- `benchmark/test_<op_id>.py`: Performance benchmarks
- `conf/operators.yaml`: Add operator entry (kind: <kind>, stage: alpha 5.1)
EOF
)"
```

**PR description rules:**
- **MUST be in English** — all sections
- Must include **Summary / Testing / Performance / Files Changed** sections
- Performance table must contain actual measured speedup (run benchmark in worktree before submitting)
- Files Changed must list accurate file paths — no garbled URLs
- `<op_id>` in file list is the name without leading underscore (e.g., `test_cholesky_solve_helper.py`)

### Phase 7: Backfill PR Link (MUST DO)

PR 创建成功后，**必须**将链接回填到 `规范名.xlsx`：

```bash
python <skill>/scripts/operator_registry.py backfill <operator_name> <pr_url>
```

示例：
```bash
python <skill>/scripts/operator_registry.py \
  backfill _cholesky_solve_helper https://github.com/flagos-ai/FlagGems/pull/3354
```

**查看待提交/已提交状态：**
```bash
# 列出待提交的算子（按加速比排序）
python .../operator_registry.py pending --limit 20

# 列出已提交的算子
python .../operator_registry.py submitted
```

## Code Review Focus Points

When reviewing Ascend operator code, pay special attention to:

1. **Duplicate functions** — same function defined twice will silently override
2. **Unused imports** — especially `import torch` in pure triton kernels (flake8 F401)
3. **print() usage** — forbidden in both kernel and test files
4. **Import style** — must use relative imports in test/benchmark, top-level imports only
5. **Registration completeness** — `_ascend/ops/__init__.py` + yaml（昇腾只有 2 个注册点）
6. **Alphabetical ordering** — imports, __all__, yaml entries
7. **pytest mark alignment** — mark name must exactly match operator ID
8. **Benchmark class choice** — must use the appropriate base class, never custom framework
9. **Naming convention** — aten ops use snake_case, fused ops use PascalCase for ID
10. **Dead code** — kernel 文件中未注册、未测试、未导出的函数必须删除（如未用的 inplace 版本）
11. **Triton 实现验证** — 核心计算必须在 `@triton.jit` 函数中完成，不允许用 torch 做核心计算
12. **`@use_tl_extra` 桩函数** — 只保留 kernel 中实际调用的；未调用的（如多余的 `exp`/`pow`）必须删除
13. **昇腾特有：`tle.program_id`** — 昇腾 Triton 使用 `tle.program_id()` 而非 `tl.program_id()`
14. **昇腾特有：`CORE_NUM`** — 需正确设置 grid 中的 core 数量参数
15. **昇腾特有：libdevice 兼容性** — `tl.extra.cuda.libdevice` 在昇腾上可能不可用，需用 `tl.math` 或 `tl_extra_shim`

## Reference Materials

- `references/pr-checklist.md` — detailed per-item checklist for each PR
- `references/common-issues.md` — historical review issues and solutions
- `scripts/check_operator.py` — automated validation script (Ascend version)

## Batch Submission Notes

When submitting multiple operators:
- Process 10-20 PRs per batch
- Wait 1-2 minutes between PR submissions (Rule 27) — back-to-back submissions get some CI jobs dropped
- Sleep 5 seconds between gh API calls to avoid rate limits
- Prioritize pointwise operators (simpler, reviewed faster)
- Log success/failure for each operator
