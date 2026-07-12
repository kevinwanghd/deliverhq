#!/usr/bin/env python3
"""Pure routing, sizing, and cost decisions for the DeliverHQ orchestrator."""

import os
from pathlib import Path
import re
import sys
from typing import Dict, List, Optional

import yaml

VERBS: Dict[str, List[str]] = {
    "spec": ["grill", "spec", "drift_check"],
    "design": ["design", "architecture"],
    "dev": ["pre_dev", "context", "dev"],
    "verify": ["goal_contract", "review", "quality", "anti_gaming"],
    "archive": ["writeback", "rule_maturity"],
}

VERB_DESCRIPTIONS = {
    "spec": "需求澄清拷问（条件）+ 验收规格完备性 + PRD↔CR 对账",
    "design": "UI/设计产物 + 架构设计人工确认",
    "dev": "开发前综合门禁 + 上下文纪律 + 开发交接（停在写码前）",
    "verify": "目标契约双轨校验 + 对抗式审查 + 真实构建/测试 + 反钻空子（信证据不信声明）",
    "archive": "知识沉淀完整性 + 规则成熟度更新",
}

VERB_GATE_STEPS = {
    "spec": "specgate",
    "design": "designgate",
    "architecture": "architecturegate",
    "pre_dev": "pre_dev_gate",
    "review": "reviewgate",
    "quality": "qualitygate",
    "writeback": "writeback_gate",
}

VERB_NON_GATE_STEPS = {
    "context", "dev", "drift_check", "anti_gaming", "rule_maturity",
    "goal_contract", "grill",
}
VERB_CONDITIONAL_STEPS = {"goal_contract": "goal-contract.yml", "grill": "request.md"}
VERB_STANDALONE_GATES = {"permissiongate", "deploygate", "structuregate", "reverse_spec_gate"}
VERB_NO_ARG_STEPS = {"rule_maturity"}

TOKEN_ESTIMATES = {
    "spec": {"no_cache": (30000, 50000), "with_cache": (5000, 10000), "description": "grill + specgate + drift_check"},
    "design": {"no_cache": (40000, 70000), "with_cache": (8000, 15000), "description": "designgate + architecturegate"},
    "dev": {"no_cache": (50000, 100000), "with_cache": (10000, 25000), "description": "pre_dev_gate + dev_phase"},
    "verify": {"no_cache": (80000, 150000), "with_cache": (15000, 35000), "description": "reviewgate + qualitygate + writeback"},
    "archive": {"no_cache": (20000, 40000), "with_cache": (5000, 10000), "description": "writeback + rule_maturity"},
}
SONNET_PRICING = {"input": 3.0 / 1_000_000, "output": 15.0 / 1_000_000}


def estimate_cost(verb: str, has_cache: bool = False) -> Optional[dict]:
    if verb not in TOKEN_ESTIMATES:
        return None
    estimate = TOKEN_ESTIMATES[verb]
    minimum, maximum = estimate["with_cache" if has_cache else "no_cache"]
    return {
        "min_tokens": minimum,
        "max_tokens": maximum,
        "min_cost": minimum * SONNET_PRICING["input"] + minimum * 0.2 * SONNET_PRICING["output"],
        "max_cost": maximum * SONNET_PRICING["input"] + maximum * 0.2 * SONNET_PRICING["output"],
        "description": estimate["description"],
    }


def _normalize_gate_name(name: str) -> str:
    normalized = (name or "").lower().replace("_", "")
    return normalized[:-4] if normalized.endswith("gate") else normalized


def has_gate_cache(cr_path: Path, verb: str) -> bool:
    state_path = cr_path / "state.yml"
    if not state_path.exists():
        return False
    try:
        data = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
        gates = data.get("gates", {})
        if not isinstance(gates, dict):
            return False
        modules = [VERB_GATE_STEPS.get(step) for step in VERBS.get(verb, [])]
        return any(
            _normalize_gate_name(key) == _normalize_gate_name(module)
            and isinstance(info, dict)
            and bool(info.get("fingerprint"))
            for module in modules if module
            for key, info in gates.items()
        )
    except Exception:
        return False


