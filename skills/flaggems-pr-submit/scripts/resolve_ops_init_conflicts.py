#!/usr/bin/env python3
"""解决 src/flag_gems/ops/__init__.py 中 import 和 __all__ 区域的 merge/rebase 冲突。

文件结构：
  1. import 语句区域（按模块名字母序）
  2. __all__ 列表（按导出名字母序）

策略：
  - 提取冲突两侧的 import 语句和 __all__ 条目
  - 合并去重，按字母序重排
  - 重建文件

用法：
    python resolve_ops_init_conflicts.py --repo-dir /path/to/FlagGems
    python resolve_ops_init_conflicts.py --file src/flag_gems/ops/__init__.py --dry-run
    python resolve_ops_init_conflicts.py --repo-dir . --force  # 无冲突时重排
"""

import argparse
import re
import sys
from pathlib import Path

CONFLICT_START = "<<<<<<< "
CONFLICT_MID = "======="
CONFLICT_END = ">>>>>>> "


def find_file(repo_dir: str) -> Path:
    p = Path(repo_dir) / "src" / "flag_gems" / "ops" / "__init__.py"
    if not p.exists():
        print(f"错误: 文件不存在: {p}", file=sys.stderr)
        sys.exit(1)
    return p


def has_conflict_markers(content: str) -> bool:
    return CONFLICT_START in content and CONFLICT_END in content


def strip_conflicts(lines: list[str]) -> list[str]:
    """移除冲突标记，保留两侧内容。"""
    result = []
    for line in lines:
        stripped = line.strip()
        if (stripped.startswith("<<<<<<<") or stripped == "======="
                or stripped.startswith(">>>>>>>")):
            continue
        result.append(line)
    return result


def parse_import_block(lines: list[str]) -> list[str]:
    """解析 import 语句区域，返回完整的 import 语句列表。

    每个 import 语句可能跨多行（带括号的 from ... import (...)）。
    """
    # 先移除冲突标记
    clean_lines = strip_conflicts(lines)

    imports = []
    current = []
    paren_depth = 0
    in_import = False

    for line in clean_lines:
        stripped = line.strip()
        if not stripped:
            continue

        if not in_import:
            if stripped.startswith(("from ", "import ")):
                current = [line]
                paren_depth = line.count("(") - line.count(")")
                if paren_depth == 0:
                    imports.append("\n".join(current))
                    current = []
                else:
                    in_import = True
            # 跳过非 import 行（不应出现在 import 区域）
        else:
            current.append(line)
            paren_depth += line.count("(") - line.count(")")
            if paren_depth <= 0:
                imports.append("\n".join(current))
                current = []
                in_import = False

    return imports


def import_sort_key(imp: str) -> str:
    """提取 import 语句的排序 key。

    from flag_gems.ops.abs import abs -> "flag_gems.ops.abs"
    """
    m = re.match(r"from\s+([\w.]+)\s+import", imp.strip())
    if m:
        return m.group(1)
    m = re.match(r"import\s+([\w.]+)", imp.strip())
    if m:
        return m.group(1)
    return imp.strip()


def normalize_import(imp: str) -> str:
    """标准化 import 语句的格式。"""
    lines = imp.split("\n")
    if len(lines) == 1:
        return lines[0].strip()
    # 多行 import
    result = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if i == 0:
            result.append(stripped)
        elif stripped in (")", ")"):
            result.append(")")
        else:
            result.append("    " + stripped)
    return "\n".join(result)


def parse_all_block(lines: list[str]) -> list[str]:
    """解析 __all__ 列表中的条目。"""
    clean_lines = strip_conflicts(lines)
    entries = []
    for line in clean_lines:
        stripped = line.strip()
        if stripped in ("__all__ = [", "]", ""):
            continue
        # 提取字符串值
        m = re.search(r'["\']([^"\']+)["\']', stripped)
        if m:
            entries.append(m.group(1))
    return entries


