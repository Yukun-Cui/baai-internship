# FlagGems PR Review 常见问题

来自历史 PR Review 的经验总结，提交前务必逐条排查。

## 1. 算子命名问题

### 命名转换规则
- aten 算子需要进行名字转换（例如 `a.out` → `a_out`，`a.self_out` → `a_self_out`）
- **前导下划线去除（mark 和 yaml id 中）**：`_foo` → `foo`
  - 文件名、函数名、import、`_FULL_CONFIG` 的 aten name 保留下划线
  - 只有 pytest mark 和 yaml `id` 去掉前导下划线
  - 例如：`_cholesky_solve_helper` → yaml `id: cholesky_solve_helper`，mark `@pytest.mark.cholesky_solve_helper`
- 尾部下划线保留：`b_` → `b_`（inplace 变体）
- fused 算子以算子本身名称为 ID，不用参考实现的名称
- **禁止随意 mark**

### 命名冲突
- 提交前必须检查是否与现有算子冲突
- 运行：`grep "id: <op>" conf/operators.yaml`

## 2. 测试文件问题

### 禁止 print
- 测试中 `print()` 会干扰正常数据采集
- 跳过测例用 `@pytest.mark.skip(reason=…)`

### 运行时间
- 注意测试运行时间，避免不必要的开销
- 审视是否真的需要很重的 shapes 来执行精度测试

### mark 不匹配
- 测例的 mark 必须与算子 ID 严格匹配
- 错误示例：算子名 `special_erfcx` 但 mark 是 `@pytest.mark.erfcx`

## 3. Benchmark 问题

### 禁止自定义框架
- **必须使用 pytest + base 封装类**
- 不允许用自定义框架替代 pytest

### 封装类选择
| 算子类型 | 使用的类 |
|---------|---------|
| 一元 pointwise | `base.UnaryPointwiseBenchmark` |
| 二元 pointwise | `base.BinaryPointwiseBenchmark` |
| Reduction | `base.ReductionBenchmark` |
| Linalg/自定义 | 继承 `base.OperationBenchmark`，实现 `get_input_iter` |

### dtypes 不要硬编码
- **必须使用 `consts.FLOAT_DTYPES`**，不要写 `[torch.float32]`
- 参考已合入的 PR（如 #3278 atan2）

## 4. 代码质量问题

### 无意义代码
- 不提交无意义的代码片段
- 不用无意义的冗余函数名
- 不做无意义的封装

### Import 规范
- 禁止奇怪的 import（如 `from flag_gems.fused import fp8_einsum, fp8_einsum_ref`）
- import 放在文件顶部，不在函数中间 import

### 日志规范
- 算子名使用 `logger.debug` 输出，不用 `print`

### 重复函数
- 检查是否有重复的函数定义（同名函数会互相覆盖）
- 检查 kernel 函数名与导出函数名是否合理

## 5. 文件与格式规范

- 遵循项目命名约定，不乱起文件名
- 维持已有列表的排列顺序（字母序），不随意打乱
- 文件末尾必须有换行
- 行长度不超过 120 字符

## 6. 上游结构差异（重要）

当前上游已大幅重构，**不能直接 cherry-pick**：

| 项目 | 旧格式 | 上游当前格式 |
|------|-------|------------|
| 测试文件 | 共享文件追加 | 每算子独立文件 `tests/test_<op>.py` |
| Benchmark | 共享文件追加 | 每算子独立文件 `benchmark/test_<op>.py` |
| Benchmark API | 直接 pytest parametrize | `base.UnaryPointwiseBenchmark()` 等封装类 |
| operators.yaml | `name` 字段 | `id` 字段 |

## 7. pre-commit 常见问题

| Hook | 常见问题 | 修复方法 |
|------|---------|---------|
| `end-of-file-fixer` | 文件末尾缺换行 | 自动修复，重新 stage |
| `flake8` | `F401` 未使用的 import | 删掉多余 import（如 kernel 中不需要的 `import torch`） |
| `flake8` | `F401` 未使用的 `consts` | benchmark 中不 import `consts` 除非真的用了 |
| `isort` | import 顺序不对 | 自动修复，重新 stage |
| `black` | 格式不对 | 自动修复，重新 stage |
| `trailing-whitespace` | 行尾有空白 | 自动修复，重新 stage |

## 8. libdevice 兼容性

- 部分算子使用了 `tl.extra.cuda.libdevice`（如 special_erfcx）
- 上游要求跨后端兼容
- 如果 reviewer 提出此问题，需改用 `tl_extra_shim`

## 9. special.* 算子 aten dispatch 格式

yaml `for` 字段和 `_FULL_CONFIG` 注册中，`special` 类算子**必须用 dot 格式**：

| 位置 | 错误 | 正确 |
|------|------|------|
| yaml `for` | `special_chebyshev_polynomial_v` | `special.chebyshev_polynomial_v` |
| `_FULL_CONFIG` | `("special_chebyshev_polynomial_v", ...)` | `("special.chebyshev_polynomial_v", ...)` |