def print_cost_estimate(verb: str, cr_path: Path) -> None:
    cached = has_gate_cache(cr_path, verb)
    estimate = estimate_cost(verb, cached)
    if not estimate:
        return
    print(f"\n📊 预估 token 消耗（{estimate['description']}）：")
    print(f"  - 范围：{estimate['min_tokens']/1000:.1f}k - {estimate['max_tokens']/1000:.1f}k tokens")
    print(f"  - 费用：${estimate['min_cost']:.2f} - ${estimate['max_cost']:.2f} (Sonnet 定价)")
    if cached:
        uncached = estimate_cost(verb, False)
        saved = (uncached["min_cost"] + uncached["max_cost"]) / 2 - (estimate["min_cost"] + estimate["max_cost"]) / 2
        print(f"  - ✅ Gate 缓存已启用，预计节省 ${saved:.2f}")
    print("")


def _load_lane(cr_path: Path) -> Optional[str]:
    state_path = cr_path / "state.yml"
    if not state_path.exists():
        return None
    try:
        data = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
        lane = data.get("lane")
        return lane if isinstance(lane, str) else None
    except Exception:
        return None


def should_use_fast_lane(cr_path: Path) -> bool:
    if "--fast" in sys.argv:
        return True
    if _load_lane(cr_path) == "fast":
        return True
    request_file = cr_path / "request.md"
    if not request_file.exists():
        return False
    content = request_file.read_text(encoding="utf-8")
    if "[fast-lane]" in content or "<!-- fast-lane -->" in content:
        return True
    risky = ["架构", "数据库", "schema", "api", "接口", "migration", "重构", "database", "architecture"]
    if len(content) < 200 and not any(keyword in content.lower() for keyword in risky):
        print("🚀 检测到小改动（<200字 + 无高风险关键词）")
        print("   建议走快速通道（dev 链精简 context，保留 pre_dev + dev）")
        if not sys.stdin.isatty() or os.environ.get("DELIVERHQ_NON_INTERACTIVE") == "1":
            print("   （非交互环境，默认走完整链；如需快速通道加 --fast）")
            return False
        return input("   使用快速通道？[Y/n]: ").strip().lower() in ("", "y", "yes")
    return False


def analyze_cr_size(cr_path: str) -> dict:
    cr_dir = Path(cr_path)
    if not cr_dir.exists():
        return {"error": f"CR 目录不存在: {cr_path}"}
    total_tokens = 0
    file_count = 0
    for file_path in cr_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix in {".md", ".yml", ".yaml", ".json"}:
            try:
                total_tokens += len(file_path.read_text(encoding="utf-8", errors="ignore")) // 4
                file_count += 1
            except Exception:
                pass
    criteria_count = 0
    spec_file = cr_dir / "acceptance-spec.md"
    if spec_file.exists():
        content = spec_file.read_text(encoding="utf-8", errors="ignore")
        criteria_count = len(re.findall(r"^\s*[-\*] \[[ x]\]|^\s*\d+\.\s", content, re.MULTILINE))
    reasons = []
    if criteria_count > 10:
        reasons.append(f"验收条件 {criteria_count} 条（建议上限 10 条）")
    if total_tokens > 5000:
        reasons.append(f"CR 总量约 {total_tokens:,} tokens（建议上限 5,000）")
    return {
        "total_tokens": total_tokens,
        "criteria_count": criteria_count,
        "file_count": file_count,
        "should_decompose": bool(reasons),
        "reasons": reasons,
    }


def decompose_cr(cr_path: str) -> None:
    print("\n🔍 CR 规模分析\n")
    result = analyze_cr_size(cr_path)
    if "error" in result:
        print(f"❌ {result['error']}")
        return
    cr_name = Path(cr_path).name
    print(f"CR: {cr_name}")
    print(f"  文件数:        {result['file_count']}")
    print(f"  Token 估算:    {result['total_tokens']:,}")
    print(f"  验收条件数:    {result['criteria_count']}\n")
    if result["should_decompose"]:
        print("⚠️  建议拆解（触发以下阈值）：")
        for reason in result["reasons"]:
            print(f"  - {reason}")
        print(f"\n使用 scripts/create_sub_cr.py {cr_name} 创建经人工审阅的子 CR。")
    else:
        print("✅ CR 规模合理，无需拆解")
        print("  （验收条件 ≤ 10 且 tokens ≤ 5,000）")


