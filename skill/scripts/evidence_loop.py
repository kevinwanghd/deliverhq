#!/usr/bin/env python3
"""
evidence_loop.py —— 证据补全 Loop（可恢复 / 可验证 / 有停止条件）

Loop Engineering 原则的具体落地：不是"让 Agent 干到完成"，而是在
**明确状态 + 真实证据 + 停止条件 + 人工接管边界**下让可自动化节点推进。

这不是新 Agent，而是把现有积木串成一个可恢复 loop：
  - 状态/恢复：复用 cr_state（state.yml），不靠会话记忆
  - 证据判定：复用 reviewgate 同款"真实 evidence"口径（traceability/changed-files/verification-manifest/test-plan）
  - 重试纪律：复用 retry_guard（同类失败达上限→needs_human）
  - 证据留痕：复用 runtime_support.write_gate_evidence 写 evidence bundle

每轮（一次调用）做的事：
  1. 读 state.yml 恢复进度（无则 fail-closed：要求先 init_cr）
  2. 扫描 CR 缺哪些 evidence（只读真实文件，不信自述）
  3. 缺 → 输出结构化 gaps + 明确 next_action，写 evidence bundle，状态置 needs-human
  4. 齐 → loop done（next_action=进入 ReviewGate）
本脚本只"推进+判定+留痕"，不替人写文件、不自动发布。

停止条件（stop_rules）：
  success = 全部必需 evidence 齐全
  needs_human = 存在缺口（需人补 traceability/changed-files/manifest/test-plan）
  fail-closed = 无 state.yml（要求先 init_cr）

跨平台 / Python 3.6 兼容。

用法：
  python evidence_loop.py <CR目录>
  python evidence_loop.py <CR目录> --json    # 仅输出机器可读结果
"""

import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("需要 PyYAML：pip install PyYAML")
    sys.exit(2)


class Color:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    END = "\033[0m"


# 必需 evidence 及其缺失时的 next_action（与 reviewgate 口径一致）
REQUIRED_EVIDENCE = [
    ("acceptance-spec.md", "缺验收规格", "运行 Spec Agent 生成 acceptance-spec.md（含 AC-N）"),
    ("traceability.yml", "缺可追溯映射", "补 traceability.yml：需求→现有代码→测试 的映射"),
    ("evidence/changed-files.json", "缺变更清单", "生成 changed-files.json（git diff 或人工列出本 CR 改动文件）"),
    ("verification-manifest.yml", "缺验证清单", "补 verification-manifest.yml：build/test/lint 真实命令"),
    ("test-plan.md", "缺测试计划", "补 test-plan.md：覆盖各 AC 的测试用例"),
]

PLACEHOLDER_MARKS = ("{{", "[待确认]", "[TODO]")


def _has_placeholder(path):
    try:
        c = path.read_text(encoding="utf-8", errors="ignore")
        return any(m in c for m in PLACEHOLDER_MARKS)
    except Exception:
        return False


def scan_gaps(cr_dir):
    """扫描缺口。返回 gaps 列表，每项 {evidence, reason, next_action}。只读真实文件。"""
    gaps = []
    for rel, reason, action in REQUIRED_EVIDENCE:
        p = cr_dir / rel
        if not p.exists():
            gaps.append({"evidence": rel, "reason": reason, "next_action": action})
        elif p.suffix in (".md", ".yml") and _has_placeholder(p):
            gaps.append({"evidence": rel, "reason": "%s（仍含占位符）" % reason,
                         "next_action": "填实 %s 的占位符（{{}}/[待确认]/[TODO]）" % rel})
    return gaps


def run_evidence_loop(cr_path, json_only=False):
    cr_dir = Path(cr_path)
    scripts_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(scripts_dir))

    # fail-closed：必须有 state.yml（不靠会话记忆）
    try:
        from cr_state import load_state
    except Exception:
        load_state = None
    state = load_state(cr_dir) if load_state else None
    if state is None:
        msg = "无 state.yml —— 请先 init_cr.py 创建 CR（fail-closed，不靠会话记忆）"
        if json_only:
            print(json.dumps({"loop": "evidence", "result": "fail_closed",
                              "reason": msg, "gaps": []}, ensure_ascii=False, indent=2))
        else:
            print("%s✗ %s%s" % (Color.RED, msg, Color.END))
        return "fail_closed", []

    if not json_only:
        print("%s=== 证据补全 Loop ===%s" % (Color.BLUE, Color.END))
        print("CR: %s | lane: %s | 当前状态: %s\n"
              % (cr_dir.name, state.lane, state.current_state.value))

    gaps = scan_gaps(cr_dir)

    # 决定结果与 next_action
    if gaps:
        result = "needs_human"
        next_action = gaps[0]["next_action"]
    else:
        result = "done"
        next_action = "证据齐全，运行 ReviewGate/QualityGate 验收"

    # 写 evidence bundle（复用 runtime_support）
    try:
        from runtime_support import write_gate_evidence
        write_gate_evidence(
            cr_dir,
            "evidence_loop",
            "pass" if result == "done" else "blocked",
            blocking_items=[g["reason"] for g in gaps],
            commands_run=["evidence_loop.py scan"],
            artifacts=["evidence/evidence_loop-result.json"],
            next_action=next_action,
            metadata={"loop": "evidence", "gaps": gaps},
        )
    except Exception:
        pass

    # 写回状态（缺口→needs_human）
    try:
        from cr_state import load_state as _ls, save_state, CRState
        from datetime import datetime
        st = _ls(cr_dir)
        if st and gaps:
            st.current_state = CRState.NEEDS_HUMAN
            st.requires_human = True
            st.blocking_reason = "证据补全 Loop: %d 项证据缺口" % len(gaps)
            st.updated_at = datetime.now().isoformat()
            save_state(cr_dir, st)
    except Exception:
        pass

    if json_only:
        print(json.dumps({
            "loop": "evidence", "cr_id": cr_dir.name, "result": result,
            "gaps": gaps, "next_action": next_action,
        }, ensure_ascii=False, indent=2))
        return result, gaps

    # 人类可读输出
    if gaps:
        print("%s[证据缺口] %d 项%s" % (Color.RED, len(gaps), Color.END))
        for i, g in enumerate(gaps, 1):
            print("  %d. %s（%s）" % (i, g["evidence"], g["reason"]))
            print("     → %s" % g["next_action"])
        print("\n%s=== Loop 结果 ===%s" % (Color.BLUE, Color.END))
        print("%s🔶 NEEDS-HUMAN — 证据未齐，需人工补全后重跑本 loop%s" % (Color.YELLOW, Color.END))
        print("下一步: %s" % next_action)
        print("（已写 evidence/evidence_loop-result.json，状态置 needs_human）")
    else:
        print("%s=== Loop 结果 ===%s" % (Color.BLUE, Color.END))
        print("%s✅ DONE — 全部必需证据齐全%s" % (Color.GREEN, Color.END))
        print("下一步: %s" % next_action)
    return result, gaps


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("用法: python evidence_loop.py <CR目录> [--json]")
        sys.exit(1)
    result, gaps = run_evidence_loop(args[0], json_only="--json" in sys.argv)
    # 退出码：done=0；needs_human/fail_closed=1（可被编排/CI 捕获）
    sys.exit(0 if result == "done" else 1)


if __name__ == "__main__":
    main()
