#!/usr/bin/env python3
"""
anti_gaming_check.py —— 反钻空子客观检查（防 Reward Hacking / Goodhart）

核心原则：从 **git diff 客观证据** 检测作弊，绝不询问 Agent 自评。
（建议#6 的"验收时问 Agent 有没有作弊"是方法论错误：你不能靠问作弊者来抓作弊。）

检测项（均基于 git diff，可复现）：
  1. tests_not_reduced            —— 测试文件/用例净减少 → 疑似删测试过关
  2. no_disabled_assertions      —— 新增 skip/xfail/注释掉的 assert → 疑似禁用断言
  3. coverage_threshold_not_lowered —— verification-manifest 阈值被调低
  4. gate_scripts_unmodified     —— scripts/*gate*.py / selftest.py / *contract*.py 被改 → 疑似改门禁绕过
  5. diff_in_scope               —— 改动落在 goal-contract.boundaries.allowed_paths 之外

任一命中 → BLOCKED（fail-closed）。需要 git 环境；非 git 时降级为 WARNING（无法取证）。

声明⇒证据的完整映射见 docs/verification.md 的「证据类型映射」表（evidence-type-per-claim）。

跨平台 / Python 3.10+。

用法：
  python anti_gaming_check.py <CR目录>           # 读 CR 下 goal-contract.yml 的 allowed_paths
  python anti_gaming_check.py <CR目录> --base <git-ref>   # 指定对比基线，默认 HEAD
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


class Color:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    END = "\033[0m"


# 门禁/自检脚本：被改动视为疑似绕过
GATE_SCRIPT_PATTERNS = ["gate", "selftest", "contract", "anti_gaming"]

# 测试文件识别
TEST_PATTERNS = ["test_", "_test.", ".test.", ".spec.", "/tests/", "/test/", "__tests__"]

# 禁用断言的新增行特征
DISABLE_PATTERNS = [
    re.compile(r"^\+.*@(pytest\.mark\.)?(skip|xfail)", re.I),
    re.compile(r"^\+.*\.skip\(", re.I),
    re.compile(r"^\+\s*#.*assert ", re.I),       # 注释掉的 assert
    re.compile(r"^\+.*it\.skip\(|^\+.*describe\.skip\(", re.I),  # JS
    re.compile(r"^\+.*@Ignore", re.I),            # Java
]


def _git(args, cwd):
    try:
        r = subprocess.run(["git"] + args, cwd=str(cwd),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, encoding="utf-8", errors="replace", timeout=20)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return 1, "", str(e)


def _repo_root(cwd):
    rc, out, _ = _git(["rev-parse", "--show-toplevel"], cwd)
    if rc != 0:
        return None
    return out.strip()


def get_diff(repo_root, base):
    """取 working tree 相对 base 的 diff（含未提交改动）。"""
    rc, out, _ = _git(["diff", base], repo_root)
    if rc != 0:
        # 退化：仅暂存/未跟踪难取，尝试不带 base
        rc, out, _ = _git(["diff"], repo_root)
        if rc != 0:
            return None
    return out


def _is_test_path(path):
    p = path.lower()
    return any(t in p for t in TEST_PATTERNS)


def _is_gate_script(path):
    p = path.lower()
    if not p.endswith(".py"):
        return False
    return any(g in Path(p).name for g in GATE_SCRIPT_PATTERNS)


def check_tests_not_reduced(diff):
    """测试函数定义被净删除，疑似删测试过关。

    精准信号：统计 diff 中被删除(-)与新增(+)的"测试函数定义"行数。
    净删除测试函数 = 强信号（比单纯数行更准，避免被重构噪声淹没）。
    """
    # 测试函数定义特征（跨语言）
    test_def = re.compile(
        r"(def\s+test\w*|def\s+\w*_test|"          # python
        r"\b(it|test|describe)\s*\(|"               # js/ts
        r"@Test\b|public\s+void\s+test\w*|"         # java
        r"func\s+Test\w*)",                          # go
        re.I)
    added = removed = 0
    cur_file = None
    in_test_file = False
    for line in diff.splitlines():
        if line.startswith("diff --git"):
            cur_file = line.split(" b/")[-1] if " b/" in line else None
            in_test_file = bool(cur_file and _is_test_path(cur_file))
            continue
        if not in_test_file:
            continue
        if line.startswith("+") and not line.startswith("+++") and test_def.search(line):
            added += 1
        elif line.startswith("-") and not line.startswith("---") and test_def.search(line):
            removed += 1
    issues = []
    if removed > added:
        issues.append("测试函数净减少 %d 个（删除 %d / 新增 %d，疑似删测试过关）"
                      % (removed - added, removed, added))
    return issues


def check_disabled_assertions(diff):
    issues = []
    cur_file = None
    for line in diff.splitlines():
        if line.startswith("diff --git"):
            cur_file = line.split(" b/")[-1] if " b/" in line else None
        else:
            for pat in DISABLE_PATTERNS:
                if pat.search(line):
                    issues.append("新增禁用断言/跳过测试: %s -> %s"
                                  % (cur_file, line.strip()[:60]))
                    break
    return issues


def check_threshold_lowered(diff):
    """检测 coverage_threshold / threshold 被调低。"""
    issues = []
    # 收集旧值(-)与新值(+)
    old_vals = {}
    new_vals = {}
    key_re = re.compile(r"(coverage_threshold|threshold)\s*[:=]\s*(\d+)")
    for line in diff.splitlines():
        m = key_re.search(line)
        if not m:
            continue
        key, val = m.group(1), int(m.group(2))
        if line.startswith("-"):
            old_vals.setdefault(key, []).append(val)
        elif line.startswith("+"):
            new_vals.setdefault(key, []).append(val)
    for key in old_vals:
        if key in new_vals and new_vals[key] and old_vals[key]:
            if min(new_vals[key]) < max(old_vals[key]):
                issues.append("%s 被调低: %s → %s（疑似降阈值过关）"
                              % (key, max(old_vals[key]), min(new_vals[key])))
    return issues


def check_gate_scripts(diff):
    issues = []
    for line in diff.splitlines():
        if line.startswith("diff --git") and " b/" in line:
            path = line.split(" b/")[-1]
            if _is_gate_script(path):
                issues.append("门禁/自检脚本被修改: %s（疑似改门禁绕过失败）" % path)
    return issues


def check_scope(diff, allowed_paths):
    """改动文件是否都落在 allowed_paths（glob）内。"""
    if not allowed_paths:
        return []   # 未声明范围则不检查
    import fnmatch
    issues = []
    changed = []
    for line in diff.splitlines():
        if line.startswith("diff --git") and " b/" in line:
            changed.append(line.split(" b/")[-1])
    for f in changed:
        if not any(fnmatch.fnmatch(f, pat) for pat in allowed_paths):
            issues.append("改动超出 allowed_paths: %s" % f)
    return issues


def load_allowed_paths(cr_dir):
    gc = cr_dir / "goal-contract.yml"
    if not gc.exists() or yaml is None:
        return []
    try:
        data = yaml.safe_load(gc.read_text(encoding="utf-8")) or {}
        return (data.get("boundaries", {}) or {}).get("allowed_paths", []) or []
    except Exception:
        return []


def check_anti_gaming(cr_path, base="HEAD"):
    print("%s=== 反钻空子检查（客观证据，不问 Agent）===%s\n" % (Color.BLUE, Color.END))
    cr_dir = Path(cr_path)
    repo_root = _repo_root(cr_dir if cr_dir.is_dir() else cr_dir.parent)

    if not repo_root:
        print("%s⚠️  非 git 仓库，无法取 diff 证据 —— 降级为 WARNING（不能确认无作弊）%s"
              % (Color.YELLOW, Color.END))
        return True, []   # 非 git 环境无法取证，不硬阻断（但已警告）

    diff = get_diff(repo_root, base)
    if diff is None:
        print("%s⚠️  无法获取 git diff，降级为 WARNING%s" % (Color.YELLOW, Color.END))
        return True, []
    if not diff.strip():
        print("%s✓ 无改动（diff 为空）%s" % (Color.GREEN, Color.END))
        return True, []

    allowed = load_allowed_paths(cr_dir)
    blockers = []

    checks = [
        ("测试未被削减", check_tests_not_reduced(diff)),
        ("无禁用断言", check_disabled_assertions(diff)),
        ("阈值未被调低", check_threshold_lowered(diff)),
        ("门禁脚本未被改", check_gate_scripts(diff)),
        ("改动在范围内", check_scope(diff, allowed)),
    ]
    for name, issues in checks:
        if issues:
            print("%s  ✗ %s%s" % (Color.RED, name, Color.END))
            for it in issues[:5]:
                print("      - %s" % it)
            blockers.extend(issues)
        else:
            print("%s  ✓ %s%s" % (Color.GREEN, name, Color.END))

    print("\n%s=== 反钻空子结果 ===%s" % (Color.BLUE, Color.END))
    if blockers:
        print("%s❌ BLOCKED - 检测到疑似 reward hacking%s" % (Color.RED, Color.END))
        for i, b in enumerate(blockers, 1):
            print("  %d. %s" % (i, b))
        print("\n%s⛔ 必须交还人类核查（escalate_to_human）。%s" % (Color.RED, Color.END))
        return False, blockers

    print("%s✅ PASS - 未发现钻空子证据%s" % (Color.GREEN, Color.END))
    return True, []


def main():
    parser = argparse.ArgumentParser(description="反钻空子客观检查")
    parser.add_argument("cr_path", help="CR 目录")
    parser.add_argument("--base", default="HEAD", help="git 对比基线，默认 HEAD")
    args = parser.parse_args()
    passed, _ = check_anti_gaming(args.cr_path, base=args.base)
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from cr_state import record_from_arg
        record_from_arg(args.cr_path, "anti_gaming", passed)
    except Exception:
        pass
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