def resolve(content: str) -> str:
    """解决冲突并重建文件。"""
    lines = content.split("\n")

    # 定位 __all__ 的起始行
    all_start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("__all__") and "=" in line:
            all_start = i
            break

    if all_start is None:
        print("错误: 未找到 __all__ 定义", file=sys.stderr)
        sys.exit(1)

    # 定位 __all__ 结束（找到匹配的 ]）
    all_end = None
    bracket_depth = 0
    for i in range(all_start, len(lines)):
        stripped = lines[i].strip()
        if (stripped.startswith("<<<<<<<") or stripped == "======="
                or stripped.startswith(">>>>>>>")):
            continue
        bracket_depth += lines[i].count("[") - lines[i].count("]")
        if bracket_depth == 0 and i > all_start:
            all_end = i
            break

    if all_end is None:
        # fallback: 找单独的 ]
        for i in range(all_start + 1, len(lines)):
            if lines[i].strip() == "]":
                all_end = i
                break

    if all_end is None:
        print("错误: 未找到 __all__ 的闭合 ]", file=sys.stderr)
        sys.exit(1)

    # 分三段
    import_lines = lines[:all_start]
    all_lines = lines[all_start:all_end + 1]
    after_lines = lines[all_end + 1:]

    # 解析 import 区域
    imports = parse_import_block(import_lines)
    # 去重（以 sort_key 为准）
    seen_imports = {}
    for imp in imports:
        key = import_sort_key(imp)
        seen_imports[key] = imp

    sorted_imports = [normalize_import(seen_imports[k])
                      for k in sorted(seen_imports.keys())]

    # 解析 __all__ 区域
    all_entries = parse_all_block(all_lines)
    # 去重并排序
    sorted_all = sorted(set(all_entries))

    # 重建文件
    result_parts = []

    # import 区域
    result_parts.append("\n".join(sorted_imports))
    result_parts.append("")  # 空行

    # __all__ 区域
    all_block = "__all__ = [\n"
    for entry in sorted_all:
        all_block += f'    "{entry}",\n'
    all_block += "]"
    result_parts.append(all_block)

    # after 区域
    if after_lines:
        after_text = "\n".join(after_lines)
        # 移除 after 中的冲突标记（如果有）
        if has_conflict_markers(after_text):
            print("⚠️  __all__ 之后仍有冲突标记，需手动处理", file=sys.stderr)
        result_parts.append(after_text)

    return "\n".join(result_parts)


def main():
    parser = argparse.ArgumentParser(
        description="解决 flag_gems/ops/__init__.py 的 merge/rebase 冲突"
    )
    parser.add_argument("--repo-dir", default=".",
                        help="FlagGems 仓库根目录 (默认: 当前目录)")
    parser.add_argument("--file", help="直接指定文件路径")
    parser.add_argument("--dry-run", action="store_true",
                        help="只打印结果，不写入文件")
    parser.add_argument("--force", action="store_true",
                        help="无冲突时也重新排序")
    args = parser.parse_args()

    filepath = Path(args.file) if args.file else find_file(args.repo_dir)
    if not filepath.exists():
        print(f"错误: 文件不存在: {filepath}", file=sys.stderr)
        sys.exit(1)

    content = filepath.read_text(encoding="utf-8")

    if not has_conflict_markers(content) and not args.force:
        print("文件没有冲突标记。如需重新排序，请使用 --force 参数。")
        sys.exit(0)

    resolved = resolve(content)

    if args.dry_run:
        # 打印 __all__ 区域前后几行
        for line in resolved.split("\n"):
            if "__all__" in line or line.strip().startswith('"'):
                break
        import_count = sum(1 for l in resolved.split("\n")
                         if l.strip().startswith("from "))
        all_count = sum(1 for l in resolved.split("\n")
                       if re.match(r'\s+"[^"]+",', l))
        print(f"Import 语句数: {import_count}")
        print(f"__all__ 条目数: {all_count}")
        remaining = has_conflict_markers(resolved)
        if remaining:
            print("\n⚠️  文件仍有冲突标记")
        else:
            print("✅ 无冲突标记")
    else:
        filepath.write_text(resolved, encoding="utf-8")
        import_count = sum(1 for l in resolved.split("\n")
                         if l.strip().startswith("from "))
        all_count = sum(1 for l in resolved.split("\n")
                       if re.match(r'\s+"[^"]+",', l))
        print(f"✅ 已解决 ops/__init__.py 冲突: {filepath}")
        print(f"   Import 语句: {import_count}, __all__ 条目: {all_count}")
        if has_conflict_markers(resolved):
            print("\n⚠️  文件仍有冲突标记，需手动处理")


if __name__ == "__main__":
    main()