> **注意**：上游已有的 `special_i1` 用了下划线格式（历史遗留），但 reviewer Qiming Teng 在 PR #3539 中明确要求新提交的 special.* 算子使用 dot 格式。`extract_from_worktree.py` 已自动修正。

## 10. inplace 变体完整性

导出了 `xxx_`（inplace）函数时，以下**全部必须有**，否则 reviewer 会拒绝：

| 位置 | 要求 |
|------|------|
| `__all__` / `ops/__init__.py` | 导出 `xxx_` |
| `_FULL_CONFIG` | 注册 `("xxx_", xxx_)` |
| `operators.yaml` | 独立条目 `id: xxx_` |
| 测试文件 | `test_xxx_` 函数，mark 为 `@pytest.mark.xxx_` |
| benchmark | `test_xxx_` 函数（建议有，缺少为 warning） |

**inplace 测试必须比较 mutated input**：不能只 assert 返回值 `res_out`，要同时比较被修改的 `inp1` 与 `ref_inp1`。（PR #3542 tengqm 明确要求）

## 11. kernel 全局变量

Reviewer Qiming Teng 明确表示 "I really hate global vars"（PR #3537）。

**禁止**：在 kernel 文件模块级别定义非常量的全局变量（如 `_original_resize_method = torch.Tensor.resize_`）。

**正确做法**：将变量移入函数体内，或用 `torch.ops.aten.xxx` 直接调用避免递归。

## 12. 多变体 mark 规则

真实 variant / overload 的 mark 必须独立，helper / edge-case 测试应保留所属 canonical operator mark，不能为了函数名唯一而发明非 yaml mark。

**真实 variant 示例**（PR #3542）：
```python
@pytest.mark.true_divide          # ✗ 应为 true_divide_tensor_scalar
def test_true_divide_tensor_scalar(...):
```

```python
@pytest.mark.true_divide_tensor_scalar  # ✓ 真实 variant 独立覆盖
def test_true_divide_tensor_scalar(...):
```

**helper / edge-case 示例**：
```python
@pytest.mark.reflection_pad3d  # ✓ 仍属于 canonical operator
def test_reflection_pad3d_list_padding(...):
```

`_check_mark_opname_per_function` 只对真实 variant 强制独立 mark；helper case 允许 canonical mark。

## 13. git 操作注意

- ❌ **禁止 `git add -A` 或 `git add .`**（仓库有 687 个 worktree 和大目录）
- ❌ **禁止 cherry-pick**（worktree 代码结构与上游不同，容易带入旧基线并造成 PR merge conflict）
- ❌ **禁止 rebase**（分支基于 upstream/master 创建，不需要）
- 必须逐文件 stage
- 分支命名统一用 `pr/<operator>`
- 每个分支基于 `upstream/master` 创建


## 14. variant / canonical ID 覆盖

新增算子前先查 `conf/operators.yaml`、`_FULL_CONFIG`、tests、benchmark，确认 base / inplace / out / scalar / tensor / alias 是否已有 precedent。

- 真实 ATen variant（inplace、out、Scalar、Tensor overload）应有对应 yaml id、pytest mark、benchmark `op_name`、测试函数和注册。
- alias 到已有 canonical ATen operator 时，不新造不在 yaml/predecessor 中存在的 mark 或 `op_name`。
- mark / benchmark `op_name` 以 `operators.yaml id` 和 sibling precedent 为准，不以生成器文件名为准。

## 15. benchmark op_name

`op_name` 必须使用 canonical operator id 或真实 variant id，通常与 `conf/operators.yaml` 的 `id` 一致。

- 不要用参数化 f-string 生成 `op_name`，例如 `upsample_trilinear3d_align_True`。
- 同一个 benchmark 覆盖不同参数组合时，用 pytest 参数区分 case，不改变 `op_name`。
- scalar/tensor/out/inplace 等真实 variant（如 `div_scalar`、`div_tensor`、`*_out`、`*_`）必须先对照 yaml 和 sibling benchmark，不能误合并到 base `op_name`。

## 16. logger 格式

- 通用 backend / Nvidia 通用算子使用 `GEMS <OP>`，op name uppercase，例如 `GEMS RENORM`、`GEMS RENORM_`。
- backend customized / specialized op 按最新 reviewer 约定使用 `GEMS_VENDOR <OP>`，其中 `VENDOR` 和 `OP` 都 uppercase。
- 不要自造 `<VENDOR> GEMS <OP>`、`<VENDOR>_GEMS <OP>` 等未确认格式。
- 加 logger 前先对照同 backend/sibling ops 和最近 reviewer 结论。

## 17. autotune 配置外置

