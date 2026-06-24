#!/usr/bin/env python3
"""
reverse_to_spec.py —— 逆向需求转化（目标2 的出口，对接目标1）

把 reverse-spec-candidates.yml 中**已人工确认**的条目，转化为：
  1. acceptance-spec.md   —— 能通过 SpecGate（无模板变量/无待确认占位符）
  2. traceability.yml     —— 反向映射：需求 → 现有代码 → 现有测试
  3. known-deviations.md  —— rejected 条目（判定为 bug/技术债，不固化为需求）

只转化 status in (confirmed, modified) 且 is_real_requirement: true 的条目。
转化前应先通过 ReverseSpecGate（确保无未裁决的高风险条目）。

逆向 traceability 的特点：与正向相反——需求映射到**已存在**的代码与测试。

跨平台 / Python 3.10+。

用法：
  python reverse_to_spec.py <CR目录>
  python reverse_to_spec.py <CR目录> --candidates <自定义yml路径>
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("需要 PyYAML：pip install PyYAML")
    sys.exit(2)


def load_candidates(path):
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _confirmed_real(candidates):
    out = []
    for c in candidates:
        hd = c.get("human_decision", {}) or {}
        if hd.get("status") in ("confirmed", "modified") and hd.get("is_real_requirement") is True:
            out.append(c)
    return out


def _rejected(candidates):
    return [c for c in candidates
            if (c.get("human_decision", {}) or {}).get("status") == "rejected"]


def build_acceptance_spec(project_name, confirmed):
    """生成 acceptance-spec.md（SDD 三段式 + 逐条验收，无 blocker 元素）。"""
    lines = []
    lines.append("# Acceptance Spec: %s（逆向生成）" % project_name)
    lines.append("")
    lines.append("> 由 reverse_to_spec.py 从已人工确认的逆向需求候选转化生成。")
    lines.append("> 每条验收条件均经人工裁决确认为真需求（非 bug/技术债）。")
    lines.append("")

    # 1. Data Spec —— 涉及的模块/源码
    lines.append("## 1. Data Spec")
    lines.append("")
    lines.append("本规格逆向自现有代码，涉及以下模块：")
    lines.append("")
    for c in confirmed:
        src = c.get("source", {}) or {}
        mod = src.get("module", "")
        files = ", ".join(src.get("files", []) or [])
        lines.append("- 模块 `%s`：%s" % (mod, files))
    lines.append("")

    # 2. Interface Spec —— 函数/接口
    lines.append("## 2. Interface Spec")
    lines.append("")
    for c in confirmed:
        src = c.get("source", {}) or {}
        funcs = ", ".join(src.get("functions", []) or []) or "（见源码）"
        lines.append("- `%s`：%s" % (src.get("module", ""), funcs))
    lines.append("")

    # 3. Behavior Spec —— 逐条验收（每条一个场景，满足场景计数）
    lines.append("## 3. Behavior Spec")
    lines.append("")
    lines.append("## 验收条件")
    lines.append("")
    for i, c in enumerate(confirmed, 1):
        criteria = c.get("becomes_acceptance_criteria") or c.get("inferred_behavior") or ""
        src = c.get("source", {}) or {}
        lines.append("### 场景 %d: %s" % (i, c.get("title", c.get("id", ""))))
        lines.append("- 验收条件：%s" % criteria)
        lines.append("- 现有实现：%s" % (", ".join(src.get("files", []) or []) or "（见源码）"))
        hd = c.get("human_decision", {}) or {}
        if hd.get("note"):
            lines.append("- 裁决备注：%s" % hd["note"])
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("**生成时间**: %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("**来源**: reverse-spec-candidates.yml（人工确认）")
    return "\n".join(lines)


def build_traceability(cr_id, project_name, confirmed):
    """生成 traceability.yml：需求 → 现有代码 → 现有测试（反向映射）。"""
    impl = []
    tests = []
    criteria_list = []
    for c in confirmed:
        src = c.get("source", {}) or {}
        criteria_list.append(c.get("becomes_acceptance_criteria") or c.get("title", ""))
        for f in src.get("files", []) or []:
            impl.append({
                "file": f,
                "functions": src.get("functions", []) or [],
                "reverse_mapped": True,   # 标记：逆向映射到已存在代码
            })
        ev = c.get("evidence", {}) or {}
        for t in ev.get("supporting_tests", []) or []:
            tests.append({"case": t, "covers": c.get("id", ""), "type": "existing"})

    return {
        "schema": "deliverhq-traceability",
        "version": 1,
        cr_id: {
            "requirement": "%s 逆向需求（从现有代码确认）" % project_name,
            "priority": "P1",
            "origin": "reverse-engineered",     # 标记来源为逆向
            "acceptance_criteria": criteria_list,
            "implementation": impl,
            "tests": tests,
        },
    }


def build_known_deviations(project_name, rejected):
    """生成 known-deviations.md：被判定为 bug/技术债的条目（不固化为需求）。"""
    lines = []
    lines.append("# 已知偏差清单: %s" % project_name)
    lines.append("")
    lines.append("> 逆向扫描中被人工判定为 **bug / 技术债** 的行为（is_real_requirement=false）。")
    lines.append("> 这些**不应固化为需求**，而应作为改造 CR 的候选输入。")
    lines.append("")
    if not rejected:
        lines.append("（无）")
        return "\n".join(lines)
    lines.append("| ID | 模块 | 当前行为 | 判定 | 备注 |")
    lines.append("|---|---|---|---|---|")
    for c in rejected:
        src = c.get("source", {}) or {}
        hd = c.get("human_decision", {}) or {}
        lines.append("| %s | %s | %s | bug/债 | %s |" % (
            c.get("id", ""), src.get("module", ""),
            (c.get("inferred_behavior", "") or "").replace("|", "\\|"),
            (hd.get("note", "") or "").replace("|", "\\|")))
    lines.append("")
    lines.append("**生成时间**: %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="逆向需求 → acceptance-spec + traceability")
    parser.add_argument("cr_path", help="CR 目录路径")
    parser.add_argument("--candidates", default=None, help="自定义 candidates.yml 路径")
    args = parser.parse_args()

    cr_dir = Path(args.cr_path)
    if not cr_dir.exists():
        print("CR 目录不存在: %s" % cr_dir)
        sys.exit(1)

    cand_path = Path(args.candidates) if args.candidates else (cr_dir / "reverse-spec-candidates.yml")
    data = load_candidates(cand_path)
    if data is None:
        print("找不到 reverse-spec-candidates.yml: %s" % cand_path)
        sys.exit(1)

    project_name = (data.get("project", {}) or {}).get("name", cr_dir.name)
    candidates = data.get("candidates", []) or []
    confirmed = _confirmed_real(candidates)
    rejected = _rejected(candidates)

    if not confirmed:
        print("⚠ 没有已确认的真需求条目（confirmed/modified + is_real_requirement:true）。")
        print("  请先用 confirm_reverse_spec.py 裁决，并通过 ReverseSpecGate。")
        sys.exit(1)

    # 1. acceptance-spec.md
    spec_text = build_acceptance_spec(project_name, confirmed)
    spec_path = cr_dir / "acceptance-spec.md"
    spec_path.write_text(spec_text, encoding="utf-8")

    # 2. traceability.yml
    trace = build_traceability(cr_dir.name, project_name, confirmed)
    trace_path = cr_dir / "traceability.yml"
    with open(trace_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(trace, f, allow_unicode=True, sort_keys=False)

    # 3. known-deviations.md
    dev_text = build_known_deviations(project_name, rejected)
    dev_path = cr_dir / "known-deviations.md"
    dev_path.write_text(dev_text, encoding="utf-8")

    print("✅ 转化完成：")
    print("  - %s（%d 条验收条件）" % (spec_path, len(confirmed)))
    print("  - %s（反向映射到现有代码/测试）" % trace_path)
    print("  - %s（%d 条已知偏差）" % (dev_path, len(rejected)))
    print("\n下一步：运行 specgate.py 验证生成的 acceptance-spec.md，然后进入正向开发链路（目标1）。")


if __name__ == "__main__":
    main()
