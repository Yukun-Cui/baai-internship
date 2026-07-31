#!/usr/bin/env python3
"""解决 src/flag_gems/__init__.py 中 _FULL_CONFIG 的 merge/rebase 冲突。

典型场景：上游 merge 了新 PR，我们的分支 rebase 时在 _FULL_CONFIG 区域产生冲突，
因为双方都按字母序插入了新条目到相邻位置。

解决策略：
1. 解析冲突文件，提取 ours/theirs 两侧的 _FULL_CONFIG 条目
2. 合并去重，按字母序重新排列
3. 重建文件（保留 _FULL_CONFIG 前后的非冲突内容）

用法：
    # 在 rebase/merge 冲突时运行（自动检测并修复 __init__.py）
    python resolve_init_conflicts.py --repo-dir /path/to/FlagGems

    # 预览模式（不写入文件）
    python resolve_init_conflicts.py --repo-dir /path/to/FlagGems --dry-run

    # 指定文件路径
    python resolve_init_conflicts.py --file src/flag_gems/__init__.py
"""

import argparse
import re
import sys
from pathlib import Path


CONFLICT_START = "<<<<<<< "
CONFLICT_MID = "======="
CONFLICT_END = ">>>>>>> "


def find_init_file(repo_dir: str) -> Path:
    """定位 __init__.py 文件。"""
    p = Path(repo_dir) / "src" / "flag_gems" / "__init__.py"
    if not p.exists():
        print(f"错误: 文件不存在: {p}", file=sys.stderr)
        sys.exit(1)
    return p


def has_conflict_markers(content: str) -> bool:
    """检测文件是否包含冲突标记。"""
    return CONFLICT_START in content and CONFLICT_END in content


def extract_sort_key(entry: str) -> str:
    """从条目中提取排序 key（第一个引号内的字符串）。"""
    m = re.search(r'["\']([^"\']+)["\']', entry)
    if m:
        return m.group(1)
    return entry.strip()


def normalize_entry(entry: str) -> str:
    """标准化条目缩进。"""
    lines = entry.split("\n")
    if len(lines) == 1:
        return "    " + lines[0].strip()
    # 多行条目
    result = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if i == 0:
            result.append("    " + stripped)
        elif stripped in ("),", ")"):
            result.append("    " + stripped)
        else:
            result.append("        " + stripped)
    return "\n".join(result)


def parse_entries_from_lines(lines: list[str]) -> list[str]:
    """从一组行中解析出 _FULL_CONFIG 的条目列表。

    跳过冲突标记、空行、_FULL_CONFIG = ( 和 闭合 )。
    """
    entries = []
    current_lines = []
    paren_depth = 0
    in_entry = False

    for line in lines:
        stripped = line.strip()

        # 跳过冲突标记
        if (stripped.startswith("<<<<<<<") or stripped == "======="
                or stripped.startswith(">>>>>>>")):
            continue

        # 跳过文件头尾
        if stripped == "_FULL_CONFIG = (" or stripped.startswith("_FULL_CONFIG = ("):
            continue
        if stripped == ")" and not in_entry:
            continue

        # 跳过空行
        if not stripped:
            continue

        if not in_entry:
            current_lines = [line]
            paren_depth = line.count("(") - line.count(")")
            if paren_depth == 0:
                entries.append("\n".join(current_lines))
                current_lines = []
            else:
                in_entry = True
        else:
            current_lines.append(line)
            paren_depth += line.count("(") - line.count(")")
            if paren_depth == 0:
                entries.append("\n".join(current_lines))
                current_lines = []
                in_entry = False

    return entries


