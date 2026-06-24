#!/usr/bin/env python3
"""
handoff_state.py —— 极小 STATE 指针（借 Pocock /handoff，替代 SessionStart hook）

解决的问题：长会话 / compaction 后，Agent 忘记自己处在治理链条哪一环、下一道门是什么。

为什么不用 SessionStart hook：那需要每个 harness 一套 shim（hooks-codex.json /
run-hook.cmd / …），对 DeliverHQ 要同时打 Claude/Hermes/Codex/Gemini 是 4 套膨胀，
且 research 将其列为 anti-pattern。这里改用 **agent 无关的产物**：把"我在哪一环"压成
一个极小、每轮可读的 STATE 指针文件，复用现有 state.yml，零 hook、零 per-harness 代码。

产出 `<home>/STATE.md`（极小，进入口链每轮读）：当前 CR / lane / phase / 下一道门 /
是否 needs_human / 统一不变式提醒。任何 Agent 每轮读它即可重建治理上下文。

跨平台 / Python 3.10+。

用法：
  python handoff_state.py --home <项目根>/DeliverHQ        # 汇总所有活跃 CR，刷新 STATE.md
  python handoff_state.py --home DeliverHQ --cr CR-001     # 只刷新某 CR
  python handoff_state.py --home DeliverHQ --print         # 打印不写文件
"""

import argparse
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

try:
    from cr_state import load_state
except Exception:
    load_state = None

INVARIANT = "done = 建出来的 = 计划的 = 决定的"


def _active_crs(home):
    cr_root = home / "change-requests"
    if not cr_root.exists():
        return []
    out = []
    for d in sorted(cr_root.iterdir()):
        if not d.is_dir() or not d.name.startswith("CR-"):
            continue
        if d.name in ("CR-TEMPLATE",):
            continue
        if (d / "state.yml").exists():
            out.append(d)
    return out


def _summarize(cr_dir):
    if load_state is None:
        return {"cr": cr_dir.name, "error": "cr_state 不可用"}
    st = load_state(cr_dir)
    if not st:
        return {"cr": cr_dir.name, "error": "无 state.yml"}
    return {
        "cr": cr_dir.name,
        "lane": st.lane,
        "phase": st.current_phase,
        "state": st.current_state.value,
        "next_gate": st.next_required_gate or st.next_gate or "-",
        "needs_human": getattr(st, "requires_human", False),
        "blocking": getattr(st, "blocking_reason", None),
    }


def render(summaries):
    lines = []
    lines.append("# DeliverHQ STATE（机器维护，每轮必读）")
    lines.append("")
    lines.append("> 由 `handoff_state.py` 从各 CR 的 state.yml 汇总刷新。")
    lines.append("> 统一不变式：**%s**。声明完成但证据不闭合 → fail-closed。" % INVARIANT)
    lines.append("")
    if not summaries:
        lines.append("（当前无活跃 CR）")
        return "\n".join(lines) + "\n"
    lines.append("| CR | lane | phase | state | 下一道门 | needs_human |")
    lines.append("|---|---|---|---|---|---|")
    for s in summaries:
        if s.get("error"):
            lines.append("| %s | - | - | %s | - | - |" % (s["cr"], s["error"]))
            continue
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            s["cr"], s["lane"], s["phase"], s["state"], s["next_gate"],
            "⚠ 是" if s["needs_human"] else "否",
        ))
    blocked = [s for s in summaries if s.get("blocking")]
    if blocked:
        lines.append("")
        lines.append("**阻塞原因**：")
        for s in blocked:
            lines.append("- %s：%s" % (s["cr"], s["blocking"]))
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="极小 STATE 指针（替代 SessionStart hook）")
    parser.add_argument("--home", required=True, help="<项目根>/DeliverHQ")
    parser.add_argument("--cr", help="只刷新某 CR")
    parser.add_argument("--print", dest="print_only", action="store_true", help="打印不写文件")
    args = parser.parse_args()

    home = Path(args.home)
    if not home.exists():
        print("home 不存在: %s" % home)
        sys.exit(1)

    if args.cr:
        cr_dir = home / "change-requests" / args.cr
        if not cr_dir.exists():
            print("CR 不存在: %s" % cr_dir)
            sys.exit(1)
        summaries = [_summarize(cr_dir)]
    else:
        summaries = [_summarize(d) for d in _active_crs(home)]

    text = render(summaries)

    if args.print_only:
        sys.stdout.write(text)
        return

    out = home / "STATE.md"
    out.write_text(text, encoding="utf-8")
    print("已刷新 %s（%d 个活跃 CR）" % (out, len([s for s in summaries if not s.get("error")])))


if __name__ == "__main__":
    main()
