#!/usr/bin/env python3
"""
Routing Eval 自动化 - 评估 DeliverHQ 的触发准确率。

读取 evals/skill-routing-cases.md 和 evals/workflow-routing-cases.md。
要求：真实读取 case；total=0 必须失败。
"""


import re
import sys
sys.dont_write_bytecode = True
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from routing_rules import route_request
from runtime_support import configure_console

ROOT = Path(__file__).resolve().parent.parent
configure_console()


@dataclass
class RoutingCase:
    case_id: str
    prompt: str
    expected_trigger: bool
    expected_workflow: Optional[str] = None
    reason: str = ""


def _extract_markdown_rows(section: str) -> List[List[str]]:
    rows = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 3 or cells[0] in {"#", "维度"}:
            continue
        rows.append(cells)
    return rows


def _section(content: str, start_marker: str, end_markers: List[str]) -> str:
    start = content.find(start_marker)
    if start == -1:
        return ""
    end = len(content)
    for marker in end_markers:
        pos = content.find(marker, start + len(start_marker))
        if pos != -1:
            end = min(end, pos)
    return content[start:end]


def parse_skill_routing_cases() -> List[RoutingCase]:
    file_path = ROOT / "evals" / "skill-routing-cases.md"
    if not file_path.exists():
        return []

    content = file_path.read_text(encoding="utf-8")
    cases: List[RoutingCase] = []

    positive = _section(content, "## ✅ 应该触发", ["## ❌ 不应该触发", "## 🟡 边界场景"])
    for cells in _extract_markdown_rows(positive):
        cases.append(RoutingCase(
            case_id=f"skill_positive_{cells[0]}",
            prompt=cells[1].strip('"“”'),
            expected_trigger=True,
            reason=cells[2] if len(cells) > 2 else "",
        ))

    negative = _section(content, "## ❌ 不应该触发", ["## 🟡 边界场景", "## 评估标准"])
    for cells in _extract_markdown_rows(negative):
        cases.append(RoutingCase(
            case_id=f"skill_negative_{cells[0]}",
            prompt=cells[1].strip('"“”'),
            expected_trigger=False,
            reason=cells[2] if len(cells) > 2 else "",
        ))

    boundary = _section(content, "## 🟡 边界场景", ["## 评估标准"])
    for cells in _extract_markdown_rows(boundary):
        # 边界场景的正确行为是询问，不应直接启动完整 DeliverHQ 流程。
        cases.append(RoutingCase(
            case_id=f"skill_boundary_{cells[0]}",
            prompt=cells[1].strip('"“”'),
            expected_trigger=False,
            reason=cells[2] if len(cells) > 2 else "ask_first",
        ))

    return cases


def _extract_fenced_request(block: str) -> str:
    match = re.search(r"\*\*用户请求\*\*:\s*```\s*(.*?)\s*```", block, re.DOTALL)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    return ""


def _extract_expected(block: str, label: str) -> str:
    match = re.search(rf"-\s*{re.escape(label)}:\s*(.+)", block)
    return match.group(1).strip() if match else ""


def _normalize_workflow(value: str) -> str:
    value = value.strip().strip('`')
    value = re.sub(r"\s*\(.+?\)", "", value)
    value = value.replace("`", "")
    value = value.replace(" with `quarantine`", "")
    value = value.replace(" with `adversarial`", "")
    value = value.replace(" with quarantine", "")
    value = value.replace(" with adversarial", "")
    if "或" in value:
        value = value.split("或", 1)[0].strip()
    return value.strip()


def parse_workflow_routing_cases() -> List[RoutingCase]:
    file_path = ROOT / "evals" / "workflow-routing-cases.md"
    if not file_path.exists():
        return []

    content = file_path.read_text(encoding="utf-8")
    cases: List[RoutingCase] = []
    blocks = re.split(r"\n---\s*\n", content)

    for block in blocks:
        title = re.search(r"###\s*Case\s*(\d+):", block)
        if not title:
            continue
        prompt = _extract_fenced_request(block)
        if not prompt:
            continue
        enabled_text = _extract_expected(block, "启用 DeliverHQ")
        workflow_text = _extract_expected(block, "Workflow 模式")
        expected_trigger = "YES" in enabled_text.upper() or "✅" in enabled_text
        expected_workflow = _normalize_workflow(workflow_text) if expected_trigger else "linear"
        cases.append(RoutingCase(
            case_id=f"workflow_{title.group(1)}",
            prompt=prompt,
            expected_trigger=expected_trigger,
            expected_workflow=expected_workflow,
            reason=_extract_expected(block, "原因"),
        ))

    return cases


def simulate_routing_decision(prompt: str) -> Tuple[bool, Optional[str]]:
    decision = route_request(prompt)
    return bool(decision.get("deliverhq_required")), decision.get("workflow_type")


def evaluate_skill_routing(cases: List[RoutingCase]) -> Dict:
    correct = 0
    false_positive = []
    false_negative = []
    for case in cases:
        should_trigger, _ = simulate_routing_decision(case.prompt)
        if should_trigger == case.expected_trigger:
            correct += 1
        elif should_trigger:
            false_positive.append(case.case_id)
        else:
            false_negative.append(case.case_id)
    total = len(cases)
    return {
        "total": total,
        "correct": correct,
        "accuracy": correct / total * 100 if total else 0.0,
        "false_positive": false_positive,
        "false_negative": false_negative,
    }


