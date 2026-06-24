#!/usr/bin/env python3
"""
DeliverHQ 开发前门禁检查
AI 在进入开发阶段前必须运行此脚本，验证文档完备性。
任何 BLOCKED 项必须提醒人类工程师，不得进入开发。
"""


import argparse
import os
import sys
from pathlib import Path

from baseline_comparison import capture_baseline
from cr_state import GateStatus, ensure_state, update_gate_from_result
from permissiongate import check_permission_gate
from runtime_support import configure_console

# 定位 DeliverHQ 根目录（脚本在 DeliverHQ/scripts/ 下）
DELIVERHQ_ROOT = Path(__file__).parent.parent
configure_console()


class Color:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'


VALID_LANES = {"fast", "standard", "high-risk"}


def check_file_exists(path, description):
    """检查文件是否存在"""
    if Path(path).exists():
        print(f"  {Color.GREEN}✓{Color.END} {description}: {path}")
        return True
    print(f"  {Color.RED}✗{Color.END} {description}: {path} (缺失)")
    return False


def check_no_placeholders(path, description):
    """检查文件中是否有未替换的占位符"""
    if not Path(path).exists():
        return False

    content = Path(path).read_text(encoding='utf-8')
    placeholders = ['{{', '}}', '[待确认]', '[TODO]']

    found = [placeholder for placeholder in placeholders if placeholder in content]
    if found:
        print(f"  {Color.RED}✗{Color.END} {description}: 包含占位符 {found}")
        return False

    print(f"  {Color.GREEN}✓{Color.END} {description}: 无占位符")
    return True


def check_high_risk_human_approval(cr_path):
    """检查 high-risk 是否已获得人工审批（fail-closed：必须有正面批准证据）。"""

    decisions_path = Path(cr_path) / "human-decisions.md"
    if not decisions_path.exists():
        return False, ["high-risk CR 缺少 human-decisions.md"]

    content = decisions_path.read_text(encoding='utf-8')
    blockers = []

    if '{{' in content or '[待确认]' in content or '[TODO]' in content:
        blockers.append("human-decisions.md 仍有未填充占位符")

    if 'pending' in content.lower():
        blockers.append("human-decisions.md 仍包含 pending 决策")

    # fail-closed：仅排除负面信号不够，必须有正面批准证据。
    # 接受两种证据：(a) 显式 Approved/批准 标记；(b) 决策表中至少一行真实数据（含决策人）。
    has_approved_marker = ('approved' in content.lower()
                           or '已批准' in content or '批准人' in content)
    has_decision_row = False
    for line in content.splitlines():
        s = line.strip()
        if not s.startswith('|') or '---' in s:
            continue
        cells = [c.strip() for c in s.strip('|').split('|')]
        # 排除表头（含"决策"/"#"等列名）与占位
        if len(cells) >= 4 and cells[0] and cells[0] not in ('#', '决策', '编号') \
                and '{{' not in s and cells[-1] and cells[-2]:
            has_decision_row = True
            break

    if not has_approved_marker and not has_decision_row:
        blockers.append("high-risk CR 缺少人工批准证据（需 Approved 标记或填写的决策记录行）")

    if blockers:
        return False, blockers

    return True, []


