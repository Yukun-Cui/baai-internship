#!/usr/bin/env bash
# run_precommit.sh <op> [--repo-dir DIR] [--staged]
#
# 用真实 pre-commit 校验 MUSA 特化文件（与 CI code-style 同一条链路）。
#   --staged: 额外校验「将要推送的 __init__.py」（从 master 重建 + 插入注册行）
#             因为 PR 里的 __init__.py 不是 worktree 那份。
set -uo pipefail

OP="${1:?Usage: run_precommit.sh <op> [--repo-dir DIR] [--staged]}"
shift
REPO_DIR="/root/FlagGems"
STAGED=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-dir) REPO_DIR="$2"; shift 2 ;;
    --staged) STAGED=1; shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

MTH="src/flag_gems/runtime/backend/_mthreads/ops"
WT="$REPO_DIR/.worktrees/gen-${OP}"
FILES=()

[ -f "$WT/$MTH/$OP.py" ] || { echo "[✗] missing $WT/$MTH/$OP.py" >&2; exit 1; }
FILES+=("$REPO_DIR/.worktrees/gen-${OP}/$MTH/$OP.py")
[ -f "$WT/$MTH/__init__.py" ] && FILES+=("$REPO_DIR/.worktrees/gen-${OP}/$MTH/__init__.py")

echo "=== pre-commit (worktree) ==="
cd "$REPO_DIR" || exit 1
pre-commit run --files "${FILES[@]}" 2>&1 | tee /tmp/precommit_${OP}.log | \
  grep -E "Passed|Failed|modified" | grep -v Skipped
rc=${PIPESTATUS[0]}
if grep -q "Failed" /tmp/precommit_${OP}.log; then
  echo "[✗] pre-commit FAILED — fix before creating/updating the PR" >&2
  exit 1
fi
echo "[✓] worktree files clean"

if [ "$STAGED" -eq 1 ]; then
  echo
  echo "=== pre-commit (content to be pushed) ==="
  TMP=$(mktemp -d)
  mkdir -p "$TMP/$MTH"
  # fetch master __init__.py, insert registration (isort-wrapped), fetch kernel from worktree
  python3 - "$OP" "$TMP" "$REPO_DIR" "$MTH" <<'PY'
import base64, json, subprocess, sys, re
op, tmp, repo, mth = sys.argv[1:5]
def gh(*a):
    p = subprocess.run(["gh","api"]+list(a), capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        sys.exit(f"gh api failed: {p.stderr[:200]}")
    return p.stdout
init = base64.b64decode(json.loads(gh(f"repos/flagos-ai/FlagGems/contents/{mth}/__init__.py?ref=master"))["content"]).decode()
def import_line(op):
    one = f"from .{op} import {op}"
    if len(one) <= 88: return one
    return f"from .{op} import (\n    {op},\n)"
imp = import_line(op)
if imp not in init and f"from .{op} import {op}" not in init:
    lines = init.split("\n"); idx = None
    for i, l in enumerate(lines):
        m = re.match(r"^from \.(\w+) import", l)
        if m and m.group(1) > op: idx = i; break
    lines.insert(idx if idx is not None else len(lines), imp); init = "\n".join(lines)
    s = init.index("__all__ = ["); e = init.index("]", s)
    blk = init[s:e].split("\n"); j = None
    for i, l in enumerate(blk):
        t = l.strip().rstrip(",").strip('"')
        if t and not t.startswith("__all__") and t > op: j = i; break
    blk.insert(j if j is not None else len(blk), f'    "{op}",')
    init = init[:s] + "\n".join(blk) + init[e:]
open(f"{tmp}/{mth}/__init__.py","w").write(init)
print("built staged __init__.py")
PY
  cp "$WT/$MTH/$OP.py" "$TMP/$MTH/$OP.py"
  pre-commit run --files "$TMP/$MTH/__init__.py" "$TMP/$MTH/$OP.py" 2>&1 | tee /tmp/precommit_${OP}_staged.log | \
    grep -E "Passed|Failed|modified" | grep -v Skipped
  if grep -q "Failed" /tmp/precommit_${OP}_staged.log; then
    echo "[✗] pre-commit FAILED on content to be pushed" >&2
    rm -rf "$TMP"; exit 1
  fi
  echo "[✓] content to be pushed is clean"
  rm -rf "$TMP"
fi
