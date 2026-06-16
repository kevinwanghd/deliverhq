#!/usr/bin/env python3
"""
失败归因系统 - Gate 失败类型分类和修复建议

将 Gate 失败从"简单 BLOCKED"升级为"结构化归因 + 修复建议"
"""

from enum import Enum
from typing import List, Dict, Optional
from dataclasses import dataclass


class FailureType(Enum):
    """失败类型枚举"""
    # 文档缺失
    SPEC_MISSING = "spec_missing"                    # 规格文档缺失
    DESIGN_MISSING = "design_missing"                # 设计文档缺失
    TEST_PLAN_MISSING = "test_plan_missing"          # 测试计划缺失

    # 内容不完整
    AMBIGUITY_UNRESOLVED = "ambiguity_unresolved"    # 待确认问题未解决
    TEMPLATE_VAR_UNRESOLVED = "template_var_unresolved"  # 模板变量未替换
    SECTION_INCOMPLETE = "section_incomplete"        # 章节不完整

    # Gate 问题
    GATE_FALSE_POSITIVE = "gate_false_positive"      # Gate 误报（应该通过但被阻断）
    GATE_FALSE_NEGATIVE = "gate_false_negative"      # Gate 漏报（应该阻断但通过了）
    GATE_SCRIPT_ERROR = "gate_script_error"          # Gate 脚本执行错误

    # 执行错误
    AGENT_EXECUTION_ERROR = "agent_execution_error"  # Agent 执行错误
    BUILD_FAILURE = "build_failure"                  # 构建失败
    TEST_FAILURE = "test_failure"                    # 测试失败

    # 权限和边界
    PERMISSION_BOUNDARY_UNCLEAR = "permission_boundary_unclear"  # 权限边界不明
    PROTECTED_PATH_VIOLATED = "protected_path_violated"          # 违反保护路径

    # 流程问题
    WORKFLOW_MISROUTED = "workflow_misrouted"        # Workflow 选择错误
    DEPENDENCY_MISSING = "dependency_missing"        # 依赖缺失

    # 模板和工具
    TEMPLATE_CONTAMINATION = "template_contamination"  # 模板污染
    TOOL_CONTRACT_MISMATCH = "tool_contract_mismatch"  # 工具契约不匹配

    # 人工决策
    HUMAN_DECISION_REQUIRED = "human_decision_required"  # 需要人工决策
    OUT_OF_SCOPE = "out_of_scope"                    # 超出范围


class RepairAction(Enum):
    """修复动作枚举"""
    ASK_HUMAN = "ask_human"                          # 询问用户
    PATCH_SKILL = "patch_skill"                      # 修补 Skill 定义
    PATCH_GATE_SCRIPT = "patch_gate_script"          # 修补 Gate 脚本
    UPDATE_TEMPLATE = "update_template"              # 更新模板
    UPDATE_EVAL_CASE = "update_eval_case"            # 更新评估用例
    RERUN_SAME_GATE = "rerun_same_gate"             # 重新运行同一 Gate
    ABORT_WORKFLOW = "abort_workflow"                # 中止 Workflow
    FILL_DOCUMENT = "fill_document"                  # 补充文档
    RESOLVE_AMBIGUITY = "resolve_ambiguity"          # 解决模糊性
    FIX_CODE = "fix_code"                            # 修复代码
    FIX_TEST = "fix_test"                            # 修复测试
    ADJUST_PERMISSION = "adjust_permission"          # 调整权限


@dataclass
class FailureAttribution:
    """失败归因结构"""
    gate_name: str                                   # Gate 名称
    failure_type: FailureType                        # 失败类型
    repair_action: RepairAction                      # 修复动作
    evidence: List[str]                              # 证据列表
    next_step: str                                   # 下一步建议
    is_blocker: bool = True                          # 是否阻断
    metadata: Optional[Dict] = None                  # 额外元数据


# 失败类型到修复动作的映射
FAILURE_TYPE_TO_REPAIR = {
    FailureType.SPEC_MISSING: RepairAction.FILL_DOCUMENT,
    FailureType.DESIGN_MISSING: RepairAction.FILL_DOCUMENT,
    FailureType.TEST_PLAN_MISSING: RepairAction.FILL_DOCUMENT,

    FailureType.AMBIGUITY_UNRESOLVED: RepairAction.RESOLVE_AMBIGUITY,
    FailureType.TEMPLATE_VAR_UNRESOLVED: RepairAction.FILL_DOCUMENT,
    FailureType.SECTION_INCOMPLETE: RepairAction.FILL_DOCUMENT,

    FailureType.GATE_FALSE_POSITIVE: RepairAction.PATCH_GATE_SCRIPT,
    FailureType.GATE_FALSE_NEGATIVE: RepairAction.PATCH_GATE_SCRIPT,
    FailureType.GATE_SCRIPT_ERROR: RepairAction.PATCH_GATE_SCRIPT,

    FailureType.AGENT_EXECUTION_ERROR: RepairAction.FIX_CODE,
    FailureType.BUILD_FAILURE: RepairAction.FIX_CODE,
    FailureType.TEST_FAILURE: RepairAction.FIX_TEST,

    FailureType.PERMISSION_BOUNDARY_UNCLEAR: RepairAction.ASK_HUMAN,
    FailureType.PROTECTED_PATH_VIOLATED: RepairAction.ADJUST_PERMISSION,

    FailureType.WORKFLOW_MISROUTED: RepairAction.PATCH_SKILL,
    FailureType.DEPENDENCY_MISSING: RepairAction.FIX_CODE,

    FailureType.TEMPLATE_CONTAMINATION: RepairAction.UPDATE_TEMPLATE,
    FailureType.TOOL_CONTRACT_MISMATCH: RepairAction.PATCH_SKILL,

    FailureType.HUMAN_DECISION_REQUIRED: RepairAction.ASK_HUMAN,
    FailureType.OUT_OF_SCOPE: RepairAction.ABORT_WORKFLOW,
}