ROUTES = {
    "new_feature": {"name": "新需求/功能", "flow": ["grill (如有 request.md)", "spec", "design", "dev", "verify", "archive"], "entry": "spec", "description": "从想法到交付的主流程。有代码库从 grill→spec 开始；无 request.md 直接写 spec。", "mode": "standard", "keywords": ["新功能", "需求", "feature", "idea", "想法", "加个"]},
    "bug_fix": {"name": "Bug 修复", "flow": ["spec (简化)", "dev", "verify"], "entry": "spec", "description": "小改动可简化 spec（只写验收条件），跳过 design，直奔 dev→verify。", "mode": "fast-lane", "keywords": ["bug", "修复", "fix", "错误", "问题"]},
    "refactor": {"name": "重构/优化", "flow": ["spec (重构目标)", "design (架构)", "dev", "verify"], "entry": "spec", "description": "重构需要明确目标（spec）和架构约束（design），然后 dev→verify。", "mode": "standard", "keywords": ["重构", "refactor", "优化", "optimize", "改进"]},
    "legacy": {"name": "遗留代码/逆向工程", "flow": ["reverse-spec (模式2)", "design", "verify"], "entry": "reverse-spec", "description": "已有代码无文档：先逆向生成 spec（模式2：analyze→spec），再补 design 和测试。", "mode": "reverse", "keywords": ["遗留", "legacy", "无文档", "逆向", "已有代码"]},
    "cr_exists": {"name": "已有 spec/设计，继续开发", "flow": ["design (如未完成)", "dev", "verify", "archive"], "entry": "design", "description": "CR 已有 acceptance-spec，从 design 或 dev 继续（用 resume 自动判断）。", "mode": "standard", "keywords": ["继续", "resume", "已有spec", "接着做"]},
}


def route_situation(situation: Optional[str] = None) -> None:
    print("\n🧭 DeliverHQ 动词路由器\n")
    if not situation or situation.lower() in ("interactive", "?", "help"):
        print("回答几个问题，帮你找到合适的动词流:\n")
        print("1. 你的场景是?\n   a) 我有一个新想法/需求要实现\n   b) 我要修一个 bug\n   c) 我要重构/优化现有代码\n   d) 我有遗留代码，没文档，想补齐\n   e) 我已经有 CR 和 spec，想继续开发\n")
        key = {"a": "new_feature", "b": "bug_fix", "c": "refactor", "d": "legacy", "e": "cr_exists"}.get(input("选择 (a/b/c/d/e): ").strip().lower())
        if not key:
            print("\n⚠ 未识别的选择，显示所有路径供参考。\n")
            for route in ROUTES.values():
                print(f"** {route['name']} **\n   流程: {' → '.join(route['flow'])}\n   入口: {route['entry']}\n   说明: {route['description']}\n")
            return
    else:
        value = situation.lower()
        key = next((name for name, route in ROUTES.items() if any(word in value for word in route["keywords"])), None)
        if not key:
            print("📍 识别场景: 不确定/需要引导\n\n   推荐流程: 参考交互式 route\n   入口动词: (见帮助)\n")
            return
    route = ROUTES[key]
    print(f"📍 识别场景: {route['name']}\n")
    print(f"   推荐流程: {' → '.join(route['flow'])}")
    print(f"   入口动词: {route['entry']}")
    print(f"   模式: {route['mode']}\n\n   {route['description']}\n")
    print("💡 下一步命令:")
    if route["entry"] == "spec":
        print("   python scripts/skill_orchestrator.py verb spec <CR目录>")
    elif route["entry"] == "design":
        print("   python scripts/skill_orchestrator.py verb design <CR目录>")
    else:
        print("   python scripts/reverse_spec_gate.py mode2 <目标目录>")
    print()
