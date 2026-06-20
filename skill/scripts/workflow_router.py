#!/usr/bin/env python3
"""
Lightweight DeliverHQ workflow router.

规则优先，不接 LLM。输入用户请求，输出可解释 JSON。
定位：低噪主动提醒，不做复杂多 Agent 编排。
"""


import argparse
import json
import re
import sys
from typing import Dict


def _is_plan_only_no_modification(lower: str) -> bool:
    plan_only_signals = [
        "先给方案", "只给建议", "只做分析", "只给优化建议", "不要实施",
        "plan only", "recommendation only", "recommend only",
    ]
    no_modification_signals = [
        "不要修改文件", "不要改文件", "不要修改代码", "不要改代码", "不要创建 cr", "不要实施",
        "不要启动 deliverhq", "不走 cr", "只读", "do not modify", "don't modify",
        "do not create a cr", "don't create a cr", "no file changes",
    ]
    return any(signal in lower for signal in plan_only_signals) and any(
        signal in lower for signal in no_modification_signals
    )


def route_request(text: str) -> Dict:
    raw = text.strip()
    lower = raw.lower()

    if _is_plan_only_no_modification(lower):
        return {
            "deliverhq_required": False,
            "lane": "fast",
            "workflow_type": "linear",
            "adversarial_required": False,
            "permissiongate_required": False,
            "reason": "仅请求方案/建议且明确不修改文件或不创建 CR，避免过度治理",
            "next_action": "handle_directly",
        }

    reject_keywords = [
        "错别字", "拼写错误", "解释", "查看", "总结", "临时脚本", "commit message",
        "不要启动 deliverhq", "不用deliverhq", "不走 cr", "快速修一下",
    ]
    if any(keyword in lower for keyword in reject_keywords):
        return {
            "deliverhq_required": False,
            "lane": "fast",
            "workflow_type": "linear",
            "adversarial_required": False,
            "permissiongate_required": False,
            "reason": "轻量/只读/用户明确跳过，避免过度治理",
            "next_action": "handle_directly",
        }

    high_risk = any(kw in lower for kw in ["支付", "权限", "安全", "数据迁移", "生产", "核心", "回滚", "配置文件"])
    protected = any(kw in lower for kw in ["protected", "受保护", "权限", "配置文件", "secret", "token", "生产配置"])
    batch = any(kw in lower for kw in ["批量", "200 个", "issue", "分类", "去重", "优先级"])
    generate = any(kw in lower for kw in ["方案", "选型", "架构", "优缺点", "推荐一个", "3 个", "三种"])
    loop = any(kw in lower for kw in ["一直失败", "循环", "直到通过", "反复失败"])
    fanout = any(kw in lower for kw in ["多文件", "大模块", "迁移", "80 个文件", "所有 api", "多个假设"])
    done = any(kw in lower for kw in ["做完了", "修完了", "提交", "准备提交"])
    writing_code = any(kw in lower for kw in ["开发", "写代码", "实现", "修改", "重构", "修 bug", "修复"])

    deliverhq_required = high_risk or protected or batch or generate or loop or fanout or done or writing_code or "cr-" in lower or "deliverhq" in lower

    if batch:
        workflow = "classify-and-act"
    elif loop:
        workflow = "loop-until-done"
    elif generate:
        workflow = "generate-and-filter"
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


def main():
    parser = argparse.ArgumentParser(description="Route a user request to a low-noise DeliverHQ workflow decision")
    parser.add_argument("prompt", nargs="*", help="user request text")
    args = parser.parse_args()

    text = " ".join(args.prompt).strip()
    if not text:
        text = sys.stdin.read().strip()
    if not text:
        print(json.dumps({"error": "empty prompt"}, ensure_ascii=False, indent=2))
        sys.exit(1)

    print(json.dumps(route_request(text), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
