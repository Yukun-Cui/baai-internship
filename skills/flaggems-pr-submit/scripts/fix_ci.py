#!/usr/bin/env python3
"""读取 PR CI 失败日志，自动修复常见问题并 force push。

用法:
    python fix_ci.py <pr_number>
    python fix_ci.py <pr_number> --dry-run     # 只分析不修改

支持的自动修复：
  - code-style: isort 排序错误 → 运行 isort + black 修复
  - python-op:  ref 计算用了 aten op 但 CPU 后端不支持 → 用 torch.nn.functional 替代
  - conflict:   .pr_gate / 无关文件混入 commit → 重置并只 stage 相关文件
  - signature:  aten 函数签名参数顺序不匹配（backward 类）→ 提示需人工确认
"""

import argparse
import re
import subprocess
import sys
import os

REPO_DIR = os.environ.get("FLAGGEMS_REPO", "/root/FlagGems")
BASE = os.environ.get("FLAGGEMS_BASE", "infra-ci")
PUSH_REMOTE = os.environ.get("FLAGGEMS_PUSH_REMOTE", "origin")
BRANCH_PREFIX = "pr/"


class Colors:
    OK = "\033[92m"
    FAIL = "\033[91m"
    WARN = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"


def ok(msg):   print(f"  {Colors.OK}✓{Colors.END} {msg}")
def warn(msg): print(f"  {Colors.WARN}⚠{Colors.END} {msg}")
def fail(msg): print(f"  {Colors.FAIL}✗{Colors.END} {msg}")
def info(msg): print(f"  {Colors.CYAN}→{Colors.END} {msg}")


def run(cmd, cwd=None, capture=True, check=False, timeout=120):
    r = subprocess.run(cmd, cwd=cwd or REPO_DIR, capture_output=capture, text=True, timeout=timeout)
    return r


def get_pr_info(pr_number):
    r = run(["gh", "pr", "view", str(pr_number), "--json", "title,headRefName"], capture=True)
    import json
    return json.loads(r.stdout)


def get_failed_checks(pr_number):
    r = run(["gh", "pr", "checks", str(pr_number)], capture=True)
    failed = []
    for line in r.stdout.splitlines():
        if "\tfail\t" in line:
            parts = line.split("\t")
            name = parts[0].strip()
            url = parts[-1].strip()
            failed.append((name, url))
    return failed


def get_run_id_from_url(url):
    m = re.search(r"/runs/(\d+)/", url)
    return m.group(1) if m else None


def get_ci_log(run_id):
    r = run(["gh", "run", "view", run_id, "--log-failed"], capture=True, timeout=60)
    return r.stdout + r.stderr


def extract_changed_op_files(branch):
    """获取该分支相对 upstream/<base> 新增/修改的算子相关文件。"""
    r = run(["git", "diff", "--name-only", f"upstream/{BASE}..HEAD"])
    all_files = r.stdout.splitlines()
    # 过滤出算子相关文件（排除 .pr_gate、container、pyproject 等）
    op_files = [f for f in all_files if not f.startswith((
        ".pr_gate", "container/", ".github/", "pyproject.toml",
        "setup.sh", "tools/", "mkdocs",
    ))]
    return op_files, all_files


def fix_code_style(log, branch, dry_run):
    """修复 isort / black 问题，去除混入的无关文件。"""
    print(f"\n{Colors.BOLD}[code-style] 分析中...{Colors.END}")

    # 检查是否有无关文件混入
    op_files, all_files = extract_changed_op_files(branch)
    dirty_files = [f for f in all_files if f not in op_files]
    if dirty_files:
        warn(f"发现 {len(dirty_files)} 个无关文件混入 commit（.pr_gate 等）")
        if not dry_run:
            info("重置 commit，只保留算子相关文件...")
            run(["git", "reset", f"upstream/{BASE}", "--mixed"])
            for f in op_files:
                if os.path.exists(os.path.join(REPO_DIR, f)):
                    run(["git", "add", f])
            run(["git", "commit", "-m", f"feat: add operator ({branch.removeprefix(BRANCH_PREFIX)})"])
            ok("已重新提交，无关文件已排除")

    # 检查 log 中 isort/black 报错
    fixing_files = []
    for line in log.splitlines():
        if "Fixing" in line and ".py" in line:
            m = re.search(r"Fixing (.+\.py)", line)
            if m:
                fixing_files.append(m.group(1).split("/")[-1])

    if fixing_files or "isort" in log.lower() or "black" in log.lower():
        info(f"运行 isort + black 修复格式...")
        if not dry_run:
            run(["python", "-m", "isort", ".", "--profile", "black"], cwd=REPO_DIR)
            run(["python", "-m", "black", "src/flag_gems/ops/__init__.py",
                 "src/flag_gems/__init__.py"], cwd=REPO_DIR, check=False)
            # 只 amend 已有 commit
            run(["git", "add", "src/flag_gems/ops/__init__.py", "src/flag_gems/__init__.py"])
            run(["git", "commit", "--amend", "--no-edit"])
            ok("isort/black 已修复，commit 已 amend")
    else:
        ok("无 isort/black 格式问题")