def resolve_full_config_block(content: str) -> str:
    """解决整个文件中 _FULL_CONFIG 区域的冲突，返回修复后的完整文件内容。"""
    lines = content.split("\n")

    # 定位 _FULL_CONFIG = ( 的行号
    config_start = None
    for i, line in enumerate(lines):
        # 可能在冲突区域外，也可能在冲突区域内
        if "_FULL_CONFIG = (" in line and not line.strip().startswith("#"):
            config_start = i
            break

    if config_start is None:
        print("错误: 未找到 _FULL_CONFIG 定义", file=sys.stderr)
        sys.exit(1)

    # 找到闭合 ) —— 在 _FULL_CONFIG 开始后的第一个独立 ) 行
    # 需要考虑冲突标记的干扰
    config_end = None
    # 用一个简单策略：跟踪净括号深度，忽略冲突标记行
    net_parens = 0
    for i in range(config_start, len(lines)):
        stripped = lines[i].strip()
        if (stripped.startswith("<<<<<<<") or stripped == "======="
                or stripped.startswith(">>>>>>>")):
            continue
        net_parens += lines[i].count("(") - lines[i].count(")")
        if net_parens == 0 and i > config_start:
            config_end = i
            break

    if config_end is None:
        print("错误: 未找到 _FULL_CONFIG 的闭合括号", file=sys.stderr)
        sys.exit(1)

    # 提取三部分
    before_lines = lines[:config_start]
    config_lines = lines[config_start:config_end + 1]
    after_lines = lines[config_end + 1:]

    # 检查 before/after 是否还有冲突（不处理）
    before_text = "\n".join(before_lines)
    after_text = "\n".join(after_lines)
    if has_conflict_markers(before_text):
        print("警告: _FULL_CONFIG 前的区域也有冲突，需要手动解决", file=sys.stderr)
        print("  _FULL_CONFIG 区域冲突将被自动解决，其他冲突请手动处理", file=sys.stderr)
    if has_conflict_markers(after_text):
        print("警告: _FULL_CONFIG 后的区域也有冲突，需要手动解决", file=sys.stderr)
        print("  _FULL_CONFIG 区域冲突将被自动解决，其他冲突请手动处理", file=sys.stderr)

    # 从 config 区域解析所有条目（自动跳过冲突标记）
    all_entries = parse_entries_from_lines(config_lines)

    # 去重（以 sort_key 为 key，保留后出现的版本）
    seen = {}
    for entry in all_entries:
        key = extract_sort_key(entry)
        seen[key] = entry

    # 按字母序排列
    sorted_keys = sorted(seen.keys())
    sorted_entries = [normalize_entry(seen[k]) for k in sorted_keys]

    # 重建 _FULL_CONFIG 块
    new_config = "_FULL_CONFIG = (\n"
    new_config += "\n".join(sorted_entries) + "\n"
    new_config += ")"

    # 重组文件
    result = "\n".join(before_lines) + "\n" + new_config + "\n" + "\n".join(after_lines)
    return result


def check_non_config_conflicts(content: str, config_start: int, config_end: int) -> list[tuple[int, int]]:
    """检查 _FULL_CONFIG 区域之外是否有冲突。返回冲突区域列表。"""
    lines = content.split("\n")
    conflicts = []
    in_conflict_start = None

    for i, line in enumerate(lines):
        if i >= config_start and i <= config_end:
            continue
        if line.startswith(CONFLICT_START):
            in_conflict_start = i
        elif line.startswith(CONFLICT_END) and in_conflict_start is not None:
            conflicts.append((in_conflict_start, i))
            in_conflict_start = None

    return conflicts


def main():
    parser = argparse.ArgumentParser(
        description="解决 flag_gems/__init__.py 中 _FULL_CONFIG 的 merge/rebase 冲突"
    )
    parser.add_argument(
        "--repo-dir",
        default=".",
        help="FlagGems 仓库根目录 (默认: 当前目录)",
    )
    parser.add_argument(
        "--file",
        help="直接指定文件路径（覆盖 --repo-dir）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印结果，不写入文件",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="即使没有冲突标记也重新排序 _FULL_CONFIG（用于修复乱序）",
    )
    args = parser.parse_args()

    # 定位文件
    if args.file:
        filepath = Path(args.file)
    else:
        filepath = find_init_file(args.repo_dir)

    if not filepath.exists():
        print(f"错误: 文件不存在: {filepath}", file=sys.stderr)
        sys.exit(1)

    content = filepath.read_text(encoding="utf-8")

    # 检查是否有冲突
    if not has_conflict_markers(content) and not args.force:
        print("文件没有冲突标记。如需重新排序，请使用 --force 参数。")
        sys.exit(0)

    if not has_conflict_markers(content) and args.force:
        print("无冲突标记，--force 模式：重新排序 _FULL_CONFIG...")

    # 解决冲突
    resolved = resolve_full_config_block(content)

    if args.dry_run:
        print("=== 解决后的 _FULL_CONFIG 区域 ===")
        # 只打印 _FULL_CONFIG 区域
        in_config = False
        for line in resolved.split("\n"):
            if "_FULL_CONFIG = (" in line:
                in_config = True
            if in_config:
                print(line)
            if in_config and line.strip() == ")":
                in_config = False
                break
        print(f"\n总条目数: {resolved.count('    (')}")
        remaining_conflicts = has_conflict_markers(resolved)
        if remaining_conflicts:
            print("\n⚠️  文件其他区域仍有冲突，需手动解决")
    else:
        filepath.write_text(resolved, encoding="utf-8")
        entry_count = sum(1 for line in resolved.split("\n")
                         if line.strip().startswith("(") and line.strip() != ")")
        print(f"✅ 已解决 _FULL_CONFIG 冲突并写入: {filepath}")
        print(f"   条目数: {entry_count}")

        remaining_conflicts = has_conflict_markers(resolved)
        if remaining_conflicts:
            print("\n⚠️  文件其他区域仍有冲突，需手动解决：")
            for i, line in enumerate(resolved.split("\n"), 1):
                if line.startswith(CONFLICT_START):
                    print(f"   行 {i}: {line.strip()}")

        # 提示后续操作
        print("\n后续步骤：")
        if remaining_conflicts:
            print("  1. 手动解决其余冲突")
            print("  2. git add src/flag_gems/__init__.py")
            print("  3. git rebase --continue")
        else:
            print("  1. git add src/flag_gems/__init__.py")
            print("  2. git rebase --continue")


if __name__ == "__main__":
    main()