def evaluate_real_router_regressions() -> Dict:
    cases = [
        ("优化 DeliverHQ skill 的路由规则，先给方案不要修改文件", False, "linear"),
        ("只给优化建议，不要创建 CR，也不要修改代码", False, "linear"),
        ("Plan only: recommend routing changes, do not modify files or create a CR", False, "linear"),
        ("优化 DeliverHQ skill 的路由规则，先给方案，不要实施", False, "linear"),
        ("给我 3 个缓存架构方案（Redis / Memcached / 内存），分析优缺点并推荐一个", True, "generate-and-filter"),
    ]
    failures = []
    for prompt, expected_required, expected_workflow in cases:
        decision = route_request(prompt)
        actual_required = bool(decision.get("deliverhq_required"))
        actual_workflow = decision.get("workflow_type")
        if actual_required != expected_required or actual_workflow != expected_workflow:
            failures.append({
                "prompt": prompt,
                "expected_required": expected_required,
                "actual_required": actual_required,
                "expected_workflow": expected_workflow,
                "actual_workflow": actual_workflow,
            })
    total = len(cases)
    return {
        "total": total,
        "correct": total - len(failures),
        "accuracy": (total - len(failures)) / total * 100 if total else 0.0,
        "failures": failures,
    }


def evaluate_workflow_routing(cases: List[RoutingCase]) -> Dict:
    correct = 0
    misrouted = []
    for case in cases:
        should_trigger, predicted = simulate_routing_decision(case.prompt)
        if should_trigger == case.expected_trigger and (not case.expected_trigger or predicted == case.expected_workflow):
            correct += 1
        else:
            misrouted.append({
                "case_id": case.case_id,
                "expected_trigger": case.expected_trigger,
                "predicted_trigger": should_trigger,
                "expected": case.expected_workflow,
                "predicted": predicted,
            })
    total = len(cases)
    return {
        "total": total,
        "correct": correct,
        "accuracy": correct / total * 100 if total else 0.0,
        "misrouted": misrouted,
    }


def main():
    print("=" * 60)
    print("  DeliverHQ Routing Eval 自动化")
    print("=" * 60)
    print()

    skill_cases = parse_skill_routing_cases()
    wf_cases = parse_workflow_routing_cases()
    skill_result = evaluate_skill_routing(skill_cases)
    wf_result = evaluate_workflow_routing(wf_cases)
    real_router_result = evaluate_real_router_regressions()

    print("1. Skill Routing 评估")
    print("-" * 60)
    print(f"  总用例: {skill_result['total']}")
    print(f"  正确数: {skill_result['correct']}")
    print(f"  准确率: {skill_result['accuracy']:.1f}%")
    if skill_result['total'] == 0:
        print("  ❌ Skill Routing FAIL: 读取到 0 个 case")
    if skill_result.get('false_positive'):
        print(f"  ❌ False Positive: {skill_result['false_positive']}")
    if skill_result.get('false_negative'):
        print(f"  ❌ False Negative: {skill_result['false_negative']}")
    print("  ✅ Skill Routing PASS" if skill_result['total'] > 0 and skill_result['accuracy'] >= 95 else "  ❌ Skill Routing FAIL")
    print()

    print("2. Workflow Routing 评估")
    print("-" * 60)
    print(f"  总用例: {wf_result['total']}")
    print(f"  正确数: {wf_result['correct']}")
    print(f"  准确率: {wf_result['accuracy']:.1f}%")
    if wf_result['total'] == 0:
        print("  ❌ Workflow Routing FAIL: 读取到 0 个 case")
    if wf_result.get('misrouted'):
        print(f"  ❌ Misrouted: {len(wf_result['misrouted'])} 个")
        for item in wf_result['misrouted'][:8]:
            print(f"     {item['case_id']}: expected={item['expected']}, predicted={item['predicted']}")
    print("  ✅ Workflow Routing PASS" if wf_result['total'] > 0 and wf_result['accuracy'] >= 80 else "  ❌ Workflow Routing FAIL")
    print()

    print("3. Real Router Regression 评估")
    print("-" * 60)
    print(f"  总用例: {real_router_result['total']}")
    print(f"  正确数: {real_router_result['correct']}")
    print(f"  准确率: {real_router_result['accuracy']:.1f}%")
    if real_router_result.get('failures'):
        print(f"  ❌ Real Router Failures: {len(real_router_result['failures'])} 个")
        for item in real_router_result['failures']:
            print(f"     prompt={item['prompt']}")
            print(f"       expected_required={item['expected_required']}, actual_required={item['actual_required']}")
            print(f"       expected_workflow={item['expected_workflow']}, actual_workflow={item['actual_workflow']}")
    print("  ✅ Real Router Regression PASS" if real_router_result['total'] > 0 and real_router_result['accuracy'] == 100 else "  ❌ Real Router Regression FAIL")

    print()
    print("=" * 60)
    ok = (
        skill_result['total'] > 0
        and wf_result['total'] > 0
        and real_router_result['total'] > 0
        and skill_result['accuracy'] >= 95
        and wf_result['accuracy'] >= 80
        and real_router_result['accuracy'] == 100
    )
    if ok:
        print("  ✅ 所有 Routing Eval 通过")
        sys.exit(0)
    print("  ❌ 部分 Routing Eval 未通过")
    sys.exit(1)


if __name__ == "__main__":
    main()
