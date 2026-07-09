#!/usr/bin/env python3
"""Operator source/implementation/canonical name planning for FlagGems PR scripts.

The worktree generator name is not always the internal wrapper name, and neither
is always the final submitted operator name.

- source_name: generated worktree/module file name, e.g. Cross_Attention
- impl_name: worktree internal wrapper/pytest mark/op_name, e.g. cross_attention
- canonical_name: final submitted/registered name, e.g. CrossAttention
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    import operator_registry
except Exception:  # pragma: no cover - scripts should still run without registry deps
    operator_registry = None


@dataclass(frozen=True)
class NamePlan:
    input_name: str
    source_name: str
    impl_name: str
    canonical_name: str
    source_op_id: str
    impl_op_id: str
    canonical_op_id: str
    worktree_dir: str
    registry_row: int | None = None
    registry_pr_url: str | None = None
    registry_speedup: str | None = None

    @property
    def renamed(self) -> bool:
        return self.source_name != self.canonical_name or self.impl_name != self.canonical_name


def op_id(name: str) -> str:
    return name.lstrip("_")


def normalize_key(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "", name).lower()


def _lookup(name: str) -> dict:
    if operator_registry is None:
        return {}
    try:
        return operator_registry.lookup(name)
    except Exception:
        return {}


def _valid_norm(result: dict) -> str | None:
    norm = str(result.get("规范名") or "").strip()
    if not norm or norm == "nan":
        return None
    # operator_registry falls back to input when the norm table has no row.
    if result.get("行号") is None:
        return None
    return norm


def _find_worktree_source(repo_dir: str, name: str) -> tuple[str | None, str | None]:
    wt_root = Path(repo_dir) / ".worktrees"
    direct = wt_root / f"gen-{name}"
    if direct.is_dir():
        return name, str(direct)

    if not wt_root.is_dir():
        return None, None

    target = normalize_key(name)
    matches: list[tuple[str, Path]] = []
    for child in wt_root.iterdir():
        if not child.is_dir() or not child.name.startswith("gen-"):
            continue
        source = child.name[len("gen-"):]
        if normalize_key(source) == target:
            matches.append((source, child))

    if len(matches) == 1:
        source, path = matches[0]
        return source, str(path)
    return None, None


def _first_public_name(names: list[str]) -> str | None:
    if not names:
        return None
    for name in names:
        if not name.endswith("_") and not name.endswith("_out") and "kernel" not in name.lower():
            return name
    for name in names:
        if not name.endswith("_out") and "kernel" not in name.lower():
            return name
    return names[0]


def _impl_from_ops_init(worktree_dir: str, source_name: str) -> str | None:
    init_path = Path(worktree_dir) / "src/flag_gems/ops/__init__.py"
    if not init_path.is_file():
        return None
    try:
        tree = ast.parse(init_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return None
    module = f"flag_gems.ops.{source_name}"
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            names = [alias.asname or alias.name for alias in node.names]
            return _first_public_name(names)
    return None


def _impl_from_kernel_file(worktree_dir: str, source_name: str) -> str | None:
    kernel_path = Path(worktree_dir) / f"src/flag_gems/ops/{source_name}.py"
    if not kernel_path.is_file():
        return None
    try:
        tree = ast.parse(kernel_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return None

    public = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        is_jit = any(
            (isinstance(d, ast.Attribute) and d.attr == "jit")
            or (isinstance(d, ast.Name) and d.id == "jit")
            for d in node.decorator_list
        )
        if not is_jit:
            public.append(node.name)
    return _first_public_name(public)


def infer_impl_name(worktree_dir: str, source_name: str) -> str:
    return (
        _impl_from_ops_init(worktree_dir, source_name)
        or _impl_from_kernel_file(worktree_dir, source_name)
        or source_name
    )


def build_name_plan(
    input_name: str,
    repo_dir: str,
    source_name: str | None = None,
    canonical_name: str | None = None,
    impl_name: str | None = None,
) -> NamePlan:
    clean = input_name.replace("aten::", "").strip()
    if not clean:
        raise ValueError("operator name is empty")

    lookup_result = _lookup(clean)
    canonical = canonical_name or _valid_norm(lookup_result) or clean

    source = source_name
    worktree = None
    if source:
        found_source, found_worktree = _find_worktree_source(repo_dir, source)
        source = found_source or source
        worktree = found_worktree or str(Path(repo_dir) / ".worktrees" / f"gen-{source}")
    else:
        source, worktree = _find_worktree_source(repo_dir, clean)
        if source is None and canonical != clean:
            source, worktree = _find_worktree_source(repo_dir, canonical)
        if source is None:
            source = clean
            worktree = str(Path(repo_dir) / ".worktrees" / f"gen-{source}")

    impl = impl_name or infer_impl_name(worktree, source)

    return NamePlan(
        input_name=clean,
        source_name=source,
        impl_name=impl,
        canonical_name=canonical,
        source_op_id=op_id(source),
        impl_op_id=op_id(impl),
        canonical_op_id=op_id(canonical),
        worktree_dir=worktree or str(Path(repo_dir) / ".worktrees" / f"gen-{source}"),
        registry_row=lookup_result.get("行号"),
        registry_pr_url=lookup_result.get("PR链接"),
        registry_speedup=lookup_result.get("加速比"),
    )


def plan_dir(repo_dir: str) -> Path:
    return Path(repo_dir) / ".name_plan"


def write_name_plan(repo_dir: str, plan: NamePlan) -> None:
    directory = plan_dir(repo_dir)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{plan.canonical_name}.json").write_text(
        json.dumps(asdict(plan), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_name_plan(repo_dir: str, canonical_name: str) -> NamePlan | None:
    path = plan_dir(repo_dir) / f"{canonical_name}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("impl_name", data.get("source_name", canonical_name))
        data.setdefault("impl_op_id", op_id(data["impl_name"]))
        data.setdefault("source_op_id", op_id(data.get("source_name", canonical_name)))
        data.setdefault("canonical_op_id", op_id(data.get("canonical_name", canonical_name)))
        return NamePlan(**data)
    except Exception:
        return None