大段 inline `triton.Config(...)` 会被自动 review 提醒。新增 autotune kernel 时，优先使用 `runtime.get_tuned_config("<op>")`。

- Nvidia 通用算子在 `src/flag_gems/runtime/backend/_nvidia/tune_configs.yaml` 增加对应配置。
- 如果确实必须 inline autotune，需要说明原因，并对照 repo 现有例外模式。

## 18. YAML 文案质量

`conf/operators.yaml` 中 `description` 等长文本应使用 block scalar `|` 或合理换行，不提交超过 120 字符的单行描述。长 description 应对照 sibling ops 的 yaml 文案风格。

## 19. dispatch / direct path validation

不能只依赖 public API 测试通过，要证明 FlagGems kernel 实际被执行。

- 如果 `torch.<op>` 在 `flag_gems.use_gems()` 下可能绕过注册实现，必须增加直接 wrapper 或 `torch.ops.aten.<op>` 测试。
- 对 autograd Function 类实现，必须至少增加一个 backward smoke test，确认 `.backward()` 能跑且关键 gradients 非空/正确。

## 20. 新提交分支冲突预防

- 新算子提交前必须 `git fetch upstream master`。
- `check_operator.py` 必须通过“上游冲突检查”：当前分支既不能提交上游已存在的算子，也必须能与 `upstream/master` 无冲突合并。
- 如果上游冲突检查失败，本次新提交必须重新基于最新 `upstream/master` 创建分支并重新提取算子，不能把冲突分支提交成 PR。

## 21. 普通算子 PR 不改全局 infra

普通 KernelGen 算子 PR 只解决当前算子的实现、注册、测试和 benchmark，不顺手修 CI 依赖或全局环境。

**禁止出现在普通算子 PR diff 中**：
- `tools/vendor.sh`
- `setup.sh`
- `tools/env.sh`
- `.github/workflows/**`
- `container/**`
- `pyproject.toml`
- 全局依赖 pin / build 环境文件

如果 CI 在依赖解析、安装 torch/triton、checkout、容器初始化等阶段失败，先按 upstream/infra 环境问题记录。不要在算子 PR 中改 dependency pin 绕过；应等待 upstream 修复，或基于最新 `upstream/master` 重新创建干净分支并重新提取算子。

## 22. PR diff 文件列表必须 reviewer 友好

“文件最终内容和 upstream 一样”不代表 GitHub PR diff 会干净。请求 review 前必须看 reviewer 实际会看到的 diff：

```bash
gh pr diff <PR> --repo flagos-ai/FlagGems --name-only
```

普通算子 PR 通常只允许以下文件：
- `src/flag_gems/ops/<op>.py`
- `tests/test_<op>.py`
- `benchmark/test_<op>.py`
- `conf/operators.yaml`
- `src/flag_gems/__init__.py`
- `src/flag_gems/ops/__init__.py`

仅在当前算子确实需要时，额外允许：
- `src/flag_gems/runtime/backend/_nvidia/tune_configs.yaml`
- `benchmark/core_shapes.yaml`

如果出现无关文件，不要用 infra patch 掩盖，也不要把无关改动留给 reviewer 解释；重新基于最新 `upstream/master` 创建干净分支并重新提取/提交当前算子。

## 23. logger.debug 的位置

logger 文案格式正确还不够。public wrapper 中的 debug call 应放在 docstring 后第一条有意义语句：

```python
def foo(x):
    logger.debug("GEMS FOO")
    ...
```

不要先做 shape normalization、dtype cast、input validation 后才打日志。例外必须能用同类 sibling 算子 precedent 解释。通用算子使用 `GEMS <OP>`，backend 特化使用 `GEMS_VENDOR <OP>`，均 uppercase。

## 24. Benchmark class 和 override 噪音

Reviewer 不喜欢 benchmark 里藏在 test function 内的 class，也不喜欢没有行为变化的 override。

正确模式：
- 自定义 benchmark class 放在 module scope。
- `test_<op>()` 只实例化 benchmark 并调用 `run()`。
- 只有确实改变 shapes、输入构造或 benchmark 行为时才覆盖 `set_shapes()` / `set_more_shapes()`。

错误模式：
```python
def test_foo():
    class FooBenchmark(base.OperationBenchmark):
        ...
```

错误模式：
```python
def set_shapes(self):
    super().set_shapes()
```

## 25. PR body 和 skip/xfail 文案

PR body 是 reviewer-facing 文档，不能暴露自动化内部状态。

不要提交：
- `operator not in summary`
- `TODO`
- `FIXME`
- `UNKNOWN`
- parser/debug/artifact 等调试词

使用：
- `Not benchmarked`
- `Not applicable`
- `Skipped: <short reason>`

新增 `pytest.mark.skip`、`skipif`、`xfail` 时，reason 必须包含 issue URL 或 `#<number>`。如果没有 issue，不要静默跳过；先报告 BLOCKED 或让用户决定是否创建 issue。
