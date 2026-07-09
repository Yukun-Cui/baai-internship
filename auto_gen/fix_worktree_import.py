#!/usr/bin/env python3
"""
fix_worktree_import.py — 修复 worktree 中 flag_gems 的导入路径问题。

问题：flag_gems 以 editable 模式全局安装于 /root/FlagGems/src/ 下，
通过 _flag_gems_editable import hook 拦截导入。即使 sys.path 优先指向
worktree 的 src/，Python 仍会加载全局版本，导致 worktree 中新建的沐曦
特化算子（_metax/ops/*.py）不可见。

本脚本在 import flag_gems 之前：
1. 移除 _flag_gems_editable 的 import hook
2. 将 worktree 的 src/ 插入 sys.path 最前端
3. 清除 sys.modules 中的 flag_gems 缓存

用法（两种方式）：

方式 1：作为 Python 入口脚本（推荐，最可靠）
  python3 /root/baai-internship/auto_gen/fix_worktree_import.py -c "import flag_gems; print(flag_gems.__file__)"
  python3 /root/baai-internship/auto_gen/fix_worktree_import.py --pytest tests/test_binary_pointwise_ops.py -m div -vs

方式 2：通过 exec + 分隔符嵌入（不引入路径污染）
  python3 -c "
import sys; sys.path.insert(0, '/root/baai-internship/auto_gen')
exec(open('/root/baai-internship/auto_gen/fix_worktree_import.py').read().split('SPLIT_HERE')[0])
# fix_imports() 已被 exec 调用
import flag_gems
print(flag_gems.__file__)
  "

方式 3：通过 PYTHONSTARTUP 环境变量
  PYTHONSTARTUP=/root/baai-internship/auto_gen/fix_worktree_import.py python3 -c "import flag_gems; print(flag_gems.__file__)"
"""
import os
import sys

# SPLIT_HERE — exec split anchor (do not remove)

_workdir = os.environ.get("FIX_WORKTREE_DIR")
if not _workdir:
    # Detect worktree root from CWD: find directory containing src/flag_gems/
    cwd = os.getcwd()
    while cwd and cwd != "/":
        if os.path.isdir(os.path.join(cwd, "src", "flag_gems")):
            _workdir = cwd
            break
        cwd = os.path.dirname(cwd)
    if not _workdir:
        _workdir = os.getcwd()

_workdir = os.path.abspath(_workdir)
_src_path = os.path.join(_workdir, "src")

# 1. Remove ALL /root/FlagGems paths from sys.path (from global editable install)
sys.path = [p for p in sys.path if "/root/FlagGems" not in p]

# 2. Remove the editable install hook
sys.meta_path = [
    h for h in sys.meta_path
    if '_flag_gems_editable' not in getattr(type(h), '__module__', '')
]

# 3. Insert worktree src into sys.path (highest priority)
if _src_path in sys.path:
    sys.path.remove(_src_path)
sys.path.insert(0, _src_path)
if _workdir in sys.path:
    sys.path.remove(_workdir)
sys.path.insert(0, _workdir)

# 3. Clear any cached flag_gems modules
for key in list(sys.modules.keys()):
    if 'flag_gems' in key:
        del sys.modules[key]

# 3.5 Pre-import ixformer BEFORE flag_gems to avoid registration conflicts.
# This is only required for Iluvatar (天数) attention ops that depend on ixformer;
# on other backends ixformer is absent, so the import is best-effort and skipped
# when unavailable. Override the dist-packages location with IXFORMER_PATH if needed.
_ixformer_path = os.environ.get(
    "IXFORMER_PATH", "/usr/local/corex-4.4.0/lib64/python3/dist-packages/"
)
if os.path.isdir(_ixformer_path) and _ixformer_path not in sys.path:
    sys.path.insert(0, _ixformer_path)

# Suppress warnings and import ixformer (best-effort; non-Iluvatar backends skip it)
import warnings

try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import ixformer  # noqa: F401
except ImportError:
    pass

# 4. Set environment variable so pytest can also detect
os.environ["FLAG_GEMS_WORKTREE"] = _workdir

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fix flag_gems import path for worktrees")
    parser.add_argument("-c", "--command", help="Python code to run after fixing imports")
    parser.add_argument("--pytest", nargs=argparse.REMAINDER,
                        help="Run pytest with given arguments after fixing imports")
    args = parser.parse_args()

    if args.command:
        exec(args.command)
    elif args.pytest:
        import pytest
        sys.exit(pytest.main(args.pytest))
    else:
        # Interactive mode
        import code
        code.interact(local={})