def check_cr_readiness(cr_path, lane='standard'):
    """检查 CR 是否可以进入开发阶段"""

    cr_path = Path(cr_path)
    state = ensure_state(cr_path, lane=lane)

    print(f"\n{Color.BLUE}=== 检查 CR: {cr_path} ==={Color.END}\n")
    print(f"  Lane: {state.lane}")

    blockers = []
    warnings = []

    # P0 检查项（阻断级）
    print(f"{Color.BLUE}[P0 阻断级检查]{Color.END}")

    # 1. acceptance-spec.md 存在
    spec_path = cr_path / "acceptance-spec.md"
    if not check_file_exists(spec_path, "验收规格"):
        blockers.append("缺少 acceptance-spec.md")
    elif not check_no_placeholders(spec_path, "验收规格完整性"):
        blockers.append("acceptance-spec.md 包含未解决的占位符")

    # 2. 检查是否有设计稿（如果是 UI 需求）
    design_dir = cr_path / "design"
    if design_dir.exists():
        has_lofi = (design_dir / "lo-fi-spec.md").exists()
        has_hifi = (design_dir / "hi-fi-spec.md").exists()

        if has_hifi:
            print(f"  {Color.GREEN}✓{Color.END} 设计稿: 高保真设计存在")
        elif has_lofi:
            print(f"  {Color.YELLOW}⚠{Color.END} 设计稿: 仅低保真（B 端可接受）")
            warnings.append("仅低保真设计，C 端需补充高保真")
        else:
            print(f"  {Color.RED}✗{Color.END} 设计稿: 缺失")
            blockers.append("有 design/ 目录但无设计稿")

    # 3. architecture-design.md 存在并已运行 ArchitectureGate
    architecture_path = cr_path / "architecture-design.md"
    if not check_file_exists(architecture_path, "架构设计"):
        blockers.append("缺少 architecture-design.md")
    elif not check_no_placeholders(architecture_path, "架构设计完整性"):
        blockers.append("architecture-design.md 包含未解决的占位符")

    architecture_evidence = cr_path / "evidence" / "architecture-result.json"
    if not check_file_exists(architecture_evidence, "ArchitectureGate 证据"):
        blockers.append("缺少 ArchitectureGate 证据，请先运行 architecturegate.py")
    else:
        try:
            import json
            evidence = json.loads(architecture_evidence.read_text(encoding='utf-8'))
            if evidence.get('result') not in ('pass', 'pass_with_warnings'):
                blockers.append("ArchitectureGate 未通过")
            elif evidence.get('warnings'):
                warnings.extend(evidence.get('warnings') or [])
        except Exception as exc:
            blockers.append(f"ArchitectureGate 证据无法解析: {exc}")

    # 4. context-summary.md 存在（如果已过 Spec 阶段）
    if (cr_path / "implementation-plan.md").exists():
        context_path = cr_path / "context-summary.md"
        if not check_file_exists(context_path, "上下文摘要"):
            blockers.append("已进入 Dev 阶段但缺少 context-summary.md")

    # 5. PermissionGate + high-risk 人工审批
    if state.lane in {'fast', 'standard', 'high-risk'}:
        print(f"\n{Color.BLUE}[PermissionGate]{Color.END}")
        permission_passed, permission_blockers = check_permission_gate(str(cr_path), lane=state.lane)
        if not permission_passed:
            blockers.extend(permission_blockers)

    if state.lane == 'high-risk':
        print(f"\n{Color.BLUE}[high-risk 强制检查]{Color.END}")
        approval_passed, approval_blockers = check_high_risk_human_approval(cr_path)
        if not approval_passed:
            print(f"  {Color.RED}✗{Color.END} 人工审批未完成")
            blockers.extend(approval_blockers)
        else:
            print(f"  {Color.GREEN}✓{Color.END} 人工审批已完成")

    # 5. 规则违反扫描
    if spec_path.exists():
        content = spec_path.read_text(encoding='utf-8')
        sensitive_keywords = ['密码', 'password', 'token', 'secret', '硬编码']
        for keyword in sensitive_keywords:
            if keyword in content.lower():
                print(f"  {Color.YELLOW}⚠{Color.END} 规则检查: 提及敏感信息 '{keyword}'，确保不硬编码")
                warnings.append(f"验收规格提及 '{keyword}'，注意规则 #7/#8")

    # P1 检查项（警告级）
    print(f"\n{Color.BLUE}[P1 警告级检查]{Color.END}")

    # 6. traceability.yml 存在（标准 / high-risk 建议必备）
    trace_path = cr_path / "traceability.yml"
    if not check_file_exists(trace_path, "可追溯性"):
        if state.lane in {'standard', 'high-risk'}:
            blockers.append("标准/高风险 CR 必须维护 traceability.yml")
        else:
            warnings.append("建议创建 traceability.yml")

    # 7. human-decisions.md 存在（如有模糊点）
    decisions_path = cr_path / "human-decisions.md"
    if spec_path.exists():
        content = spec_path.read_text(encoding='utf-8')
        if '模糊点' in content or '待确认' in content:
            if not decisions_path.exists():
                warnings.append("存在模糊点但缺少 human-decisions.md")

    # 汇总结果
    print(f"\n{Color.BLUE}=== 检查结果 ==={Color.END}")

    if warnings:
        print(f"{Color.YELLOW}⚠️  PASS WITH WARNINGS:{Color.END}")
        for i, warning in enumerate(warnings, 1):
            print(f"  {i}. {warning}")

    baseline_commands = []
    baseline_artifacts = []
    if state.lane in {'standard', 'high-risk'}:
        print(f"\n{Color.BLUE}[Baseline Before]{Color.END}")
        _, baseline_errors, baseline_commands = capture_baseline(cr_path, "before")
        baseline_artifacts.append("evidence/baseline-before.json")
        if baseline_errors:
            for item in baseline_errors:
                print(f"  {Color.RED}✗{Color.END} {item}")
            blockers.extend(baseline_errors)
        else:
            print(f"  {Color.GREEN}✓{Color.END} baseline-before 已生成")

    if blockers:
        print(f"{Color.RED}❌ BLOCKED - 以下问题阻断开发：{Color.END}")
        for i, blocker in enumerate(blockers, 1):
            print(f"  {i}. {blocker}")
        print(f"\n{Color.RED}⛔ AI 必须提醒人类工程师：文档不完备，不能进入开发阶段。{Color.END}")
        update_gate_from_result(
            cr_path,
            "pre_dev",
            False,
            blockers=blockers,
            state_after_pass="dev",
            current_phase="request",
            current_owner=state.current_owner,
            next_required_gate="pre_dev",
            requires_human=state.lane == 'high-risk',
            commands_run=["permissiongate.py", "pre_dev_gate.py", *baseline_commands],
            warnings=warnings,
            artifacts=baseline_artifacts,
            next_action="补齐阻断项后重新运行 PreDevGate",
        )
        return False

    if not blockers and not warnings:
        print(f"{Color.GREEN}✅ PASS - 文档完备，可以进入开发阶段。{Color.END}")
    else:
        print(f"{Color.GREEN}✅ PASS - 可以进入开发阶段。{Color.END}")

    update_gate_from_result(
        cr_path,
        "pre_dev",
        True,
        blockers=[],
        state_after_pass="dev",
        current_phase="dev",
        current_owner="dev-agent",
        next_required_gate="dev",
        requires_human=state.lane == 'high-risk',
        warnings=warnings,
        commands_run=["permissiongate.py", "pre_dev_gate.py", *baseline_commands],
        artifacts=baseline_artifacts,
        next_action="进入 ReviewGate / 开发执行阶段",
    )
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('cr_id', help='CR-ID')
    parser.add_argument('--lane', choices=sorted(VALID_LANES), help='覆盖 state.yml 的 lane')
    parser.add_argument('--suggest-lane', action='store_true',
                        help='按客观规模信号建议 lane（借 lane_advisor），不修改 state，仅打印参考')
    args = parser.parse_args()

    cr_path = DELIVERHQ_ROOT / "change-requests" / args.cr_id

    if not cr_path.exists():
        print(f"{Color.RED}错误: CR 目录不存在: {cr_path}{Color.END}")
        print(f"提示: 从 CR-TEMPLATE 复制开始新 CR")
        sys.exit(1)

    if args.suggest_lane:
        try:
            from lane_advisor import advise
            rec = advise(cr_path)
            if rec["decision"] == "split":
                print(f"{Color.YELLOW}⚠ 规模建议：{rec['reason']}{Color.END}")
            else:
                print(f"{Color.BLUE}建议 lane: {rec['lane']}（{rec['reason']}）{Color.END}")
            s = rec["signals"]
            print(f"  信号: changed_files={s['changed_files']}, ac_count={s['ac_count']}, "
                  f"sensitive={s['sensitive_domains'] or '无'}")
        except Exception as exc:
            print(f"{Color.YELLOW}⚠ lane 建议不可用: {exc}{Color.END}")

    state_lane = args.lane or ensure_state(cr_path).lane
    passed = check_cr_readiness(cr_path, lane=state_lane)

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
