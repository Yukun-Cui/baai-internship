# 摩尔线程(Moore Threads)特化算子 PR 状态记录

记录提交流程中的失败、warning、低加速比（特化未优于通用）、CI 不过、hardcode 超参、
PR 创建事件等。每条包含：日期、算子、事件类型、说明。

> 规范名映射和待提交列表默认复用 `../flaggems-pr-submit/data/` 下的
> `规范名.xlsx` 与 `第一批pr算子.xlsx`；如需独立数据，放到本目录并同名即可覆盖。

## 事件记录

| 日期 | 算子 | 类型 | 说明 |
|------|------|------|------|
| 2026-07-24 | linalg_cholesky | 测试失败-未提交 | fp64 fallback 触发 RecursionError（replace_customized_ops 替换后 default_linalg_cholesky 指向 wrapper 自身）；batch fp32 路径出现 BmmCall MUDNN NOT_SUPPORTED。10/20 tests failed。内核需彻底修复 fallback 机制后再提交。 |
| 2026-07-27 | linalg_cholesky | 提交 PR#133 | 内核已被重写(right-looking/并行行/debug_barrier)，RecursionError 不再复现。修复：Rule7 logger 命名；fp64 移出 _SUPPORTED_DTYPES(硬件 support_fp64=False，fp64 回退通用)；按 Rule15 门控 tests(3处)+benchmark(1处)硬编码 fp64。fp32 全过 10 passed，geomean 1.29x。注意 256×256=0.365x(顺序列循环，大 N 劣于 vendor)。剩余 fp64 batch 的 BmmCall MUDNN failed 是输入构造阶段 torch fp64 bmm 限制，门控后不触发。 |
| 2026-07-27 | 全部(#128/#129/#133) | 分支污染-已修 | 本地 upstream/master 陈旧(1cd434cc=被上游丢弃的#98 Metax)，真实 master 已到 62e172e 不含它。基于陈旧 ref 建分支→merge-base 退化→#98 引入的 4 个 _metax 文件泄漏进 PR diff(gh pr view files 可见，本地 git diff 看不出)。已 fetch 真实 master + cherry-pick 重建干净分支 + force push 修复。#127 因先于重写推送而幸免。 |
| 2026-07-24 | median | 无 worktree-未提交 | .worktrees/gen-median 不存在，无预生成内核，跳过。 |
| 2026-07-24 | histc | 低加速比-小 shape | sizes [64,64] speedup=0.77x、[256,256] speedup=0.76x，大 shape 显著加速（geomean 1.95x），已提交 PR#114。 |
| 2026-07-27 | trunc | 提交 | worktree 现已存在（此前无）。18/18 accuracy PASS，geomean 1.24x。通用算子在上游 trunc_.py（preflight/check_operator 按 trunc.py 找会误报 warning，实为存在）。 |
| 2026-07-27 | round_ | 提交 | 18/18 accuracy PASS，geomean 1.33x。通用算子在上游 round.py。仅特化 decimals==0 常用路径，其余回退通用。 |
| 2026-07-27 | median | 提交 | worktree 现已存在（此前记录为无）。431 passed/23 skipped/2 failed。2 个 failure 为 torch_musa 限制：torch.arange(dtype=torch.int16) 报 "unsupported data type Short"，发生在输入构造阶段(test line 1350)，与特化无关，通用实现同样会失败，CUDA CI 不受影响。geomean 1.43x（部分 4096 shape <1.0，如 [4096] 0.25x，因内核限 _SORT_SELECT_LIMIT=8192 内 in-register sort）。按 Rule 15 门控了 test_median.py 3 处硬编码 fp64（test_median_extra_no_dim_dtypes 参数化 + 2 个 test_median_float64_* 加 skipif），故本 PR 含 tests/test_median.py。 |