def classify_failure(gate_name: str, blocker_msg: str, context: Optional[Dict] = None) -> FailureAttribution:
    """
    根据 Gate 名称和阻断信息自动分类失败类型

    Args:
        gate_name: Gate 名称（如 "SpecGate", "QualityGate"）
        blocker_msg: 阻断信息
        context: 额外上下文

    Returns:
        FailureAttribution 对象
    """
    # 关键词匹配规则
    if "缺少" in blocker_msg or "不存在" in blocker_msg:
        if "acceptance-spec" in blocker_msg:
            failure_type = FailureType.SPEC_MISSING
        elif "design" in blocker_msg:
            failure_type = FailureType.DESIGN_MISSING
        elif "test" in blocker_msg:
            failure_type = FailureType.TEST_PLAN_MISSING
        elif "章节" in blocker_msg:
            failure_type = FailureType.SECTION_INCOMPLETE
        else:
            failure_type = FailureType.DEPENDENCY_MISSING

    elif "[待确认]" in blocker_msg or "TODO" in blocker_msg or "Open Questions" in blocker_msg:
        failure_type = FailureType.AMBIGUITY_UNRESOLVED

    elif "模板变量" in blocker_msg or "{{" in blocker_msg:
        failure_type = FailureType.TEMPLATE_VAR_UNRESOLVED

    elif "测试" in blocker_msg and ("失败" in blocker_msg or "未通过" in blocker_msg):
        failure_type = FailureType.TEST_FAILURE

    elif "构建" in blocker_msg and "失败" in blocker_msg:
        failure_type = FailureType.BUILD_FAILURE

    elif "权限" in blocker_msg or "protected_path" in blocker_msg:
        failure_type = FailureType.PROTECTED_PATH_VIOLATED

    elif "污染" in blocker_msg:
        failure_type = FailureType.TEMPLATE_CONTAMINATION

    else:
        # 默认：需要人工决策
        failure_type = FailureType.HUMAN_DECISION_REQUIRED

    # 获取推荐修复动作
    repair_action = FAILURE_TYPE_TO_REPAIR.get(failure_type, RepairAction.ASK_HUMAN)

    # 生成下一步建议
    next_step = generate_next_step(failure_type, repair_action, blocker_msg)

    return FailureAttribution(
        gate_name=gate_name,
        failure_type=failure_type,
        repair_action=repair_action,
        evidence=[blocker_msg],
        next_step=next_step,
        is_blocker=True,
        metadata=context
    )


def generate_next_step(failure_type: FailureType, repair_action: RepairAction, blocker_msg: str) -> str:
    """生成下一步建议"""
    suggestions = {
        FailureType.SPEC_MISSING: "创建 acceptance-spec.md，参考 change-requests/CR-TEMPLATE/",
        FailureType.AMBIGUITY_UNRESOLVED: "解决所有 [待确认] 占位符，将 P0 Open Questions 状态改为 resolved",
        FailureType.TEMPLATE_VAR_UNRESOLVED: "替换所有 {{变量}} 为实际值",
        FailureType.SECTION_INCOMPLETE: f"补充缺失章节：{blocker_msg}",
        FailureType.TEST_FAILURE: "修复失败的测试用例，确保 P0 测试 100% 通过",
        FailureType.BUILD_FAILURE: "修复构建错误，确保代码可编译",
        FailureType.GATE_FALSE_POSITIVE: "Gate 可能误报，检查 Gate 脚本逻辑或向用户确认",
        FailureType.HUMAN_DECISION_REQUIRED: "需要人工判断此问题如何修复",
    }

    return suggestions.get(failure_type, f"执行修复动作: {repair_action.value}")


def format_attribution_report(attribution: FailureAttribution) -> str:
    """格式化归因报告为人类可读文本"""
    report = f"""
╔════════════════════════════════════════════════════════╗
║  Gate 失败归因报告
╚════════════════════════════════════════════════════════╝

Gate: {attribution.gate_name}
状态: {'🚫 BLOCKED' if attribution.is_blocker else '⚠️  WARNING'}

失败类型: {attribution.failure_type.value}
修复动作: {attribution.repair_action.value}

证据:
""".strip()

    for evidence in attribution.evidence:
        report += f"\n  - {evidence}"

    report += f"\n\n下一步建议:\n  {attribution.next_step}"

    if attribution.metadata:
        report += f"\n\n额外信息:\n  {attribution.metadata}"

    return report


if __name__ == "__main__":
    # 测试用例
    test_cases = [
        ("SpecGate", "包含 3 处 [待确认] 或 [TODO] 未解决"),
        ("SpecGate", "缺少 SDD 结构: Data Spec, Interface Spec"),
        ("QualityGate", "P0 测试通过率 65%，未达标"),
        ("ReviewGate", "存在 3 个 P0 阻断问题"),
    ]

    for gate_name, blocker_msg in test_cases:
        attribution = classify_failure(gate_name, blocker_msg)
        print(format_attribution_report(attribution))
        print("\n" + "="*60 + "\n")
