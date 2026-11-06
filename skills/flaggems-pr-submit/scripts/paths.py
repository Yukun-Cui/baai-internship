#!/usr/bin/env python3
"""Shared naming/path helpers for the FlagGems PR submit skill."""

from __future__ import annotations

import ast
import os

# ── 前导下划线命名 / 冲突消歧 ──────────────────────────────────────────
#
# 默认规则：前导下划线算子的 id / mark 去掉前导下划线。
# 冲突消歧：当存在仅相差前导下划线的裸算子（如 _linalg_svd vs linalg_svd）时，
#   yaml id / kernel 文件名 / API 保留下划线，pytest mark 用 "underscore" 前缀
#   替代前导下划线（pytest marker 名不能以下划线开头）。
#
# 测试/benchmark 文件名**不参与冲突消歧**：`a` 与 `_a` 一律共用
#   tests/test_a.py 和 benchmark/test_a.py（见 test_file_id）。两个算子在同一
#   文件里靠各自的 mark（`a` / `underscore_a`）区分，pytest -m 可精确选中。
#
# 详见 references/naming.md「前导下划线冲突消歧」。


def id_to_mark(op_id):
    """把 yaml id / op_name 映射为合法的 pytest marker 名。

    前导下划线不能出现在 marker 名中，用 "underscore" 前缀替代。
    尾部/中部下划线保持不变。
    """
    return ("underscore" + op_id) if op_id.startswith("_") else op_id


def detect_underscore_conflict(repo_dir, op_name):
    """探测 op_name 是否与裸算子（去前导下划线后）冲突。

    判据：ops/ 目录存在裸算子 kernel 文件 <bare>.py 即视为冲突。

    仅看 kernel 文件而不单看 operators.yaml 中的裸 id，因为后者会导致
    自引用死循环：提取脚本刚为本算子插入的裸 id（默认规则去掉前导下划线）
    会被 check_operator 当作冲突信号，从而反过来要求保留前导下划线，而一旦
    保留又不再冲突 —— 两种状态都会自相矛盾。真正的冲突（如 `_conj_physical`
    vs 已存在的 `conj_physical`）总是伴随着裸算子的 kernel 文件，因此以 kernel
    文件为准既能识别真实冲突，又避免本算子自身 yaml 条目造成的循环。
    """
    if not op_name.startswith("_"):
        return False
    bare = op_name.lstrip("_")
    if not bare or bare == op_name:
        return False
    bare_kernel = os.path.join(repo_dir, "src/flag_gems/ops", f"{bare}.py")
    if os.path.isfile(bare_kernel):
        return True
    return False


def resolve_op_names(repo_dir, op_name):
    """返回 (op_id, mark_id)。

    - 非冲突：op_id = op_name 去前导下划线；mark_id 与 op_id 相同。
    - 冲突：op_id = op_name（保留前导下划线）；mark_id = "underscore" + op_name。
    """
    if detect_underscore_conflict(repo_dir, op_name):
        return op_name, id_to_mark(op_name)
    op_id = op_name.lstrip("_")
    return op_id, op_id


# ── 测试/benchmark 文件共享 ───────────────────────────────────────────


def test_file_id(op_name):
    """测试/benchmark 文件名用的 id —— 始终去掉前导下划线。

    `a` 和 `_a` 共用 `tests/test_a.py` / `benchmark/test_a.py`：两者同输入可比，
    能直接证明私有版没有额外开销，也避免 reviewer 反复要求合并 "redundant
    underscore" 文件。文件内各算子靠自己的 mark（`a` / `underscore_a`）区分，
    `pytest -m` 可精确选中其中一组。

    注意与 ``resolve_op_names`` 的 op_id 区分：后者是 yaml id / kernel 文件名
    用的（冲突时保留前导下划线），这里只管测试/benchmark 文件名。
    """
    return op_name.lstrip("_")


def test_paths(repo_dir, op_name):
    """返回 (tests/test_<id>.py, benchmark/test_<id>.py) 的绝对路径。"""
    file_id = test_file_id(op_name)
    return (
        os.path.join(repo_dir, "tests", f"test_{file_id}.py"),
        os.path.join(repo_dir, "benchmark", f"test_{file_id}.py"),
    )


def _mark_matches(name, mark_id):
    """mark 是否属于本算子：base mark 本身或其重载变体（``<mark>_out`` 等）。

    重载变体属于同一个算子的 PR 范围，算自己的；只有真正别的算子（如裸 `a`
    对应私名 `_a`）才算共享文件里的邻居。
    """
    return name == mark_id or name.startswith(f"{mark_id}_")


def owned_test_functions(path, mark_id):
    """返回文件中带本算子 mark（``<mark_id>`` 或 ``<mark_id>_<variant>``）的
    test 函数名集合。

    共享文件里同住着别的算子（如 `a` 的 case 住在 `_a` 要写入的 test_a.py），
    对这些文件做"本算子覆盖了什么"的判断时，必须按 mark 过滤到自己的函数，
    否则会把邻居的 case 误算成自己的覆盖。``<mark_id>_out`` 这类重载变体属于
    同一个 PR 的范围，算自己的。解析失败时返回空集合（调用方应退回到全文件
    文本检查）。
    """
    if not os.path.isfile(path):
        return set()
    try:
        with open(path, "r") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError):
        return set()

    owned = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        for deco in node.decorator_list:
            target = deco.func if isinstance(deco, ast.Call) else deco
            if (
                isinstance(target, ast.Attribute)
                and _mark_matches(target.attr, mark_id)
                and isinstance(target.value, ast.Attribute)
                and target.value.attr == "mark"
                and isinstance(target.value.value, ast.Name)
                and target.value.value.id == "pytest"
            ):
                owned.add(node.name)
                break
    return owned


def owned_source(path, mark_id):
    """返回共享文件中属于本算子的源码（模块级代码 + 自己 mark 的函数）。

    用于在共享文件上做文本检查（dtype 硬编码、print、断言用法等）时，把邻居
    算子的函数体排除掉，避免对不属于本 PR 的存量代码报错。本算子一个函数都
    没有（文件里全是邻居的）时返回空串，调用方按"无覆盖"处理。

    邻居的函数块被**替换成空行**而不是删掉，这样返回值与原文件行号一一对应，
    按行号报错的检查（硬编码 shape、行尾空白、行长）仍然能指向真实位置。
    返回值仍是合法 Python（整块连装饰器一起置空），可直接 ast.parse。
    """
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, "r") as f:
            source = f.read()
        tree = ast.parse(source)
    except (OSError, SyntaxError):
        return ""

    owned_names = owned_test_functions(path, mark_id)
    lines = source.split("\n")
    drop = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        if node.name in owned_names:
            continue
        start = min(
            [node.lineno] + [d.lineno for d in node.decorator_list]
        )
        drop.update(range(start, (node.end_lineno or node.lineno) + 1))

    return "\n".join(
        "" if i in drop else line for i, line in enumerate(lines, 1)
    )
