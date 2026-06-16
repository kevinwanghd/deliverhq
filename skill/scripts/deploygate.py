#!/usr/bin/env python3
"""
DeployGate - 部署就绪性检查
检查部署前是否满足所有必要条件
"""

import sys
import os
from pathlib import Path
import re

from cr_state import update_gate_from_result
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

def check_deploygate(cr_path):
    """DeployGate 检查"""
    print(f"{Color.BLUE}=== DeployGate 检查 ==={Color.END}\n")

    checklist_path = Path(cr_path) / "deployment-checklist.md"

    if not checklist_path.exists():
        print(f"{Color.RED}✗ deployment-checklist.md 不存在{Color.END}")
        update_gate_from_result(
            Path(cr_path),
            'deploy',
            False,
            blockers=['缺少 deployment-checklist.md，Deploy Agent 未执行'],
            state_after_pass='deploy_ready',
            current_phase='deploy',
            current_owner='deploy-agent',
            next_required_gate='deploy',
            next_action='生成 deployment-checklist.md 后重新运行 DeployGate',
        )
        return False, ["缺少 deployment-checklist.md，Deploy Agent 未执行"]

    content = checklist_path.read_text(encoding='utf-8')
    blockers = []
    warnings = []

    # 严格模式开关
    strict_mode = os.environ.get('DELIVERHQ_STRICT_MODE', '0') == '1'

    # 检查 1: 模板变量未替换
    print(f"{Color.BLUE}[文档完整性]{Color.END}")
    template_vars = re.findall(r'\{\{[^}]+\}\}', content)
    if template_vars:
        print(f"{Color.RED}✗ 包含未替换模板变量: {list(set(template_vars))[:5]}{Color.END}")
        blockers.append("包含模板变量，未填充实际内容")
    else:
        print(f"{Color.GREEN}✓ 无模板变量{Color.END}")

    # 检查 2: QualityGate 是否通过
    print(f"\n{Color.BLUE}[前置 Gate]{Color.END}")
    qualitygate_report = Path(cr_path) / "qualitygate-report.md"
    if qualitygate_report.exists():
        qg_content = qualitygate_report.read_text(encoding='utf-8')
        if 'PASS' in qg_content:
            print(f"{Color.GREEN}✓ QualityGate 已通过{Color.END}")
        else:
            print(f"{Color.RED}✗ QualityGate 未通过{Color.END}")
            blockers.append("QualityGate 未通过")
    else:
        print(f"{Color.YELLOW}⚠ 未找到 qualitygate-report.md{Color.END}")
        warnings.append("建议运行 QualityGate")

    # 检查 3: 数据库变更 + Rollback Plan
    print(f"\n{Color.BLUE}[数据库变更]{Color.END}")
    has_db_change = re.search(r'是否涉及数据库变更.*?是', content, re.IGNORECASE)
    has_rollback = '回滚计划' in content and '回滚步骤' in content

    if has_db_change:
        if not has_rollback or '{{' in content[content.find('回滚步骤'):content.find('回滚步骤')+200]:
            print(f"{Color.RED}✗ 涉及数据库变更但缺少完整 rollback plan{Color.END}")
            blockers.append("数据库变更缺少 rollback plan")
        else:
            print(f"{Color.GREEN}✓ 数据库变更有 rollback plan{Color.END}")
    else:
        print(f"{Color.GREEN}✓ 无数据库变更{Color.END}")

    # 检查 4: 回滚计划完整性
    print(f"\n{Color.BLUE}[回滚计划]{Color.END}")
    required_rollback_sections = ['回滚触发条件', '回滚步骤', '回滚验证']
    missing_rollback = []
    for section in required_rollback_sections:
        if section not in content:
            missing_rollback.append(section)

    if missing_rollback:
        msg = f"回滚计划缺少: {', '.join(missing_rollback)}"
        if strict_mode:
            print(f"{Color.RED}✗ {msg}{Color.END}")
            blockers.append(msg)
        else:
            print(f"{Color.YELLOW}⚠ {msg}（严格模式下会阻断）{Color.END}")
            warnings.append(msg)
    else:
        print(f"{Color.GREEN}✓ 回滚计划完整{Color.END}")

    # 检查 5: 部署后验证
    print(f"\n{Color.BLUE}[部署后验证]{Color.END}")
    has_smoke_test = '冒烟测试' in content
    has_monitoring = '监控指标' in content

    if not has_smoke_test:
        print(f"{Color.YELLOW}⚠ 缺少冒烟测试{Color.END}")
        warnings.append("建议补充冒烟测试")
    else:
        print(f"{Color.GREEN}✓ 包含冒烟测试{Color.END}")

    if not has_monitoring:
        print(f"{Color.YELLOW}⚠ 缺少监控指标{Color.END}")
        warnings.append("建议补充监控指标")
    else:
        print(f"{Color.GREEN}✓ 包含监控指标{Color.END}")

    # 检查 6: Human Approval（高风险场景）
    print(f"\n{Color.BLUE}[Human Approval]{Color.END}")
    is_production = re.search(r'部署环境.*?生产', content, re.IGNORECASE)
    has_approval = re.search(r'审批意见.*?Approved', content, re.IGNORECASE)

    if is_production:
        if not has_approval:
            msg = "生产环境部署缺少 Human Approval"
            if strict_mode:
                print(f"{Color.RED}✗ {msg}{Color.END}")
                blockers.append(msg)
            else:
                print(f"{Color.YELLOW}⚠ {msg}（严格模式下会阻断）{Color.END}")
                warnings.append(msg)
        else:
            print(f"{Color.GREEN}✓ 生产部署已获 Human Approval{Color.END}")
    else:
        print(f"{Color.GREEN}✓ 非生产环境，无需强制 Human Approval{Color.END}")

    # 检查 7: 高风险变更检查
    print(f"\n{Color.BLUE}[风险评估]{Color.END}")
    has_risk_assessment = '高风险项' in content or '风险评估' in content

    if has_risk_assessment:
        print(f"{Color.GREEN}✓ 包含风险评估{Color.END}")
    else:
        print(f"{Color.YELLOW}⚠ 缺少风险评估{Color.END}")
        warnings.append("建议补充风险评估")

    # 汇总结果
    print(f"\n{Color.BLUE}=== DeployGate 结果 ==={Color.END}")
    if blockers:
        print(f"{Color.RED}❌ BLOCKED{Color.END}")
        for i, b in enumerate(blockers, 1):
            print(f"  {i}. {b}")
        print(f"\n{Color.RED}⛔ 修复后才能进入部署阶段{Color.END}")
        print(f"\n{Color.YELLOW}提示：设置 DELIVERHQ_STRICT_MODE=1 启用严格模式{Color.END}")
        update_gate_from_result(
            Path(cr_path),
            'deploy',
            False,
            blockers=blockers,
            state_after_pass='deploy_ready',
            current_phase='deploy',
            current_owner='deploy-agent',
            next_required_gate='deploy',
        )
        return False, blockers

    if warnings:
        print(f"{Color.YELLOW}⚠️  PASS WITH WARNINGS{Color.END}")
        for i, w in enumerate(warnings, 1):
            print(f"  {i}. {w}")

    print(f"{Color.GREEN}✅ PASS - 部署就绪检查通过{Color.END}")
    update_gate_from_result(
        Path(cr_path),
        'deploy',
        True,
        blockers=[],
        state_after_pass='deploy_ready',
        current_phase='deploy',
        current_owner='deploy-agent',
        next_required_gate='writeback',
    )
    return True, []

def main():
    if len(sys.argv) < 2:
        print("用法: python deploygate.py <path/to/CR-XXX>")
        sys.exit(1)

    cr_path = sys.argv[1]
    passed, blockers = check_deploygate(cr_path)

    sys.exit(0 if passed else 1)

if __name__ == "__main__":
    main()
