#!/usr/bin/env python3
"""Shared paths for the FlagGems PR submit skill."""

from __future__ import annotations

import os
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path(
    os.environ.get("FLAGGEMS_PR_SUBMIT_DATA_DIR", SKILL_DIR / "data")
).expanduser()


def _resolve_data_file(env_name: str, filename: str) -> str:
    explicit = os.environ.get(env_name)
    if explicit:
        return str(Path(explicit).expanduser())
    return str(DATA_DIR / filename)


NORM_XLSX = _resolve_data_file("FLAGGEMS_NORM_XLSX", "规范名.xlsx")
PR_XLSX = _resolve_data_file("FLAGGEMS_PR_XLSX", "第一批pr算子.xlsx")
RECORD_PATH = _resolve_data_file("FLAGGEMS_PR_RECORD_PATH", "pr状态记录.md")


# ── 前导下划线命名 / 冲突消歧 ──────────────────────────────────────────
#
# 默认规则：前导下划线算子的 id / mark / 文件名去掉前导下划线。
# 冲突消歧：当存在仅相差前导下划线的裸算子（如 _linalg_svd vs linalg_svd）时，
#   id / 文件名保留下划线，pytest mark 用 "underscore" 前缀替代前导下划线
#   （pytest marker 名不能以下划线开头）。
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
