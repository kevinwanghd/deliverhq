#!/usr/bin/env python3
"""
Shared routing rules for DeliverHQ.

The router is intentionally rule-based and low-noise.  Keep this module small:
it decides whether DeliverHQ should be recommended and which workflow pattern is
appropriate; it does not create CRs or run gates.
"""

from typing import Dict


PLAN_ONLY_SIGNALS = [
    "先给方案", "只给建议", "只做分析", "只给优化建议", "不要实施",
    "plan only", "recommendation only", "recommend only",
]
NO_MODIFICATION_SIGNALS = [
    "不要修改文件", "不要改文件", "不要修改代码", "不要改代码", "不要创建 cr", "不要实施",
    "不要启动 deliverhq", "不走 cr", "只读", "do not modify", "don't modify",
    "do not create a cr", "don't create a cr", "no file changes",
]
ASK_ONLY_PATTERNS = ["是什么", "介绍一下", "检查什么"]
REJECT_KEYWORDS = [
    "错别字", "拼写错误", "解释", "查看", "总结", "临时脚本", "commit message",
    "不要启动 deliverhq", "不用deliverhq", "不走 cr", "快速修一下",
]
BOUNDARY_KEYWORDS = ["修一个 bug", "重构这个模块", "优化性能"]
HIGH_RISK_KEYWORDS = ["支付", "权限", "安全", "数据迁移", "生产", "核心", "回滚", "配置文件"]
PROTECTED_KEYWORDS = ["protected", "受保护", "权限", "配置文件", "secret", "token", "生产配置"]
BATCH_KEYWORDS = ["批量", "200 个", "issue", "分类", "去重", "优先级"]
GENERATE_KEYWORDS = ["方案", "选型", "架构", "优缺点", "推荐一个", "3 个", "三种"]
LOOP_KEYWORDS = ["一直失败", "循环", "直到通过", "反复失败"]
FANOUT_KEYWORDS = ["多文件", "大模块", "迁移", "80 个文件", "所有 api", "多个假设", "转化率"]
DONE_KEYWORDS = ["做完了", "修完了", "提交", "准备提交"]
WRITING_CODE_KEYWORDS = ["开发", "写代码", "实现", "修改", "重构", "修 bug", "修复"]
TRIGGER_KEYWORDS = [
    "deliverhq", "deliver-hq", "文档门禁", "扫描", "技术债", "代码健康", "代码质量报告", "创建", "新建需求", "推进 cr",
    "验收规格写好了", "qualitygate", "specgate", "能不能开发", "不要没文档", "开发", "修改", "bug 修完",
    "迁移", "重构", "支付", "数据迁移", "架构", "方案", "测试", "issue", "批量",
    "多文件", "所有 api", "性能", "线上", "转化率", "用户提交", "文档注释",
]


def has_any(text: str, keywords) -> bool:
    return any(keyword in text for keyword in keywords)


def is_plan_only_no_modification(text: str) -> bool:
    return has_any(text, PLAN_ONLY_SIGNALS) and has_any(text, NO_MODIFICATION_SIGNALS)


def route_request(text: str) -> Dict:
    raw = text.strip()
    lower = raw.lower()

    if is_plan_only_no_modification(lower):
        return {
            "deliverhq_required": False,
            "lane": "fast",
            "workflow_type": "linear",
            "adversarial_required": False,
            "permissiongate_required": False,
            "reason": "仅请求方案/建议且明确不修改文件或不创建 CR，避免过度治理",
            "next_action": "handle_directly",
        }

    if has_any(lower, ASK_ONLY_PATTERNS):
        return {
            "deliverhq_required": False,
            "lane": "fast",
            "workflow_type": "linear",
            "adversarial_required": False,
            "permissiongate_required": False,
            "reason": "纯信息查询，不启动 DeliverHQ",
            "next_action": "handle_directly",
        }

    if has_any(lower, REJECT_KEYWORDS):
        return {
            "deliverhq_required": False,
            "lane": "fast",
            "workflow_type": "linear",
            "adversarial_required": False,
            "permissiongate_required": False,
            "reason": "轻量/只读/用户明确跳过，避免过度治理",
            "next_action": "handle_directly",
        }

    high_risk = has_any(lower, HIGH_RISK_KEYWORDS)
    protected = has_any(lower, PROTECTED_KEYWORDS)
    batch = has_any(lower, BATCH_KEYWORDS)
    generate = has_any(lower, GENERATE_KEYWORDS)
    loop = has_any(lower, LOOP_KEYWORDS)
    fanout = has_any(lower, FANOUT_KEYWORDS)
    done = has_any(lower, DONE_KEYWORDS)
    writing_code = has_any(lower, WRITING_CODE_KEYWORDS)

    if has_any(lower, BOUNDARY_KEYWORDS) and not (high_risk or protected or batch or loop or fanout or done):
        return {
            "deliverhq_required": False,
            "lane": "fast",
            "workflow_type": "linear",
            "adversarial_required": False,
            "permissiongate_required": False,
            "reason": "边界场景，应先询问是否启用 DeliverHQ，避免过度治理",
            "next_action": "ask_first",
        }

    deliverhq_required = high_risk or protected or batch or generate or loop or fanout or done or writing_code or "cr-" in lower or has_any(lower, TRIGGER_KEYWORDS)

    if batch:
        workflow = "classify-and-act"
    elif loop or "文档注释" in lower:
        workflow = "loop-until-done"
    elif generate:
        workflow = "generate-and-filter"
    elif high_risk:
        workflow = "linear"
    elif fanout:
        workflow = "fan-out-and-synthesize"
    else:
        workflow = "linear"

    lane = "high-risk" if high_risk or protected else "standard" if deliverhq_required else "fast"
    adversarial = high_risk or generate or fanout or done
    next_action = "run_review_quality_gates" if done else "check_cr_and_pre_dev_gate" if writing_code else "create_cr" if deliverhq_required else "handle_directly"

    reasons = []
    if high_risk:
        reasons.append("命中高风险业务/数据/生产关键词")
    if protected:
        reasons.append("可能触及受保护路径或配置")
    if batch:
        reasons.append("批量问题适合 classify-and-act")
    if generate:
        reasons.append("架构/方案类任务适合 generate-and-filter")
    if loop:
        reasons.append("反复失败适合 loop-until-done，但必须有硬停止条件")
    if fanout:
        reasons.append("多文件/大模块适合 fan-out-and-synthesize")
    if done:
        reasons.append("完成/提交前应提示 ReviewGate / QualityGate")
    if writing_code:
        reasons.append("写代码前应检查 CR / acceptance-spec / PreDevGate")

    return {
        "deliverhq_required": bool(deliverhq_required),
        "lane": lane,
        "workflow_type": workflow,
        "adversarial_required": bool(adversarial),
        "permissiongate_required": bool(protected or high_risk),
        "reason": "；".join(reasons) or "未命中 DeliverHQ 触发条件",
        "next_action": next_action,
    }
