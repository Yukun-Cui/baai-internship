# PR 提交状态记录

`submit_operator.py` 会把每个算子的提交事件（FAIL / PR_CREATED / LOW_SPEEDUP 等）追加到本文件。
新环境从这份空表开始；历史运行记录属于工作数据，不随仓库提交。

| 时间 | 算子 | 事件 | 说明 |
|------|------|------|------|
| 2026-08-05 02:41 | replication_pad1d_backward | FAIL | GH_TOKEN is not set; export GH_TOKEN or pass --token before creating a PR |
| 2026-08-05 02:41 | replication_pad1d_backward | FAIL | 只找到 3 个文件（需要 6 个）: ['src/flag_gems/ops/__init__.py', 'src/flag_gems/__init__.py', 'conf/operators.ya |
| 2026-08-05 02:42 | replication_pad1d_backward | FAIL | 只找到 3 个文件（需要 6 个）: ['src/flag_gems/ops/__init__.py', 'src/flag_gems/__init__.py', 'conf/operators.ya |
| 2026-08-05 02:43 | replication_pad1d_backward | FAIL | 只找到 3 个文件（需要 6 个）: ['src/flag_gems/ops/__init__.py', 'src/flag_gems/__init__.py', 'conf/operators.ya |
| 2026-08-05 02:44 | replication_pad1d_backward | FAIL | 命令失败 (exit 1): python /root/baai-internship/skills/flaggems-pr-submit/scripts/check_operator.py repl |
| 2026-08-05 02:52 | replication_pad1d_backward | FAIL | GH_TOKEN is not set; export GH_TOKEN or pass --token before creating a PR |
| 2026-08-05 02:53 | replication_pad1d_backward | FAIL | 只找到 3 个文件（需要 6 个）: ['src/flag_gems/ops/__init__.py', 'src/flag_gems/__init__.py', 'conf/operators.ya |
| 2026-08-05 02:54 | replication_pad1d_backward | FAIL | 命令失败 (exit 1): python /root/baai-internship/skills/flaggems-pr-submit/scripts/check_operator.py repl |
| 2026-08-05 02:54 | replication_pad1d_backward | FAIL | 命令失败 (exit 1): python /root/baai-internship/skills/flaggems-pr-submit/scripts/check_operator.py repl |
| 2026-08-05 03:20 | replication_pad1d_backward | FAIL | 只找到 3 个文件（需要 6 个）: ['src/flag_gems/ops/__init__.py', 'src/flag_gems/__init__.py', 'conf/operators.ya |
| 2026-08-05 03:21 | replication_pad1d_backward | FAIL | 命令失败 (exit 1): python /root/baai-internship/skills/flaggems-pr-submit/scripts/check_operator.py repl |
| 2026-08-14 08:18 | _cslt_compress | FAIL | 命令失败 (exit 1): python /root/baai-internship/skills/flaggems-pr-submit/scripts/check_operator.py _csl |
| 2026-08-14 08:24 | _cslt_compress | FAIL | 命令失败 (exit 128): git push origin HEAD:pr/_cslt_compress |
| 2026-08-14 08:28 | _cslt_compress | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/5492 |
| 2026-08-14 08:51 | _cslt_sparse_mm_search | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/5495 |
| 2026-08-14 09:14 | _conj_physical | FAIL | 命令失败 (exit 1): python /root/baai-internship/skills/flaggems-pr-submit/scripts/check_operator.py _con |
| 2026-08-14 09:15 | _conj_physical | FAIL | pre-commit 3 次尝试后仍失败 |
| 2026-08-14 09:16 | _conj_physical | FAIL | 本地测试失败: ING  root:error.py:30 Skipped registering operator: This is not allowed since there's alread |
| 2026-08-14 09:23 | _conj_physical | FAIL | 命令失败 (exit 128): git push origin HEAD:pr/_conj_physical |
| 2026-08-14 09:25 | _conj_physical | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/5498 |
| 2026-08-14 09:56 | _add_relu_ | FAIL | 本地测试失败: t.py'. tests/conftest.py:27: in <module>     import flag_gems src/flag_gems/__init__.py:25:  |
| 2026-08-14 10:06 | _add_relu_ | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/5502 |
| 2026-08-14 10:08 | _amp_update_scale_ | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/5503 |
| 2026-08-14 10:09 | _batch_norm_impl_index_backward | FAIL | pre-commit 3 次尝试后仍失败 |
| 2026-08-14 10:10 | _batch_norm_impl_index_backward | FAIL | pre-commit 3 次尝试后仍失败 |
| 2026-08-14 10:18 | _batch_norm_impl_index_backward | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/5504 |
| 2026-08-14 10:22 | _convolution_double_backward | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/5505 |
| 2026-08-16 07:57 | _aminmax | FAIL | 命令失败 (exit 128): git push origin HEAD:pr/_aminmax |
| 2026-08-16 07:58 | _aminmax | FAIL | 本地测试失败: sts/conftest.py:27: in <module>     import flag_gems src/flag_gems/__init__.py:25: in <modul |
| 2026-08-16 08:03 | _aminmax | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/5511 |
| 2026-08-16 08:06 | _convolution_mode | FAIL | pre-commit 3 次尝试后仍失败 |
| 2026-08-16 08:12 | _convolution_mode | LOW_SPEEDUP | 平均 speedup 0.463 低于阈值 0.6，继续提交，仅作为性能提醒 |
| 2026-08-16 08:12 | _convolution_mode | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/5512 |
| 2026-08-16 11:06 | _conj_copy | FAIL | 命令失败 (exit 128): git push origin HEAD:pr/_conj_copy |
| 2026-08-16 11:09 | _conj_copy | FAIL | 本地测试失败: ImportError while loading conftest '/root/FlagGems/tests/conftest.py'. tests/conftest.py:27: |
| 2026-08-16 11:13 | _conj_copy | FAIL | 本地测试失败: ============================= test session starts ============================== platform li |
| 2026-08-16 11:18 | _conj_copy | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/5513 |
| 2026-08-16 11:20 | _compute_linear_combination | FAIL | 本地测试失败: opt.enable_fp_fusion, False) E       Failed: Timeout (>60.0s) from pytest-timeout.  /usr/loc |
| 2026-08-16 11:25 | _coalesced_ | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/5514 |
| 2026-08-16 12:06 | _compute_linear_combination | FAIL | 命令超时 (60s): python /root/baai-internship/skills/flaggems-pr-submit/scripts/check_operator.py _comput |
| 2026-08-16 12:08 | _compute_linear_combination | FAIL | 命令超时 (60s): python /root/baai-internship/skills/flaggems-pr-submit/scripts/check_operator.py _comput |
| 2026-08-16 12:11 | _compute_linear_combination | FAIL | 命令超时 (60s): python /root/baai-internship/skills/flaggems-pr-submit/scripts/check_operator.py _comput |
| 2026-08-16 12:21 | _compute_linear_combination | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/5515 |
| 2026-08-16 13:50 | _conj_copy | CI_FIX | #5513 benchmark torch_op=torch._conj_copy.out AttributeError → 改 torch.ops.aten._conj_copy.out (已push e655ce30f) |
| 2026-08-16 13:50 | _coalesced_ | CI_FIX | #5514 test_coalesced_ quick-cpu to_cpu AssertionError → ref_inp1 加 utils.to_reference (已push a6cbf7c64) |
| 2026-08-16 14:35 | _compute_linear_combination | CI_FIX | #5515 out测试缺out=参数+empty未初始化累加bug; benchmark torch._compute_linear_combination.out不存在→aten .out; op_name对齐yaml id (已push ba0810145) |
| 2026-08-16 14:55 | _conj_copy | CI_PASS | #5513 python-op+backend-tests(nvidia-cuda133) 全 pass |
| 2026-08-16 14:55 | _coalesced_ | CI_PASS | #5514 python-op pass (backend-tests skipping) |
| 2026-08-16 14:55 | _compute_linear_combination | CI_PASS | #5515 python-op pass (9m13s含autotune), backend-tests skipping |
| 2026-08-27 08:51 | _gather_sparse_backward | FAIL | 命令失败 (exit 128): git push origin HEAD:pr/_gather_sparse_backward |
| 2026-08-27 08:54 | _gather_sparse_backward | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/5803 |
| 2026-08-27 08:57 | _logcumsumexp | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/5805 |
| 2026-08-27 09:00 | _fused_sdp_choice | LOW_SPEEDUP | 平均 speedup 0.110 低于阈值 0.6，继续提交，仅作为性能提醒 |
| 2026-08-27 09:00 | _fused_sdp_choice | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/5806 |
| 2026-08-27 09:02 | _fused_sdp_choice | CLOSED | #5806 closed: 0.110x < 0.8 用户阈值（metadata-dispatch op，无重计算）|
| 2026-08-27 09:10 | _histogramdd_bin_edges | BLOCKED | check_operator._check_out_variant_coverage 与 check_overload_consistency 对前导下划线非冲突 +_out 变体算子矛盾：coverage 要求 @pytest.mark.underscore_<op>_out + op_name="_<op>_out"(kernel func 名派生)，overload consistency 要求 @pytest.mark.<op>_out + op_name="<op>_out"(yaml id stripped 派生)。已验证已合并的 _conj_copy(#5513)用 stripped 约定(conj_copy_out)通过 overload consistency 但 FAIL 当前 strict coverage check(要求 underscore_conj_copy_out)。三个 _histogramdd_* 均受此 bug 阻塞，待用户决策。|
| 2026-08-27 09:20 | _histogramdd_bin_edges | RESOLVED | 修复 check_operator.py _check_out_variant_coverage bug：out_variant 从 kernel func 名(保留前导下划线)改为 self.op_id+"_out"(非冲突 stripped/冲突保留)，与 check_overload_consistency 对齐。已验证 _conj_copy(已合并)修复后 coverage check 通过。补 BLOCK_SIZE/self.shapes 注释、.cpu()→.to("cpu")。strict check 0 error。|
| 2026-08-27 09:14 | _histogramdd_bin_edges | FAIL | benchmark 无数据（0 case），请检查 benchmark 文件 |
| 2026-08-27 09:23 | _histogramdd_bin_edges | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/5807 |
| 2026-08-27 09:33 | _histogramdd_from_bin_cts | FAIL | 本地测试失败: back] E       FuncTorchGradWrapper: registered at /pytorch/aten/src/ATen/functorch/TensorWra |
| 2026-08-27 09:40 | _histogramdd_from_bin_cts | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/5808 |
| 2026-08-27 09:50 | _histogramdd_from_bin_tensors | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/5809 |
| 2026-08-27 09:55 | _lu_with_info | SKIPPED | 重建 benchmark 源码(.pyc反编译)+修复3处strict failure(NaN假阳性"dominant"注释含nan→改文案;dtype注释须紧贴字面量上一行;LuWithInfoResult模块级全局Rule44→移入函数体)后:tests 30 pass,benchmark 10 case 跑通,算术平均 speedup=0.552(f32 0.466/f64 0.637)<0.8 用户阈值,不提交。修复benchmark:get_input_iter用模块常量LU_WITH_INFO_SHAPES而非self.shapes(否则set_shapes回退到core_shapes.yaml的Benchmark条目取到1-D [1073741824]);去掉不存在的flag_gems.set_gems()/gems_op=flag_gems._lu_with_info(私有aten未导出),依赖run()内use_gems()自动dispatch。|
| 2026-08-27 10:05 | _index_put_impl_ | SKIPPED | 已存在于 upstream/master: 实现在 src/flag_gems/ops/index_put.py(导出 _index_put_impl_),_FULL_CONFIG line158,yaml id:index_put_impl(aten _index_put_impl_),ops/__init__ 已注册,tests/test_index_put_impl.py 已存在。提交会造成重复/冲突,不提交。(此前 task#1 按 ops/_<op>.py 文件检查未发现,因该 op 寄生于 index_put.py)|
| 2026-08-27 10:05 | _log_softmax | SKIPPED | 已存在于 upstream/master: 实现在 src/flag_gems/ops/log_softmax.py,_FULL_CONFIG line173-174(_log_softmax + _log_softmax.out),yaml id:log_softmax/log_softmax_out(aten _log_softmax/_log_softmax.out),ops/__init__ 已导出 log_softmax/log_softmax_out/log_softmax_backward/log_softmax_backward_out,conflict mode(bare log_softmax.py 存在)但已是既有算子,提交会造成重复/冲突,不提交。|
| 2026-08-27 10:16 | _fused_adagrad_ | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/5811 |
| 2026-08-27 10:35 | _fused_adagrad_ | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/5811 |
| 2026-08-27 10:50 | _fused_sgd_ | SKIPPED | 6文件全部就绪(kernel+tests5tests+benchmark3tests,ops/__init__+__init__ _FULL_CONFIG+yaml fused_sgd/fused_sgd_ 双条目,strict check 0err0warn,overload consistency pass,272 tests pass),重跑 benchmark(GPU2 H20 kernel mode,与worktree原始benchmark同shapes/同_input_fn/同torch_op=aten._fused_sgd.default+torch._fused_sgd_)后算术平均 speedup=0.5612x(inplace fused_sgd_ 0.7913x + functional fused_sgd 0.3310x,30 case excl native-vs-native tensor_lr)<0.8用户阈值,不提交。根因:functional变体在小shape(64x64/256x256)的12次clone kernel launch开销被当前环境(triton3.6/cuda13)放大~17x(0.195ms vs 历史同代码0.0535ms),拖垮functional;inplace大shape(4096²/64x512x512)FlagGems 1.5x更快但小shape被use_gems dispatch开销(~0.05ms/call)拖到0.13x。历史同代码测得0.9937x(>0.8)系环境allocator/clone launch更快所致。注:tensor_lr变体FlagGems未注册该overload→native-vs-native~1.0不计入;按用户阈值不提交。|

## [2026-08-28] #5498 _conj_physical 冲突解决
- PR #5498 (pr/_conj_physical) 原与 master 冲突 (mergeable=CONFLICTING)。
- 在 worktree /root/FlagGems/.worktrees/gen-_conj_physical 上 rebase 到最新 upstream/master。
- 4 个 commit 顺序 replay：e1e788c1a(KernelGen add) + 3 个历史 "Update __init__.py/Update operators.yaml" CI 修复 commit。
- 冲突解决：operators.yaml 按 master 约定把 _conj_physical/_conj_physical_out 放在 c 段开头(conj 前)；tune_configs.yaml 保留 _adaptive_avg_pool3d_backward/_conj_copy/_conj_physical 三键字母序；__init__.py 与 ops/__init__.py 用 resolve_*脚本自动解排序冲突。
- strict check 0err0warn。force-push 后 gh 确认 mergeable=MERGEABLE。
- PR diff 仅 7 个 operator-scoped 文件（kernel/test/benchmark/operators.yaml/ops__init__/__init__/tune_configs.yaml），无 .worktree/ 污染，符合 Review Hygiene Rule 2。
- 注：mergeStateStatus=BLOCKED 是 CI/review 未满足，非冲突。

## [2026-08-28] #5498 _conj_physical 重建（修复 rebase 污染）
- 上次 rebase 到 master 后,PR diff 混入大量无关排序改动（__init__.py 几百行无关移动、ops/__init__.py 丢版权头、__all__ 顺序错乱）。根因：旧分支落后 master 288 提交，master 的 __init__.py 排序约定已变，rebase 自动解冲突脚本 resolve_*_conflicts.py 把两边不同位置的条目都保留合并导致污染。
- **改用 skill 正确流程重建**：删除污染分支 + worktree，基于最新 upstream/master(6ce64b3dc) 建全新分支，用 extract_from_worktree.py 重新提取。
- 提取后手工补齐 3 个 worktree 参考文件（ops/__init__.py、__init__.py、operators.yaml）预注册 _conj_physical 条目（按字典序：operators.yaml 放 ops: 最顶部因 _ < 小写字母；tune_configs 放 _conj_copy 后），使 extract 脚本能正确插入。
- 发现 kernel 用 @libtuner(configs=runtime.get_tuned_config("_conj_physical")) 需 tune_configs.yaml 提供 BLOCK_SIZE config，补加 6 条 config（BLOCK_SIZE 64-2048, num_warps=8）。
- tests 用 worktree 原版 3 个测试函数（test__conj_physical + _real + _out），extract 只提取了 1 个，手工还原为 3 个完整版本。
- strict check 0err0warn，pre-commit 过，30 tests PASS（真实 FlagGems kernel），benchmark 10 case 真实数据：_conj_physical 0.905x + _conj_physical_out 1.739x，均 >0.8。
- PR diff 7 个 operator-scoped 文件纯新增 248 行（无任何删除/无关改动），mergeable=MERGEABLE。
- PR body 用 gen_pr_description + format_pr_body 生成，含真实 benchmark 表格按 variant 分小节。

## [2026-08-28] 修复 6 个 PR Summary 无端换行
- PR #5803/#5805/#5807/#5808/#5809/#5811 的 Summary 段落中间有硬换行（来自 yaml description block scalar 的源码换行被原样带进 PR body）。
- 根因：submit_operator.py 的 format_pr_body 把 get_yaml_description 返回的 desc_text 直接拼进 Summary，未规整内部换行。
- 修复 1（脚本）：format_pr_body 增加把 desc_text 内部单换行合并为空格的逻辑，以后提交的 PR 不再出此问题。
- 修复 2（已提交 PR）：对 6 个 PR 读取 body、只规整 Summary 段落内的换行（保留段落双换行、Testing/Performance/Multi-backend/Files Changed 段及 benchmark 数据原样不动），用 gh pr edit --body-file 更新。
- 验证：6 个 PR 的 Summary 现在都是 1 个连续段落，文字内容不变。

## [2026-08-28] skill 脚本同步到远程 + claude/codex 副本
- 主仓 flaggems-pr-submit 的 3 个脚本修复 commit 到分支 fix/pr-body-summary-linebreak 并 push 到 origin：
  - submit_operator.py: format_pr_body 规整 yaml description 换行(PR Summary 不再有中间断行)
  - check_operator.py: _check_out_variant_coverage 用 self.op_id 派生 out_variant(对齐 naming.md)
  - gen_pr_description.py: BENCH_RE 支持 (list, kwargs) 形式的 shape_detail
- claude/codex 副本整体落后主仓多个已发布 commit, 整目录从主仓覆盖到两副本:
  - 修复副本 paths.py 的前导下划线冲突自引用死循环 bug(主仓已删 yaml 判据, 副本旧版有)
  - 补上 codex 缺失的 targets.py
  - 同步 extract_from_worktree.py/check_operator.py/name_plan.py/SKILL.md 等到主仓最新版
- data/pr状态记录.md 为运行日志, 三处各自保留未覆盖; auto_gen 运行产物未入库。
| 2026-09-24 06:02 | _linalg_solve_ex | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/6664 |

## [2026-09-24] #6664 _linalg_solve_ex 提交说明（无 worktree，按用户指示 copy 实现）
- 目标仓库 **mainline**（flagos-ai/FlagGems, base=master, fork=Yukun-Cui/FlagGems, 分支 pr/_linalg_solve_ex）。运行期把本地 `upstream` remote 临时指向 flagos-ai/FlagGems（`submit_operator.py` 内部只向 check_operator 透传 `--target`，upstream_ref 由 remote 名决定），**运行结束已恢复**为 FlagGems-Experimental。
- 无 auto_gen worktree（`.worktrees/` 为空），按用户「照着 copy 代码、别委托调用」的指示，手工构造 `.worktrees/gen-_linalg_solve_ex` 源：kernel 逐行复制 mainline `linalg_solve_ex.py`（仅改名 `_linalg_solve_ex_kernel`），wrapper 适配 `aten::_linalg_solve_ex` 的 4 输出 `(result, LU, pivots, info)`；`pivots` 为 schema parity 零填充（对齐已合并的 `_linalg_slogdet` 先例），LU 复用 kernel 的 workspace。
- **autotune 在本机 triton 3.6 下不可用**：把 BLOCK_N/BLOCK_K 当 constexpr launch kwargs 时，① 原版 `@triton.autotune`（base 算子在用的）报 `JITFunction.run() got multiple values for keyword argument 'BLOCK_K'` —— 实测 base 算子 `tests/test_linalg_solve_ex.py` 自己就 24 fail / 32 pass，benchmark 直接 fail；② 改成 `@libtuner(configs=runtime.get_tuned_config(...))` 则崩在 SQLAlchemy 调优缓存 `put_config → ConfigCls(**key_dict, **config)`（`'BLOCK_K' is an invalid keyword argument`，dict 与 triton.Config 混用）。最终**去掉 autotune**、launch 固定 `num_warps=1`（实测 {1,2,4,8} 逐 shape 对比最快/并列最快），diff 收敛为 6 个 operator-scoped 文件，strict 0 error 0 warning。
- 性能：kernel 模式 mean 0.773（PR body 记录，> 0.6 阈值）；cudagraph 模式 mean ≈ 2.15（与 base 算子 PR #5322 报的 2.33 同档），说明低值来自 benchmark 的 dispatch 开销而非 kernel。
- **extract_from_worktree 的已知坑**：worktree 里若放上游 `conf/operators.yaml` 全量副本，`insert_operators_yaml` 的 sibling 扫描会崩（`AttributeError: 'list' object has no attribute 'startswith'`）——上游 `rnn_tanh` / `rnn_tanh_data` 两条的 `name:` 值是 list。绕过方式：worktree 只放本算子的最小 yaml。另外该函数写出的条目是 2 空格缩进的 `  - id:`，与仓库 0 缩进风格不符；本 PR 的 yaml 条目按仓库风格手写后再让脚本跳过插入。
- PR body 里的 `stage: alpha 5.4` 与 `to_reference(inp, True)` 是 `submit_operator.py` 的固定模板文案（实际 yaml 是 `alpha: '5.5'`，测试用 `utils.to_reference(A)`），已合并的 #5924 同样如此，非本次引入。

## [2026-09-24] #6664 _linalg_solve_ex 计划变更：改为委托实现（用户指示「实现代码改成调用」）
- 用户决定把实现从「复制 kernel + 固定 num_warps=1」改为「调用已合并的 `linalg_solve_ex`」，LU/pivots 用零填充做 schema parity（用户选定）；测试保留 fp64；因 PR 已存在（无法用 submit_operator.py 建第二个 PR），按用户指示手工 commit + force-push 更新 #6664，PR body 用 `format_pr_body` 生成后只改 3 处事实性文案。
- 新实现 `src/flag_gems/ops/_linalg_solve_ex.py`（68 行）：`result, info = linalg_solve_ex(A, B, left=left, check_errors=check_errors)`，补 dtype assert（strict checker 要求 wrapper 有 dtype 验证）、`pivots = torch.zeros(*batch, n, int32)`、`LU = torch.zeros_like(A)`；docstring 说明 LU/pivots 是 schema parity 且 `torch.linalg.solve_ex` 会丢弃它们。yaml description 相应改写；测试 `_assert_solve_ex_outputs` docstring 更新（LU/pivots 只比 shape）。
- **本机跑不起来的真因（重要）**：本机 triton 3.6 是 FlagTree 构建，含 `knobs.autotuning.adjust_block_size`（env `FLAGTREE_AABS`，默认 True）。AABS 的 `auto_adjust_block_sizes` 会把 BLOCK 尺寸写进 `triton.Config.kwargs`，于是上游 `linalg_solve_ex` 既传 `BLOCK_N=/BLOCK_K=` 又靠 autotune，`self.fn.run(**kwargs, **config.all_kwargs())` 撞成 `TypeError: got multiple values for keyword argument 'BLOCK_K'`（autotuner.py:277）。触发与 shape 相关（n=8 时 nrhs∈{1,2,3,5} 挂，{4,8} 正常），与 dtype 无关——之前"fp64 才挂"的判断是错的。上游自己的 `tests/test_linalg_solve_ex.py` 在本机同样 24 fail / 32 pass，其 benchmark 直接 fail。
- **解法（仅本地测量用，未进 PR）**：`FLAGTREE_AABS=0`。加上后委托版 56 tests 全过、benchmark 11 case 跑通。CI 不受影响（#5322 base 算子当年 CI 绿，#6664 首轮 kernel 版 python-op 也绿，说明 CI 的 triton 没有这个 AABS 行为）。
- **性能（同机 H20，都带 FLAGTREE_AABS=0）**：kernel 模式 mean 0.542（Gems 几乎恒定 0.068ms）；cudagraph 模式 mean 1.936（逐个 3.97×~1.07×）。对比：kernel 版（自建 kernel + num_warps=1）kernel 模式 0.773 / cudagraph 2.15。委托版慢的部分是**私有 op 在 use_gems 下的 dispatch 开销**：同一组预置输入，`torch.linalg.solve_ex`（公有）16.2µs vs `torch._linalg_solve_ex`（私有）69.2µs，外加两次 parity 分配的 ~8.5µs（直调 `flag_gems._linalg_solve_ex` 23.8µs vs `flag_gems.linalg_solve_ex` 15.3µs）。kernel 本身未变。
- PR body 口径：用户选定用 cudagraph 表（与 #5322 同口径），并在正文注明 kernel 模式 0.542 及其原因。
- 验证：strict 0 error 0 warn（含 worktree 一致性、anti-hack L1/L2）、pre-commit 全过、56 tests pass（AABS=0）、与 `flagos/master`(acc1cbf9a) 无冲突。PR diff 仍为 6 个 operator-scoped 文件（kernel 292→68 行）。
- 教训：`check_operator.py --strict --target mainline` 的 upstream 冲突检查用的是本地 remote 名 `upstream` 的 ref，而本机 `upstream` 指向 Experimental → 本次一度是在拿 Experimental 的 master(274f30ac4) 做校验。要投 mainline 时必须核对 `git rev-parse upstream/master` 或显式加 `--upstream-remote flagos --base master`。

## [2026-10-08] #6664 _linalg_solve_ex 第三轮：review comment 修复（委托版 → 融合 kernel 版）
- reviewer `Caeruleann` 提了 5 条 inline comment，全部成立，已逐条 inline 回复（reply id 4216826482 / 4216830646 / 4216834575 / 4216839556 / 4216843489），head 推到 `914701f77`。
- **核心 bug：零填充 LU/pivots 会让 backward 静默算出 NaN。** 之前判断「`torch.linalg.solve_ex` 丢弃 LU/pivots，所以没人读」是错的——autograd 的 `LinalgSolveExBackward0` 把 LU/pivots 存为 saved tensor 并在 backward 里 replay（`_saved_A/_saved_LU/_saved_pivots/_saved_result/_saved_left`）。实测 use_gems + fp64 4x4：forward 正确，gradA/gradB 全 NaN、non-finite。这是「正确的前向掩盖错误的反向」最坏形态，务必不要再用 parity 占位。
- **最终实现**：自带融合 kernel（585 行），一个 launch 出全部 4 个输出。pivot search 原本就在循环里，现在额外写 `ipiv`（1-based LAPACK），LU workspace 直接返回。`LEFT` 做 `tl.constexpr` → 两种方程各自特化，内层循环无分支。`left=False` 解 `Uᵀ(Lᵀ Xᵀ)=Bᵀ`，最后把 pivot swap 倒序 replay 来撤销置换。
- **性能教训（重要）**：先尝试「组合 in-tree 算子」（`linalg_lu_factor_ex` + 2×`linalg_solve_triangular` + `_pivots_to_perm_gpu` + gather），语义 104/104 全对，但 kernel 模式直接退化到 **0.20ms vs ATen 0.042ms**（5 次 launch；单步耗时 lu_factor_ex 0.034 + perm 0.025 + trsm 0.028 + gather 0.006）。改回单融合 kernel 后 0.016ms。结论：这类小矩阵 linalg 私有算子**不能靠拼 in-tree 算子**，launch 开销就吃掉全部收益。
- **complex 走 vendor kernel 的正确姿势**：不能直接调 `aten::_linalg_solve_ex`——它内部会 re-dispatch `linalg_lu_factor_ex`，而 use_gems 已把它换成 Triton 版，于是绕回去撞 `KeyError: 'complex64'`。必须在 **import 时**（use_gems 之前）用 `torch.library.get_kernel` 抓 `linalg_lu_factor_ex`/`linalg_solve_triangular`/`gather`/`scatter.src` 四个 handle，自己拼 factor-then-substitute（照 `linalg_matrix_sqrth` 的做法）。注意 `call_boxed` 必须用 kwargs 传 schema 里带 `*` 的参数（`pivot=`/`upper=`/`left=`），位置传参会报 "takes N positional arguments"。
- **ATen 契约实测结论**（写测试前先探明，省大量返工）：
  - LU/pivots/info **恒等于 `torch.linalg.lu_factor_ex(A)`**，与 `left` 无关（不是 Aᵀ 的分解）；非连续/列主序输入也成立。实测 0 mismatch / 48 组。
  - LU/pivots/info 带的是 **A 自己的 batch shape**，不是广播后的 result shape：`A(2,1,4,4)` + `B(1,3,4,2)` → result(2,3,4,2) 但 LU(2,1,4,4) / pivots(2,1,4) / info(2,1)。
  - vector RHS 规则 = ATen `linalg_solve_is_vector_rhs`：B 是 1-D，或 `B.ndim==A.ndim-1 且 B.shape==A.shape[:-1]`。`A(2,4,4)`+`B(2,4)` 是 batch of vectors（result (2,4)），`B(4,2)` 则是单矩阵广播（result (2,4,2)）。`left=False` **不支持** vector RHS（ATen 直接报 incompatible shapes）。
  - 空输入：`A.numel()==0` 时 LU 保持 A 形状、pivots 沿 n 轴为空、info 全 0；但 **B 零列（如 B(6,0)）时 ATen 仍然会分解 A**，不能当「没事可做」早退——第一版这么写导致 LU/piv 全错。
- **测试**：111 tests（原 56），LU/pivots 不再只比 shape，`_assert_solve_ex_outputs` 对 result/LU 用 `gems_assert_close`、对 pivots/info 用 `gems_assert_equal` 精确比。新增 row pivoting / singular×check_errors / left=False / vector RHS / broadcast batches / complex / non-contiguous / dtype mismatch / aux-outputs-usable。
- **梯度 parity 测不了的原因（已在 PR 里说明）**：backward 公式只在 op 被 **dispatch** 时才触发，需要 `use_gems()`，而 `check_kernelgen_tests.py` 禁止测试新增行调用 `use_gems()`；直调 `flag_gems._linalg_solve_ex` 拿不到梯度（Triton kernel 不可微，grad 为 None）。折中：测 `lu_solve` replay（backward 实际消耗路径）+ ipiv 合法性，端到端梯度在测试外手工验证（fp64 gradA 8.8e-09 / gradB 2.3e-08）。
- **`P@L@U` 重建不要用作 fp32 断言**：误差累积超过仓库 rtol（1e-6 级），实测 29.7% 元素超标。直接比 LU/pivots 即可。
- **anti-hack Layer 1 对 `torch.ops.aten` 一律报错**，但 in-tree 已合并的 `linalg_matrix_sqrth` / `cumprod` / `slice_copy` / `mul` / `to` 五个文件同样触发（逐个实测 hack=True）。这是本地粗粒度 gate，不是仓库 CI gate；仓库自己的 4 个 ci_checks 全绿、pre-commit 全过。
- **GPU 环境坑**：本机 8 卡共享且常被别的任务压满（实测 3 卡 100%），benchmark 跑分波动可达几倍，单次 kernel 模式出现过 4 个 case 恒定 ~0.445ms 的假离群（换次运行就漂到别的 shape）。判断性能必须直接计时 + 多次复跑，别只看一次 benchmark 表。另外 NVML 会间歇性 `Failed to initialize NVML: Unknown Error` 导致 `torch.cuda.device_count()==0`，等几分钟自己恢复。
- **git push 卡死**：旧的 `git fetch`/`git push` 僵尸进程会占住 repo，新 push 一直挂。`ps -C git` 找出来 kill -9 再推；本机到 github 延迟很高（简单 GET 9s），push 要放后台等。

## [2026-10-08] #6664 第四轮：按 reviewer 要求把测试/benchmark 并入公有算子文件
- reviewer 的 "redundant underscore, you can move these cases to test_linalg_solve_ex.py" 按要求执行：删除 `tests/test__linalg_solve_ex.py` 和 `benchmark/test__linalg_solve_ex.py`，case 并入 `tests/test_linalg_solve_ex.py`（167 tests = 56 公有 + 111 私有）和 `benchmark/test_linalg_solve_ex.py`（复用同一个 `LinalgSolveExBenchmark` 类和 `SOLVE_EX_SHAPES`，两个 `op_name` 各跑一次）。
- **并入后的额外收益**：两个算子同输入同 shape 直接可比。cudagraph 口径同一次运行：公有 2.255 / 私有 2.565；kernel 口径 2.182 / 2.157。私有版多返回 LU+pivots 却不更慢，正好证明融合 kernel 里产出辅助输出是零成本的。
- **用户明确指示「不要动 conf/ci_test_aliases.yaml，ci 失败就让他失败」**：我原本加了一行 `_linalg_solve_ex: test_linalg_solve_ex` 让 `check_operator_markers` 能解析到合并后的文件，已按指示撤回（`git checkout flagos/master -- conf/ci_test_aliases.yaml`）。
- **已知且被接受的红灯**：`check-operator-markers` exit=1（`find_test_file()` 按 `tests/test_<id>.py` 解析，找不到 `tests/test__linalg_solve_ex.py`），该 job 在 `rule-check-required` 的 needs 里 → 门禁会红。其余 4 个 required check（check_operators_yaml / check_init_exports / check_kernelgen_tests / check_aten_operators）全绿，167 tests 两种模式全过，`-m underscore_linalg_solve_ex` 仍能选出全部 111 个。已在 PR body 和 inline 回复里写明这是预期失败及原因。
- `check_performance_reference` 同理会 warning（找 `benchmark/test__linalg_solve_ex.py`），但它 exit=0 且不在 required 门禁里。
- 顺带 rebase 到新 master（`acc1cbf9a..4e96fbfec`），唯一冲突是 `conf/ci_test_aliases.yaml`（上游在同一处加了 lshift/tensor_split 几条），撤回该文件后冲突一并消失。
- **网络坑**：本机到 github 极不稳定，`git push` 多次挂死或 `Failed to connect to github.com port 443 after 131152 ms`。可靠做法是后台跑 `for i in $(seq 1 40); do git push ... && break; sleep 20; done`，别单次等。
| 2026-10-13 07:51 | values_copy | FAIL | 命令失败 (exit 1): python /root/baai-internship/skills/flaggems-pr-submit/scripts/check_operator.py valu |
| 2026-10-13 08:45 | values_copy | FAIL | 命令超时 (60s): git fetch upstream master |
| 2026-10-13 08:51 | values_copy | FAIL | 命令失败 (exit 1): gh api repos/flagos-ai/FlagGems/pulls -f title=[KernelGen][Nvidia] Add values_copy op |
| 2026-10-13 08:54 | values_copy | FAIL | 命令超时 (60s): git fetch upstream master |
| 2026-10-13 08:58 | values_copy | FAIL | 命令失败 (exit 128): git fetch upstream master |
| 2026-10-13 09:09 | values_copy | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/7083 |
| 2026-10-13 09:16 | coalesce | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/7086 |
| 2026-10-13 09:25 | _neg_view_copy | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/7088 |
| 2026-10-13 09:31 | col_indices_copy | FAIL | 本地测试失败: dance.  (Triggered internally at /pytorch/aten/src/ATen/Context.cpp:760.)     inp = torch.sp |
| 2026-10-13 09:36 | col_indices_copy | FAIL | 命令超时 (60s): git push fork HEAD:pr/col_indices_copy |
| 2026-10-13 10:09 | col_indices_copy | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/7094 |
| 2026-10-13 10:15 | _coalesce | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/7096 |
| 2026-10-19 14:33 | _indices | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/7293 |
| 2026-10-19 14:34 | ccol_indices | FAIL | 命令失败 (exit 1): python /root/baai-internship/skills/flaggems-pr-submit/scripts/check_operator.py ccol |
| 2026-10-19 15:07 | ccol_indices | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/7295 |
| 2026-10-19 15:10 | _convert_indices_from_coo_to_csr | FAIL | 命令超时 (60s): git fetch upstream master |
| 2026-10-19 15:13 | _convert_indices_from_csr_to_coo | FAIL | 命令超时 (60s): git fetch upstream master |
| 2026-10-19 15:18 | _convert_indices_from_csr_to_coo | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/7296 |
| 2026-10-19 15:20 | _convert_indices_from_coo_to_csr | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/7297 |

## [2026-10-19] #7293/#7295/#7296/#7297 第四批：convert_indices/ccol_indices/_indices 提交
- 4 个 PR 全部投递 mainline（flagos-ai/FlagGems:master）：7293 _indices、7295 ccol_indices、7296 _convert_indices_from_csr_to_coo、7297 _convert_indices_from_coo_to_csr。每个 PR 6 文件、单算子、check_operator --strict 0E0W。
- **网络根因定位**：github.com:443 间歇性 GnuTLS recv error(-110)/连接挂起，api.github.com 始终可用。解决：全局 git http.version=HTTP/1.1 后 git fetch/push 稳定；完全不可达窗口用 REST API 构建同 tree commit 强制更新远端分支（/tmp/api_push.py，脚本按 base=upstream/master tree + 6 文件 blob 重建）。
- **submit_operator.py 两处最小容错**（备份 /tmp/submit_operator.py.bak）：(1) push 前若 fork 分支远端 tree 与本地 HEAD tree 一致则跳过 git push（API 回退推送后内容已等价）；(2) push 前 fetch 失败降级 warning 不中断。
- **CI python-op 首轮失败根因（3 个下划线算子）**：`tools/ci_checks/derive_changed_operators.py` 的 #6359 约定对带前导下划线算子派生 marker 时，若去下划线名与该算子自身注册 id 冲突则加 `underscore_` 前缀（如 _indices → underscore_indices）；而我的测试只声明了去下划线 mark，`pytest -m underscore_...` 选到 0 用例 → exit 4。修复：测试文件加模块级 `pytestmark = [pytest.mark.<bare>, pytest.mark.underscore_<bare>]`（对齐已合并的 `_indices_copy` 先例），远端分支已更新。
- **7296 code-style 失败是 runner 侧 robust-checkout 网络问题**（"all links failed after 30 rounds"），非代码问题；重跑需 admin 权限，只能等新 push 触发全量 CI。
- **.pr_gate/ 误入 _indices 等 3 个 worktree 的 commit**（submit dry-run 的 gate marker）：已从 index 移除并 amend；远端 tree 与本地核对一致。
- ccol_indices 无需双 mark：裸 id 即派生 marker（ccol_indices 不带前导下划线）。
| 2026-10-20 07:00 | indices | PR_CREATED | https://github.com/flagos-ai/FlagGems/pull/7325 |

## [2026-10-21] #7222~7226/#7293/#7296/#7297/#7325 reviewer 修复轮
- reviewer Caeruleann 提了 15 条 inline + 2 条 PR-level 意见。全部修复并逐条 inline 回复。
- **核心教训 1（yaml id 与文件 stem 必须一致）**：CI derive marker 先按 ops 文件 stem 精确匹配 yaml id；不匹配时 fallback raw stem → expected_marker 剥下划线，若 stripped 名（本 PR 自己加的裸 id）在 all_op_ids 里就加 `underscore_` 前缀 → 与测试声明的裸 mark 不一致 → `pytest -m` 选 0 用例 → python-op 失败。解法：yaml id 用 ATen 注册名（=文件 stem），测试声明裸 mark（derive 剥下划线后的形式）。
- **关键教训 2（check_operator_markers 只认函数级 decorator）**：模块级 `pytestmark` 列表不算数，共享 test 文件里必须有至少一个函数带 `@pytest.mark.<derive_marker>`。7223/7293 删 bare helper 时踩坑，已恢复 helper（注释说明 bare coverage 属于对应 bare PR）。
- **yaml 老 base 问题**：7223/7225/7226/7296/7297 的 yaml 基于早期 fork，含大量后来 master 已有/已变的条目 → sort-exports 全文件排序失败 + 与 master 冲突。解法：全部以当前 upstream/master yaml 为底 + 仅插入本 PR 条目（casefold 排序正确位置：_convert_* 在 _ctc_loss 前；_fw_primal_copy 在 _linalg_eigh 前；_make_dual_copy 在 _philox_uniform_ 前；_indices_copy 在 _linalg_eigh 前；_indices 在 _linalg_eigh 前）。
- **make_dual .out 的 inference 约束**：native `aten::_make_dual_copy.out` 要求 out 是 inference tensor（与 _fw_primal_copy 不同），benchmark baseline 需在 InferenceMode 内重建传入的 out（含注释说明）。
- **7293 冲突对命名落地**：yaml id=_indices/for=_indices、测试函数 test__indices*、pytestmark 双 mark（indices+underscore_indices）+ bare helper（flag_gems.indices 在 #7325 merge 前不存在，helper 内部走 flag_gems._indices 并注释说明）。#7325 merge 后 CI derive 变为 underscore_indices，双 mark 两态均覆盖。
- 教训：`.pr_gate/` 会反复混入 amend（pre-commit dry-run 重新生成），每次 push 前必须 `git rm -r --cached .pr_gate`。

## [2026-10-21] #7295 ccol_indices 合并
- maintainer Dongxu-H 于 2026-10-21 02:22 UTC 将 #7295 合入 master（merge commit c1abc6927）。四项 CI 全绿、reviewer 无遗留意见。
- 其余 9 个 PR（7222/7223/7224/7225/7226/7293/7296/7297/7325）CI 全绿，MERGEABLE/BLOCKED（等 reviewer approve）。review 修复后的最新 head 均已推送并通过全部检查。

## [2026-10-21] #7223 yaml 无关改动修复（第二轮）
- **根因**：#7222（bare indices_copy）已先合并进 master，而 #7223 分支是基于老 base 的注册文件版本 —— API 重放时把 master 上 bare indices_copy 的注册行/测试/benchmark case 全部"覆盖删除"了。GitHub files-changed 显示 +2 -2 / +3 -3 / 大量 - 行，reviewer 视角就是"一堆无关改动"。
- **修复（coexistence 原则）**：注册文件、test、benchmark 全部以"最新 master 内容为底 + 仅追加 _indices_copy 相关行"重建：
  - 顶层 __init__.py：保留 bare 两行，+2 行 _indices_copy 注册
  - ops/__init__.py：保留 bare import，+1 import +2 __all__
  - tests/test_indices_copy.py：bare 三个测试 + 追加 underscore 三个测试（bare-marker helper 因 #7222 已 merge 而删除）
  - benchmark/test_indices_copy.py：bare 两个 benchmark + 追加 underscore 两个（类重命名为 UnderscoreIndicesCopy* 避免撞名）
  - conf/operators.yaml：master + 仅 26 行 _indices_copy 条目（casefold 位置在 _linalg_eigh 前）
- 最终 diff：6 文件 205 行纯新增、0 删除行。MERGEABLE。
- **教训**：冲突对（bare/underscore）PR 的注册与测试必须是"master 现状 + 追加"，任何 API 重放都不能基于老 head tree 直接覆盖共享文件——共享文件（test/bench/init/yaml）一律以"当前 master 版本为底 + 追加本 PR 内容"的方式重建。

## [2026-10-21] #7224/#7225/#7226/#7296/#7297/#7325 yaml 无关改动批量修复 + #7222 合并
- **根本原因统一**：这些 PR 的分支仍基于是几天前的 master，而 upstream/master 持续前进（新增 fp8_paged_mqa_logits、fused_inv_rope_fp8_quant 等 yaml 条目）。GitHub files-changed 按 merge-base 计算，于是把"分支上缺少的 master 新条目"显示成 PR 的删除行（7225: 686 行 diff，7226/7296/7297: 各 36 删除行，7325 甚至变 CONFLICTING）。
- **统一修复手法**：全部以「当前 upstream/master 内容为底 + 仅追加本 PR 的条目/注册行/文件」重建 commit（parent = 最新 master tip），共享文件（operators.yaml、两个 __init__.py）只做追加，绝不覆盖。test/benchmark 若 master 已有同名文件（如 indices_copy 系列）则"保留 master 内容 + 追加 underscore 版本"，类名加 Underscore 前缀避免撞名。
- **最终全员状态**：7223/7224/7225/7226/7293/7296/7297/7325 全部 0 删除行、OPEN/MERGEABLE，yaml 各 +12~+28 -0。
- **#7222 (bare indices_copy) 与 #7295 (ccol_indices) 已合并**进 master。
- **操作注意**：master 用 gh api 拉取当前内容（`repos/flagos-ai/FlagGems/contents/<path>` + `git/blobs/<sha>`），因为本地浅克隆常有 staleness；每次重建前都要重新拉一次，避免 base 又落后。

## [2026-10-21] 第三轮：isort/sorter 位置修正（7224/7225/7226/7296/7297/7325）
- 第一轮重建后 CI 报 isort + sort-exports 失败：手工插入的行位置不符合仓库工具链的排序键。
- **修正**：
  - `_FULL_CONFIG` / `__all__` 必须按 `str.casefold()` 排序（sorter 用这个键）。例如 `_fw_primal_copy` 在 `_fused_sgd_` 之后（不是 `_fused_dropout` 之后）；`_make_dual_copy` 在 `_make_dep_token` 之后。
  - ops/__init__.py 的 import 必须满足 isort 5.12 `--profile black -o packaging`（CI 固定该版本）。用 `pip install isort==5.12.0 --target` 后本地跑相同的命令验证。
  - 顶层 __init__.py 的 `from packaging import version` 必须留在 `import torch` 之后（isort 在没有正确 first-party 配置的临时目录会误排，需手工复原）。
- 最终 6 个 PR 全部：0 删除行、MERGEABLE、yaml 各 +12~+28 -0。
- **方法沉淀**：共享文件重建流程 = 从 GitHub API 拉最新 master 原文 → 只用脚本追加本 PR 的行 → 用 isort 5.12 + black + sort_exports.py 三重本地校验 → API 建 commit（parent=master tip）。

## [2026-10-21] #7325 合并后 #7293 改为追加写入
- #7325（裸名 `indices`）于 2026-10-21 08:34 合入 master，因此 #7293（`_indices`）现在满足「前导下划线冲突对」例外条件：yaml id `_indices`、mark `underscore_indices`、与裸名版共用 test/benchmark 文件。
- 改造方式：以 master 的三个共享文件为底，**只追加** `_indices` 内容——
  - operators.yaml：+12 行（`_indices` 条目，casefold 插在 `_index_put_impl_` 之后、`_int_mm` 之前）
  - src/flag_gems/__init__.py：+1 行（`_FULL_CONFIG`，插在 `_index_put_impl_` 与多行 `_int_mm` 条目之间）
  - src/flag_gems/ops/__init__.py：+2 行（import + `__all__`）
  - tests/test_indices.py：+104 行（保留 #7325 的 7 个 bare 测试，追加 7 个 `test__indices*`）
  - benchmark/test_indices.py：+26 行（保留 bare benchmark，追加 `UnderscoreIndicesBenchmark` 避免类名冲突）
- **踩坑**：master 的共享 `_make_coo` 末尾带 `.coalesce()`（为公开 `indices` 服务），直接复用会让 `_indices` 的「uncoalesced 输入」用例失效（`assert not is_coalesced()` 失败）。改为在该用例内直接构造未 coalesce 的原始 COO 张量。
- 验证：`pytest tests/test_indices.py` 24 passed；`--ref=cpu --quick` 24 passed；benchmark 2 passed；`use_gems()` 下 `GEMS INDICES` 与 `GEMS _INDICES` 分别触发、均返回别名视图；`sort_exports.py --check`、`check_init_exports.py`、isort 5.12、black 全部通过。
- 已回复 reviewer 那条「master 没有 indices 条目」的评论：说明评论时点确实不成立，但 #7325 合并后条件成立，现按冲突对追加实现。

## [2026-10-21] 第四轮：#7225 命名规范 comment（yaml id 裸名化）
- reviewer Caeruleann 指出：yaml id `_fw_primal_copy` 但 benchmark op_name 是裸名 `fw_primal_copy`，两者对不上；且 master 没有 bare `fw_primal_copy`，不满足冲突对例外。建议参考 `values` (for: `_values`)、`neg_view_copy` (for: `_neg_view_copy`) 的写法。
- **修正**：7225/7226/7296/7297 四个 PR 的 yaml id 全部改为裸名（`fw_primal_copy`、`make_dual_copy`、`convert_indices_from_csr_to_coo`、`convert_indices_from_coo_to_csr`），`for` 保留 ATen 名（带下划线）。benchmark op_name / test mark / 文件名本来就是裸名，现在全部对齐。
- **注意区分两种情况**：
  1. 无裸名孪生算子（如 _fw_primal_copy）：naming.md 默认规则 → yaml id 去下划线，_FULL_CONFIG/_indices.py 等实现侧保留 ATen 名。
  2. 真冲突对（如 _indices vs indices=#7325 已合并、_indices_copy vs indices_copy=#7222 已合并）：id 保留前导下划线，mark 用 underscore_ 前缀。
- casefold 排序时裸名与下划线名混排（'_'(95) < 字母，但 fw... 无下划线所以排裸名区），插入点用 `sorted(ids+[new], key=str.casefold)` 的后继元素作为 anchor。
- **教训**：/tmp 临时目录缺少仓库的 first-party 配置，直接跑 isort 会把 `from packaging import version` 误排到文件尾 → 恢复 master 原文 + 只插入目标行，不要整文件跑 isort。
- 四个 PR 最终：0 删除行、MERGEABLE、yaml +25~+28 -0。

## [2026-10-21] 方案 A 执行：kernel 文件裸名化（7225/7226/7296/7297）
- 用户选定方案 A：kernel 实现文件从 `_fw_primal_copy.py` 改名为 `fw_primal_copy.py`（裸名，跟随 values.py 先例）。
- **闭环逻辑**：文件 stem 裸名 → derive 的 stem 精确匹配 yaml 裸名 id → derive 输出裸名 marker（不再加 underscore 前缀）→ 与测试裸 mark 一致 → python-op 的 `pytest -m` 能选中。yaml id/for/op_name/mark/文件名五者全对齐。
- **不变的部分**：wrapper 函数名/ATen 注册名（`("_fw_primal_copy", _fw_primal_copy)`）保持 ATen 名，仅文件名与 import 路径变。
- **工具链坑位（本轮全踩过）**：
  1. sorter 重写 _FULL_CONFIG 会丢 master 注释（_pin_memory/_aten::dim/nested_to_padded_tensor/pin_memory 4 处）→ 重写后必须从 master 原文恢复注释行。
  2. isort 在 /tmp 临时目录会把 `from packaging import version` 误排 → 用 isort --fix 应用（它会正确保留在 import torch 后），但每次 fix 后要检查 4 处注释 + packaging 是否还在。
  3. 正确顺序：先改 kernel 文件名 → isort --fix → sorter --fix → 检查注释丢失 → 手工恢复 → 再跑三重 check-mode 直到 0 错误。
- 最终 4 个 PR：derive/isort/sorter/black 四项本地校验 0 错误后推送。

## [2026-10-21] 方案 A 补丁：nested_to_padded_tensor 无关改动消除
- 用户发现 4 个 PR 的顶层 __init__.py diff 里出现 nested_to_padded_tensor 条目的"移动"（+2 -2 变成上下文错位）。
- 根因：sorter --fix 重写 _FULL_CONFIG 时丢了注释，我恢复注释时把注释块插到了 `("nested_to_padded_tensor",` 条目的 `(` 行之前，而不是它原本的位置（条目内部首行之前），造成条目与注释的相对位置错乱。
- 修复：顶层 __init__.py 一律以「master 原文 + 仅在 casefold 正确位置插入本 PR 条目」重建，绝不跑 sorter --fix（它的全量重写会丢注释）；恢复注释用"从 master 原文提取、按原相对位置插回"。
- 修复后：4 个 PR 顶层 init 均 +2/-0（_indices 是 +1），0 删除行，isort/sorter/init_exports/black 四项 0 错误。
- **教训**：凡是 sorter --fix 改过的文件，注释一定丢；正确做法是"master 原文 + 脚本插入"，sorter 只用于 --check 验证，绝不用于 --fix 生成最终内容。
