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
