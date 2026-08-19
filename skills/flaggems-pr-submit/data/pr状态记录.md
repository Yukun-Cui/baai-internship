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
