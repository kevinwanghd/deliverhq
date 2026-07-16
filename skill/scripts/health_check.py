#!/usr/bin/env python3
"""
DeliverHQ health_check — 已安装核心的轻量健康自检（随包发布，面向用户）。

用法: python scripts/health_check.py [DeliverHQ核心目录]

与 dev/scripts/selftest.py 的区别：
  - selftest 是**框架开发者**的全量契约测试，依赖 dev/ 下的夹具（CR-EXAMPLE、
    evals 等），只在 DeliverHQ 仓库内运行；
  - health_check 只做在**已初始化项目**里有意义、且不依赖任何开发夹具的检查：
    骨架完整性 + dir-graph 合法性 + 脚本可编译。用户装完 / doctor 跑的是它。

输出末尾打印 `通过: N/M`，供 bin/cli.js 与 publish 流程解析。
"""

import sys
sys.dont_write_bytecode = True
import subprocess
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    from runtime_support import configure_console
    configure_console()
except Exception:  # runtime_support 缺失不应让健康检查崩溃
    pass

# 被检核心目录：默认本脚本所在 scripts/ 的上一级；可用 argv[1] 覆盖。
ROOT = _SCRIPTS_DIR.parent
positional = [a for a in sys.argv[1:] if not a.startswith("--")]
if positional:
    ROOT = Path(positional[0]).resolve()

PASS = "✅"
FAIL = "❌"


def section(title):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")


def _run(script_args):
    return subprocess.run(
        [sys.executable, *[str(a) for a in script_args]],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def check_skeleton():
    """骨架完整性：委托 check_skeleton.py。"""
    section("1. 骨架完整性")
    script = ROOT / "scripts" / "check_skeleton.py"
    if not script.exists():
        print(f"  {FAIL} check_skeleton.py 不存在")
        return False
    result = _run([script, ROOT])
    if result.returncode == 0:
        print(f"  {PASS} 骨架完整")
        return True
    print(f"  {FAIL} 骨架不完整")
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        if "✗" in line:
            print(f"    {line.strip()}")
    return False


def check_dir_graph():
    """dir-graph.yaml 合法性：委托 dir_graph_lint.py（占位符仅告警不阻断）。"""
    section("2. dir-graph 合法性")
    script = ROOT / "scripts" / "dir_graph_lint.py"
    graph = ROOT / "dir-graph.yaml"
    if not script.exists() or not graph.exists():
        print(f"  {FAIL} dir_graph_lint.py 或 dir-graph.yaml 不存在")
        return False
    result = _run([script, graph])
    if result.returncode == 0:
        print(f"  {PASS} dir-graph 合法")
        return True
    print(f"  {FAIL} dir-graph 校验失败")
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("-"):
            print(f"    {stripped}")
    return False


def check_scripts_compile():
    """脚本可编译：对 scripts/*.py 逐个 compile()，捕获语法错误。"""
    section("3. 脚本可编译")
    scripts_dir = ROOT / "scripts"
    all_ok = True
    failed = []
    for script in sorted(scripts_dir.glob("*.py")):
        try:
            compile(script.read_text(encoding="utf-8"), str(script), "exec")
        except Exception as exc:
            all_ok = False
            failed.append((script.name, exc))
    if all_ok:
        print(f"  {PASS} 全部脚本可编译")
    else:
        print(f"  {FAIL} {len(failed)} 个脚本编译失败:")
        for name, exc in failed[:10]:
            print(f"    - {name}: {exc}")
    return all_ok


def main():
    print("=== DeliverHQ health_check ===")
    print(f"核心目录: {ROOT}")

    checks = [
        ("骨架完整性", check_skeleton),
        ("dir-graph 合法性", check_dir_graph),
        ("脚本可编译", check_scripts_compile),
    ]

    results = {}
    for name, fn in checks:
        try:
            results[name] = fn()
        except Exception as exc:  # 单项异常不应终止整轮
            print(f"  {FAIL} {name} 执行异常: {exc}")
            results[name] = False

    passed = sum(1 for ok in results.values() if ok)
    total = len(results)

    section("结果")
    for name, ok in results.items():
        print(f"  {PASS if ok else FAIL} {name}")
    print(f"\n通过: {passed}/{total}")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
