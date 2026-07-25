# 摩尔线程(Moore Threads)特化算子 PR 状态记录

记录提交流程中的失败、warning、低加速比（特化未优于通用）、CI 不过、hardcode 超参、
PR 创建事件等。每条包含：日期、算子、事件类型、说明。

> 规范名映射和待提交列表默认复用 `../flaggems-pr-submit/data/` 下的
> `规范名.xlsx` 与 `第一批pr算子.xlsx`；如需独立数据，放到本目录并同名即可覆盖。

## 事件记录

| 日期 | 算子 | 类型 | 说明 |
|------|------|------|------|
| 2026-07-24 | linalg_cholesky | 测试失败-未提交 | fp64 fallback 触发 RecursionError（replace_customized_ops 替换后 default_linalg_cholesky 指向 wrapper 自身）；batch fp32 路径出现 BmmCall MUDNN NOT_SUPPORTED。10/20 tests failed。内核需彻底修复 fallback 机制后再提交。 |
| 2026-07-24 | median | 无 worktree-未提交 | .worktrees/gen-median 不存在，无预生成内核，跳过。 |
| 2026-07-24 | histc | 低加速比-小 shape | sizes [64,64] speedup=0.77x、[256,256] speedup=0.76x，大 shape 显著加速（geomean 1.95x），已提交 PR#114。 |