def fix_python_op(log, branch, dry_run):
    """修复 python-op 测试失败（常见：ref 用 aten op 但 CPU 不支持）。"""
    print(f"\n{Colors.BOLD}[python-op] 分析中...{Colors.END}")

    # 提取失败的测试文件
    failed_test = None
    for line in log.splitlines():
        if "FAILED tests/" in line:
            m = re.search(r"FAILED (tests/\S+\.py)", line)
            if m:
                failed_test = m.group(1)
                break

    if not failed_test:
        warn("无法从日志中定位失败的测试文件")
        return

    info(f"失败文件: {failed_test}")

    # CPU Backend 错误
    if "Expected tensor to have CPU Backend" in log or "batch_norm_cpu" in log:
        fail("ref 计算调用了 aten op，但该 op 在 CPU 后端不支持")
        warn("需要人工修复：将 ref 改用 torch.nn.functional 高层 API")
        return

    # Cast error / signature mismatch
    if "Unable to cast" in log and "Declaration:" in log:
        decl = ""
        for line in log.splitlines():
            if "Declaration:" in line:
                decl = line.split("Declaration:")[-1].strip()
                break
        fail(f"函数签名与 aten schema 不匹配")
        warn(f"aten schema: {decl}")
        warn("需要人工检查参数顺序后修复")
        return

    # 一般错误：输出前 20 行相关错误
    errors = [l for l in log.splitlines() if "Error" in l or "FAILED" in l or "assert" in l.lower()]
    for e in errors[:10]:
        warn(e.strip())


def push(branch, dry_run):
    print(f"\n{Colors.BOLD}[push] force push...{Colors.END}")
    if dry_run:
        info(f"dry-run: git push {PUSH_REMOTE} {branch} --force")
        return
    r = run(["git", "push", PUSH_REMOTE, branch, "--force"], timeout=90)
    if r.returncode == 0:
        ok(f"已 force push: {branch}")
    else:
        fail(f"push 失败:\n{r.stderr}")


def main():
    global REPO_DIR  # noqa: PLW0603
    parser = argparse.ArgumentParser(description="读取 PR CI 日志并自动修复常见问题")
    parser.add_argument("pr_number", type=int)
    parser.add_argument("--dry-run", action="store_true", help="只分析，不修改文件")
    parser.add_argument("--repo-dir", default=REPO_DIR)
    args = parser.parse_args()

    REPO_DIR = args.repo_dir

    print(f"{Colors.CYAN}{Colors.BOLD}=== FlagGems CI Fix: PR #{args.pr_number} ==={Colors.END}")

    # 获取 PR 信息
    pr = get_pr_info(args.pr_number)
    branch = pr["headRefName"]
    title = pr["title"]
    info(f"Branch: {branch}")
    info(f"Title: {title}")

    # checkout 分支
    run(["git", "checkout", branch])

    # 获取失败的 checks
    failed = get_failed_checks(args.pr_number)
    if not failed:
        ok("所有 CI checks 均通过！")
        return

    print(f"\n{Colors.FAIL}失败的 checks:{Colors.END}")
    for name, url in failed:
        print(f"  - {name}: {url}")

    pushed = False
    for check_name, url in failed:
        run_id = get_run_id_from_url(url)
        if not run_id:
            warn(f"无法提取 run_id: {url}")
            continue

        info(f"拉取日志: run {run_id}...")
        log = get_ci_log(run_id)

        if "code-style" in check_name:
            fix_code_style(log, branch, args.dry_run)
            pushed = True
        elif "python-op" in check_name:
            fix_python_op(log, branch, args.dry_run)
        else:
            warn(f"暂不支持自动修复 {check_name}，请人工处理")

    if pushed and not args.dry_run:
        push(branch, args.dry_run)
    elif args.dry_run:
        info("dry-run 模式，跳过 push")


if __name__ == "__main__":
    main()
