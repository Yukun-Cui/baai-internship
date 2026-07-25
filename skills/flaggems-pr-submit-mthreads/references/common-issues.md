# FlagGems 摩尔线程特化 PR Review 常见问题

摩尔线程(Moore Threads/MUSA)特化算子提交前务必逐条排查。

## 1. 设备判定问题

- **必须用 `"musa"`**：摩尔线程张量 `device.type == "musa"`，**不是** `"cuda"`
- 错误示例：`if x.device.type != "cuda": ...` → 特化永远不会触发
- 正确：`if x.device.type != "musa": return default_<op>(...)`

## 2. Fallback（回退）问题

摩尔线程特化覆盖通用算子，必须在不满足条件时回退，否则会崩溃或算错：

- 非 musa 设备 → 回退 `default_<op>`
- dtype 不在白名单（尤其 fp64/int64）→ 回退
- 空 tensor / 非 contiguous / 特殊 layout → 回退
- 回退目标必须来自 `from flag_gems.ops.<op> import <op> as default_<op>`
- **禁止无条件透传** `default_<op>`（那样等于没做特化，anti-hack 会拦）

## 3. fp64/int64 不支持

摩尔线程硬件 `VendorDescriptor.fp64_enabled = False`：

- kernel 内需 double/long 计算时，转 `tl.float32` / `tl.int32`
- 或用 `_SUPPORTED_DTYPES` 白名单过滤，不支持的 dtype 回退通用实现
- 通用测试 `tests/test_<op>.py` 若含 fp64 参数，应通过 fallback 正确处理，而非报错

## 4. libdevice 兼容性（重要）

- **禁止** `tl.extra.cuda.libdevice.xxx` — MUSA 上不存在，会崩溃
- 用 `from flag_gems.utils import tl_extra_shim` 后 `exp = tl_extra_shim.exp` 等
- 或用 Triton 内置 `tl.math.*`

## 5. Logger 命名与文案

### 5.1 Logger 命名（易错点）

- 摩尔线程后端 **不用** 主文件夹写法 `logging.getLogger(__name__)`
- 必须用后端专用写法（与上游 `_mthreads/ops/celu.py`、`log.py`、`mm.py` 一致）：
  ```python
  logger = logging.getLogger(
      f'flag_gems.runtime.backend._mthreads.ops.{__name__.split(".")[-1]}'
  )
  ```
- 说明：`__name__.split(".")[-1]` 取模块名末段（如 `celu`），显式拼上
  `flag_gems.runtime.backend._mthreads.ops.` 前缀，保证 vendor backend 动态加载时
  logger 层级稳定，不受导入路径 / `__name__` 变化影响
- auto_gen 从通用层复制模板时常残留 `getLogger(__name__)`，提交前务必替换

### 5.2 Logger 文案

- 摩尔线程特化用 `logger.debug("GEMS_MTHREADS <OP>")`（算子名大写，如 `GEMS_MTHREADS CELU`）
- 与通用算子的 `GEMS <OP>` 区分，便于确认走的是特化路径
- 应是 wrapper docstring 后第一条有意义语句
- **测试时必须在输出看到这条日志**，否则说明 `replace_customized_ops()` 未替换（注册有问题）

## 6. 注册问题（_mthreads/ops/__init__.py）

- `__init__.py` 有 **device_capability 分区**：BLAS 类算子（addmm/bmm/mm/gelu/tanh）在
  `if get_device_capability(current_device())[0] >= 3:` 块内注册，其余在顶层
- import 和 `__all__` 都按字母序（分区内各自有序）
- 只导出 wrapper 函数，不导出 `@triton.jit` kernel
- 特化算子放错分区会导致低算力卡上 import 失败或高算力卡上不注册

## 7. 复用上游测试/benchmark

- 摩尔线程特化验证用的是通用层**已有**的 `tests/test_<op>.py` / `benchmark/test_<op>.py`
- **禁止修改这些文件**（会破坏其他后端的测试）
- 只有上游确实缺失独立测试文件时才新建（参考 `tests/test_relu.py`），此时才作为提交项
- 不改 `conf/operators.yaml`（通用算子已有条目）

## 8. worktree import 问题

- 环境中 `flag_gems` 以 editable 模式全局装于 `/root/FlagGems/src/`，直接 pytest 会加载全局版而非 worktree 版
- **必须**用 `/root/baai-internship/auto_gen/fix_worktree_import.py`，且先 `cd` 进 worktree 目录
- 验证：`fix_worktree_import.py -c "import flag_gems; print(flag_gems.__file__)"` 应指向 worktree

## 9. 代码质量

- 无重复函数定义（同名后者覆盖前者）
- 无未使用 import（纯 triton kernel 若不用 `torch` 则删掉，flake8 F401）
- 不做无意义封装（如 `_j1 = tl_extra_shim.j1` 直接用原函数）
- 超参用 `@triton.autotune`（参考 `celu.py`），hardcode 需注释
- 行长 ≤120，文件末尾有换行

## 10. git 操作

- **绝不用 `git add -A` / `git add .`**（仓库有大量 worktree）
- 逐文件 stage，通常只有 2 个：kernel + `_mthreads/ops/__init__.py`
- commit message：`[KernelGen][MThreads] Add <op> Moore Threads specialized operator`
- **无 Co-Authored-By / AI 署名**（🤖、Generated with 等），否则 CLA CI 失败
- 分支 `pr/mthreads-<op>`，基于 `upstream/master`
- push 前 `git fetch upstream` 确认无冲突

## 11. 环境命令对照（勿混用其他后端）

| 用途 | NVIDIA | 昇腾 | 摩尔线程 |
|------|--------|------|---------|
| 卡状态 | `nvidia-smi` | `npu-smi info` | `mthreads-gmi` |
| 指定卡 | `CUDA_VISIBLE_DEVICES` | `ASCEND_VISIBLE_DEVICES` | `MUSA_VISIBLE_DEVICES` |
| device.type | `cuda` | `npu` | `musa` |
