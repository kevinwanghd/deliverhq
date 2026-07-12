#!/usr/bin/env python3
"""
Free-flow style entrypoint for DeliverHQ.

This module is intentionally thin: it routes a natural-language request to a
governance lane and next action, but it does not create CRs or run gates. The
hard evidence chain remains in the existing gate scripts.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

from routing_rules import route_request
from runtime_support import configure_console


LANE_ALIASES = {
    "fast": "quick",
    "standard": "standard",
    "high-risk": "strict",
    "strict": "strict",
    "legacy": "legacy",
}

LEGACY_HINTS = (
    "legacy",
    "old project",
    "reverse",
    "scan existing",
    "code to spec",
    "lao xiang mu",
)

GATE_PLANS = {
    "quick": {
        "required": ["specgate", "qualitygate"],
        "skipped": ["designgate", "architecturegate", "permissiongate", "deploygate", "writebackgate"],
        "minutes": (5, 15), "tokens": (4000, 12000),
    },
    "standard": {
        "required": ["specgate", "architecturegate", "predevgate", "reviewgate", "qualitygate", "writebackgate"],
        "skipped": ["permissiongate"],
        "minutes": (20, 60), "tokens": (15000, 45000),
    },
    "strict": {
        "required": ["specgate", "designgate", "architecturegate", "predevgate", "permissiongate", "reviewgate", "qualitygate", "deploygate", "writebackgate"],
        "skipped": [],
        "minutes": (45, 120), "tokens": (35000, 90000),
    },
    "legacy": {
        "required": ["reversespecgate", "specgate", "architecturegate", "reviewgate", "qualitygate", "writebackgate"],
        "skipped": [],
        "minutes": (30, 90), "tokens": (25000, 70000),
    },
}


def route_execution_plan(lane, prompt):
    plan = GATE_PLANS.get(lane, GATE_PLANS["standard"])
    lower = prompt.lower()
    factors = [f"lane:{lane}"]
    multiplier = 1.0
    if any(term in lower for term in ("ui", "页面", "前端", "mobile", "design")):
        multiplier += 0.2
        factors.append("user-visible-ui:+20%")
    if any(term in lower for term in ("schema", "migration", "数据库", "迁移")):
        multiplier += 0.1
        factors.append("schema-change:+10%")
    minutes = [round(value * multiplier) for value in plan["minutes"]]
    tokens = [round(value * multiplier) for value in plan["tokens"]]
    return {
        "required_gates": list(plan["required"]),
        "skipped_gates": list(plan["skipped"]),
        "estimated_cost": {
            "time_minutes": minutes,
            "token_range": tokens,
            "confidence": "medium",
            "factors": factors,
            "note": "Heuristic range; calibrate with observed runs.",
        },
    }


def normalize_lane(decision, prompt):
    lower = prompt.lower()
    if any(hint in lower for hint in LEGACY_HINTS):
        return "legacy"
    return LANE_ALIASES.get(decision.get("lane"), decision.get("lane") or "quick")


def recommend_entry(decision, lane):
    next_action = decision.get("next_action")
    workflow = decision.get("workflow_type")

    if not decision.get("deliverhq_required"):
        if next_action == "ask_first":
            return {
                "entry": "ask_first",
                "command": None,
                "summary": "Clarify whether the user wants DeliverHQ governance before creating a CR.",
            }
        return {
            "entry": "quick_direct",
            "command": None,
            "summary": "Handle directly, then record only meaningful learning in DeliverHQ/notes if needed.",
        }

    if lane == "legacy":
        return {
            "entry": "deliver-legacy",
            "command": "python DeliverHQ/scripts/scan_legacy.py <project-root> --out DeliverHQ/change-requests/<CR>/reverse-spec-candidates.yml",
            "summary": "Scan existing code first, then convert confirmed findings into a normal CR.",
        }

    if next_action == "run_review_quality_gates":
        return {
            "entry": "deliver-verify",
            "command": "python DeliverHQ/scripts/skill_orchestrator.py verb verify DeliverHQ/change-requests/<CR>",
            "summary": "Run adversarial review and quality evidence before shipping.",
        }

    if workflow == "loop-until-done":
        return {
            "entry": "deliver-loop",
            "command": "python DeliverHQ/scripts/skill_orchestrator.py verb verify DeliverHQ/change-requests/<CR>",
            "summary": "Use bounded verify loops with retry limits; stop on repeated identical failure.",
        }

    if lane == "strict":
        return {
            "entry": "deliver-strict",
            "command": "python DeliverHQ/scripts/skill_orchestrator.py verb spec DeliverHQ/change-requests/<CR>",
            "summary": "Create a CR and keep the full SpecGate/ReviewGate/QualityGate evidence chain.",
        }

    return {
        "entry": "deliver-standard",
        "command": "python DeliverHQ/scripts/skill_orchestrator.py verb spec DeliverHQ/change-requests/<CR>",
        "summary": "Create a lightweight CR, then escalate only if gates or risk signals require it.",
    }


def build_decision(prompt):
    base = route_request(prompt)
    lane = normalize_lane(base, prompt)
    if lane == "legacy":
        base["deliverhq_required"] = True
        base["workflow_type"] = "legacy-scan"
        base["next_action"] = "scan_legacy"
        base["reason"] = "Legacy/code-to-spec request; scan existing code before trusting requirements."
    entry = recommend_entry(base, lane)
    execution = route_execution_plan(lane, prompt)
    governance_lane = {
        "quick": "fast", "standard": "standard",
        "strict": "high-risk", "legacy": "legacy",
    }[lane]
    return {
        "prompt": prompt,
        "lane": lane,
        "governance_lane": governance_lane,
        "confidence": execution["estimated_cost"]["confidence"],
        "deliverhq_required": bool(base.get("deliverhq_required")),
        "workflow_type": base.get("workflow_type"),
        "adversarial_required": bool(base.get("adversarial_required") or lane == "strict"),
        "permissiongate_required": bool(base.get("permissiongate_required")),
        "reason": base.get("reason"),
        "next_action": base.get("next_action"),
        "entry": entry["entry"],
        "recommended_command": entry["command"],
        "summary": entry["summary"],
        **execution,
        "read_first": [
            "DeliverHQ/attention.md",
            "DeliverHQ/REPO_MAP.md",
            "DeliverHQ/COMMANDS.yml",
        ],
        "knowledge_sink": {
            "quick_notes": "DeliverHQ/notes/",
            "inbox": "DeliverHQ/inbox/",
            "formal_writeback": "DeliverHQ/docs/",
        },
    }


def print_human(decision):
    print("DeliverHQ route")
    print(f"  lane: {decision['lane']}")
    print(f"  entry: {decision['entry']}")
    print(f"  workflow: {decision['workflow_type']}")
    print(f"  DeliverHQ required: {decision['deliverhq_required']}")
    print(f"  adversarial review: {decision['adversarial_required']}")
    print(f"  reason: {decision['reason']}")
    print(f"  next: {decision['summary']}")
    estimate = decision["estimated_cost"]
    print(f"  gates: {', '.join(decision['required_gates']) or 'none'}")
    print(f"  estimate: {estimate['time_minutes'][0]}-{estimate['time_minutes'][1]} min, "
          f"{estimate['token_range'][0]/1000:.0f}k-{estimate['token_range'][1]/1000:.0f}k tokens "
          f"({estimate['confidence']} confidence)")
    if decision["recommended_command"]:
        print(f"  command: {decision['recommended_command']}")


def print_lanes():
    print("DeliverHQ lanes")
    print("  quick    - direct small change; optional note only")
    print("  standard - lightweight CR with required evidence gates")
    print("  strict   - high-risk CR with full fail-closed gates")
    print("  legacy   - scan existing code before converting to CR")


def main():
    configure_console()
    parser = argparse.ArgumentParser(description="Route a request through DeliverHQ's light entrypoint")
    sub = parser.add_subparsers(dest="command")

    route = sub.add_parser("route", help="Route natural-language work to a lane and next entry")
    route.add_argument("prompt", nargs="*", help="request text; stdin is used when omitted")
    route.add_argument("--json", action="store_true", help="emit JSON")

    sub.add_parser("lanes", help="Describe available governance lanes")

    args = parser.parse_args()
    if args.command == "lanes":
        print_lanes()
        return
    if args.command != "route":
        parser.print_help()
        sys.exit(1)

    prompt = " ".join(args.prompt).strip() or sys.stdin.read().strip()
    if not prompt:
        print("empty prompt", file=sys.stderr)
        sys.exit(1)

    decision = build_decision(prompt)
    if args.json:
        print(json.dumps(decision, ensure_ascii=False, indent=2))
    else:
        print_human(decision)


if __name__ == "__main__":
    main()
