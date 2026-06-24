#!/usr/bin/env python3
"""
gate_composition_check.py —— Gate 冻结 + 组合规则（治理债止血）

借 Matt Pocock 的组合纪律（user-invoked 只能调 model-invoked，不能调另一个
user-invoked），落成 DeliverHQ 的两条机器可检约束，遏制"每个小版本加一道 Gate /
Gate 套 Gate"的治理债：

  约束 1 —— Gate 集合冻结：
    当前 Gate 集合是冻结基线（FROZEN_GATES）。新增/删除 Gate 脚本必须显式更新本文件，
    并在 CR 里论证"现有 Gate 无法覆盖"。脚本目录里出现未登记的 *gate*.py，或登记的
    Gate 脚本缺失 → BLOCK。

  约束 2 —— 组合规则（禁 Gate 套 Gate 的隐式链）：
    Gate 脚本之间默认不得 import / 调用彼此（避免"A 跑 B 跑 C"的隐藏耦合，让每道 Gate
    各自独立、可被编排器显式串联）。唯一例外是 ALLOWED_GATE_EDGES 里显式登记的边。
    出现未登记的 gate->gate 依赖 → BLOCK。

  说明：编排（skill_orchestrator.py 按顺序 subprocess 调各 Gate）不属于"Gate 套 Gate"——
  那是显式编排层，不是 Gate 内部偷偷调另一个 Gate。本检查只看 Gate 脚本**自身**是否
  import / exec 了其它 Gate 脚本。

跨平台 / Python 3.10+。

用法：
  python gate_composition_check.py            # 检查冻结集合与组合规则
  python gate_composition_check.py --list     # 仅列出冻结 Gate 集合
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


class Color:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    END = "\033[0m"


# ── 约束 1：冻结 Gate 集合（单一事实源）──────────────────────────
# 改这里 = 改 Gate 集合，必须经 CR 论证。键=Gate 模块名（无 .py），值=一句话职责。
FROZEN_GATES = {
    "specgate": "验收规格完备性",
    "designgate": "UI/设计产物完备性",
    "architecturegate": "架构设计人工确认（第二道人工门）",
    "pre_dev_gate": "开发前综合门禁",
    "permissiongate": "最小权限边界检查",
    "reviewgate": "对抗式代码审查",
    "qualitygate": "真实构建/测试/静态分析",
    "deploygate": "部署就绪检查",
    "writeback_gate": "知识沉淀完整性",
    "structuregate": "项目结构契约",
    "reverse_spec_gate": "逆向需求未裁决高风险阻断",
}

# 非 Gate 但文件名含 "gate" 的辅助脚本（不计入冻结集合，但允许存在）
NON_GATE_ALLOWLIST = {
    "gate_contract_check",   # 验证 Gate 正反例与参数契约（元检查，非 Gate 本身）
    "gate_json_output",      # Gate evidence JSON schema helper
    "gate_composition_check",  # 本脚本自身
}

# ── 约束 2：允许的 gate->gate 依赖边（显式白名单）────────────────
# 形如 (caller_module, callee_module)。除此之外的 gate->gate import 一律 BLOCK。
ALLOWED_GATE_EDGES = {
    # pre_dev_gate 在开发前综合检查里复用权限边界检查，属已声明的合理组合。
    ("pre_dev_gate", "permissiongate"),
}


def _gate_like_scripts():
    """scripts/ 下文件名含 'gate' 的 .py（不含本检查的辅助 allowlist 判断）。"""
    out = []
    for p in sorted(SCRIPTS.glob("*.py")):
        stem = p.stem
        if "gate" in stem.lower():
            out.append(stem)
    return out


def _import_edges():
    """扫描每个冻结 Gate 脚本，找出它 import 的其它冻结 Gate。"""
    edges = set()
    gate_names = set(FROZEN_GATES.keys())
    # import X / from X import ... ；X 为另一个 gate 模块名
    pat = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
    for caller in FROZEN_GATES:
        path = SCRIPTS / (caller + ".py")
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in pat.finditer(text):
            mod = m.group(1)
            if mod in gate_names and mod != caller:
                edges.add((caller, mod))
    return edges


def check(verbose=True):
    blockers = []
    warnings = []

    def say(s):
        if verbose:
            print(s)

    # 约束 1：冻结集合一致性
    say("%s[1. Gate 冻结集合]%s" % (Color.BLUE, Color.END))
    on_disk = set(_gate_like_scripts())
    declared = set(FROZEN_GATES.keys())
    allow = set(NON_GATE_ALLOWLIST)

    # 磁盘上出现未登记的 gate 脚本（既不在冻结集合也不在辅助 allowlist）
    unregistered = sorted(on_disk - declared - allow)
    for name in unregistered:
        blockers.append(
            "发现未登记的 Gate 脚本 %s.py：新增 Gate 须先在 FROZEN_GATES 登记并经 CR 论证" % name
        )
    # 登记的冻结 Gate 脚本缺失
    missing = sorted(name for name in declared if not (SCRIPTS / (name + ".py")).exists())
    for name in missing:
        blockers.append("冻结 Gate 脚本缺失：%s.py（删除 Gate 须更新 FROZEN_GATES 并经 CR 论证）" % name)

    if not unregistered and not missing:
        say("%s  ✓ 冻结集合 %d 个 Gate 与磁盘一致%s" % (Color.GREEN, len(declared), Color.END))
    else:
        for b in blockers:
            say("%s  ✗ %s%s" % (Color.RED, b, Color.END))

    # 约束 2：组合规则
    say("\n%s[2. 组合规则 (禁 Gate 套 Gate)]%s" % (Color.BLUE, Color.END))
    edges = _import_edges()
    illegal = sorted(edges - ALLOWED_GATE_EDGES)
    for caller, callee in illegal:
        blockers.append(
            "未登记的 Gate→Gate 依赖：%s 直接 import %s（如属合理组合，登记到 ALLOWED_GATE_EDGES 并说明）"
            % (caller, callee)
        )
    if not illegal:
        if edges:
            say("%s  ✓ %d 条 gate→gate 边均在白名单内%s" % (Color.GREEN, len(edges), Color.END))
        else:
            say("%s  ✓ Gate 之间无相互依赖%s" % (Color.GREEN, Color.END))
    else:
        for caller, callee in illegal:
            say("%s  ✗ %s → %s 未登记%s" % (Color.RED, caller, callee, Color.END))

    # 白名单里声明了但实际不存在的边 → 提示清理（仅警告）
    stale = sorted(ALLOWED_GATE_EDGES - edges)
    for caller, callee in stale:
        warnings.append("白名单边 %s→%s 实际不存在，可从 ALLOWED_GATE_EDGES 移除" % (caller, callee))

    return blockers, warnings


def main():
    if "--list" in sys.argv:
        print("=== 冻结 Gate 集合 (FROZEN_GATES) ===")
        for name, role in FROZEN_GATES.items():
            print("  %-20s %s" % (name, role))
        sys.exit(0)

    print("%s=== Gate 冻结 + 组合规则检查 ===%s\n" % (Color.BLUE, Color.END))
    blockers, warnings = check(verbose=True)

    print("\n%s=== 结果 ===%s" % (Color.BLUE, Color.END))
    if warnings:
        for w in warnings:
            print("%s  ⚠ %s%s" % (Color.YELLOW, w, Color.END))
    if blockers:
        print("%s❌ BLOCKED%s" % (Color.RED, Color.END))
        for i, b in enumerate(blockers, 1):
            print("  %d. %s" % (i, b))
        sys.exit(1)
    print("%s✅ PASS — Gate 集合冻结、组合规则未被破坏%s" % (Color.GREEN, Color.END))
    sys.exit(0)


if __name__ == "__main__":
    main()
