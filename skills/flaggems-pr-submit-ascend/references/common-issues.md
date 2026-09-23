# FlagGems PR Review 常见问题

来自历史 PR Review 的经验总结，提交前务必逐条排查。

## 1. 算子命名问题

### 命名转换规则
- aten 算子需要进行名字转换（例如 `a.out` → `a_out`，`a.self_out` → `a_self_out`）
- **前导下划线去除（mark 和 yaml id 中）**：`_foo` → `foo`
  - 文件名、函数名、import 保留下划线
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

## 9. git 操作注意

- **绝不用 `git add -A` 或 `git add .`**（仓库有 687 个 worktree 和大目录）
- 必须逐文件 stage
- 分支命名统一用 `pr/ascend-<operator>`
- 每个分支基于 `upstream/master` 创建
