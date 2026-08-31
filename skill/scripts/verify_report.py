#!/usr/bin/env python3
"""
verify_report.py —— verify 动词分层报告生成器

D8 交付物：读取 CR evidence/ 目录下 verify 四步各自的结果 JSON，
汇总为分层报告，写入 evidence/verify-layer-report.json，并打印可读摘要。

verify 动词四步对应 Layer：
  Layer 1 — goal_contract        → evidence/goal-contract-result.json
  Layer 2 — review              → evidence/review-result.json（reviewgate.py 写）
  Layer 3 — quality             → evidence/quality-result.json
  Layer 4 — anti_gaming         → evidence/anti_gaming-result.json
  Layer 5 — HK-V (needs_human) → evidence/human-checkpoint-HK-V.json

每层输出：
  status  | PASS / FAIL / SKIPPED / ERROR
  blockers（层阻断项列表）
  duration_s（若可计算）
  next_action

整体结论：
  all_pass    — 四步全部 PASS
  partial     — 部分通过
  blocked     — 某层 BLOCK
  needs_human — 触发 HK-V

跨平台 / Python 3.10+。

用法：
  python verify_report.py <CR目录> [--json]   # 机器可读输出
  python verify_report.py <CR目录>             # 人类可读摘要
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# 步骤名 → evidence JSON 文件名（与 orchestrator_core SkillConfig outputs 一致）
STEP_FILES = {
    "goal_contract": "goal-contract-result.json",
    "review": "review-result.json",
    "quality": "quality-result.json",
    "anti_gaming": "anti_gaming-result.json",
    "adversarial_review": "anti_gaming-result.json",  # 同层 alias
}

LAYER_NAMES = {
    "goal_contract": "Layer 1 — 目标契约",
    "review": "Layer 2 — Evidence 验证",
    "quality": "Layer 3 — 质量检查",
    "anti_gaming": "Layer 4 — 对抗式审查",
    "adversarial_review": "Layer 4 — 对抗式审查",
}

COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_END = "\033[0m"


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_step_result(cr_dir: Path, step: str) -> dict:
    """读取单个步骤的 evidence JSON。"""
    fname = STEP_FILES.get(step)
    if not fname:
        return {"status": "SKIPPED", "reason": f"未知的步骤: {step}"}

    # 多路径查找（适配 DeliverHQ/ 和项目根目录结构）
    candidates = [
        cr_dir / "evidence" / fname,
        cr_dir / fname,
    ]
    for p in candidates:
        data = _load_json(p)
        if data is not None:
            return _normalize(data, step)
    return {"status": "SKIPPED", "reason": f"无 evidence 文件: {fname}"}


def _normalize(data: dict, step: str) -> dict:
    """统一 normalize 各 gate JSON 为标准化层结果结构。"""
    # 检测 result 字段值
    raw_result = data.get("result", "")
    if raw_result in ("pass", "PASS"):
        status = "PASS"
    elif raw_result in ("pass_with_warnings", "PASS_WITH_WARNINGS"):
        status = "PASS_WITH_WARNINGS"
    elif raw_result in ("blocked", "BLOCKED", "FAIL", "FAIL"):
        status = "FAIL"
    elif raw_result == "error":
        status = "ERROR"
    else:
        status = "UNKNOWN"

    blockers = data.get("blocking_items", []) or []
    if not isinstance(blockers, list):
        blockers = [str(blockers)]

    return {
        "status": status,
        "blockers": blockers,
        "warnings": data.get("warnings", []) or [],
        "commands": data.get("commands_run", []) or [],
        "artifacts": data.get("artifacts", []) or [],
        "next_action": data.get("next_action", ""),
        "timestamp": data.get("timestamp", ""),
        "metadata": data.get("metadata", {}),
        # adversarial_review 特有字段
        "verdict": data.get("metadata", {}).get("verdict"),
        "blocking_findings": data.get("metadata", {}).get("blocking_findings", 0),
        "changed_files": data.get("metadata", {}).get("changed_files", []),
    }


def _build_layer_report(cr_dir: Path) -> dict:
    """构建分层报告。"""
    layers = {}
    all_pass = True
    any_blocked = False
    all_blockers = []

    for step in STEP_FILES:
        result = _load_step_result(cr_dir, step)
        layers[step] = {
            "layer_name": LAYER_NAMES.get(step, step),
            "status": result["status"],
            "blockers": result["blockers"],
            "warnings": result["warnings"],
            "commands": result["commands"],
            "artifacts": result["artifacts"],
            "next_action": result["next_action"],
            "timestamp": result["timestamp"],
        }
        if result["status"] not in ("PASS", "PASS_WITH_WARNINGS", "SKIPPED"):
            all_pass = False
        if result["status"] in ("FAIL", "ERROR"):
            any_blocked = True
            all_blockers.extend(result["blockers"])

    # 整体结论
    if not any_blocked:
        verdict = "all_pass"
    elif all_pass:
        verdict = "partial"
    else:
        verdict = "blocked"

    # 判断是否触发 HK-V
    needs_human = (
        verdict == "blocked"
        or any(
            result["status"] in ("FAIL", "ERROR")
            for result in (layers[s] for s in STEP_FILES)
        )
    )

    report = {
        "schema_version": "deliverhq-verify-layer-report/v1",
        "generated_at": datetime.now().isoformat(),
        "cr_id": cr_dir.name,
        "verdict": verdict,
        "needs_human": needs_human,
        "layers": layers,
        "all_blockers": all_blockers,
        "summary": _summarize(layers, verdict, needs_human),
    }

    return report


def _summarize(layers: dict, verdict: str, needs_human: bool) -> str:
    """生成一行人类可读摘要。"""
    passed = sum(1 for l in layers.values() if l["status"] == "PASS")
    failed = sum(1 for l in layers.values() if l["status"] in ("FAIL", "ERROR"))
    skipped = sum(1 for l in layers.values() if l["status"] == "SKIPPED")

    if verdict == "all_pass":
        return f"✅ verify 全部通过（{passed}/{len(layers)} 层 PASS）"
    elif verdict == "partial":
        return f"⚠️  verify 部分通过（{passed} PASS / {failed} FAIL / {skipped} SKIP）"
    else:
        return f"❌ verify 失败（{failed}/{len(layers)} 层 FAIL） — {'触发 HK-V' if needs_human else ''}"


def _print_report(report: dict, verbose: bool = True) -> None:
    """打印人类可读的分层报告。"""
    print(f"\n{COLOR_BLUE}{'='*60}{COLOR_END}")
    print(f"{COLOR_BLUE}  verify 动词分层报告 — {report['cr_id']}{COLOR_END}")
    print(f"{COLOR_BLUE}{'='*60}{COLOR_END}\n")

    # 整体结论
    verdict_map = {
        "all_pass": f"{COLOR_GREEN}✅ ALL PASS{COLOR_END}",
        "partial": f"{COLOR_YELLOW}⚠️  PARTIAL PASS{COLOR_END}",
        "blocked": f"{COLOR_RED}❌ BLOCKED{COLOR_END}",
    }
    print(f"整体结论：{verdict_map.get(report['verdict'], report['verdict'])}")
    print(f"摘要：{report['summary']}")
    if report.get("needs_human"):
        print(f"{COLOR_RED}⛔ 触发 Layer 5 — HK-V 需人工核查{COLOR_END}")
    print()

    # 逐层
    for step, layer in report["layers"].items():
        color = (
            COLOR_GREEN if layer["status"] == "PASS"
            else COLOR_YELLOW if layer["status"] in ("PASS_WITH_WARNINGS", "SKIPPED")
            else COLOR_RED
        )
        icon = (
            "✓" if layer["status"] == "PASS"
            else "~" if layer["status"] in ("PASS_WITH_WARNINGS", "SKIPPED")
            else "✗"
        )
        print(f"{color}  {icon} {layer['layer_name']} [{layer['status']}]{COLOR_END}")

        if layer["blockers"]:
            for b in layer["blockers"]:
                print(f"     {COLOR_RED}  BLOCK: {b}{COLOR_END}")
        if layer["warnings"] and verbose:
            for w in layer["warnings"][:3]:
                print(f"     {COLOR_YELLOW}  WARN:  {w}{COLOR_END}")
        if layer["next_action"]:
            print(f"     → {layer['next_action']}")
        print()

    # 阻断项汇总
    if report["all_blockers"]:
        print(f"{COLOR_RED}── 全部阻断项（去重）──{COLOR_END}")
        seen = set()
        for b in report["all_blockers"]:
            if b not in seen:
                seen.add(b)
                print(f"  - {b}")
        print()

    print(f"{COLOR_BLUE}{'='*60}{COLOR_END}\n")


def main():
    parser = argparse.ArgumentParser(
        description="verify 动词分层报告生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("cr_dir", help="CR 目录路径")
    parser.add_argument("--json", action="store_true", help="仅输出机器可读 JSON")
    parser.add_argument("--quiet", action="store_true", help="静默（只写文件，不打印摘要）")
    args = parser.parse_args()

    cr_dir = Path(args.cr_dir)
    if not cr_dir.exists():
        print(f"❌ CR 目录不存在: {cr_dir}")
        sys.exit(1)

    report = _build_layer_report(cr_dir)

    # 写 evidence JSON
    output_path = cr_dir / "evidence" / "verify-layer-report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif not args.quiet:
        _print_report(report)

    # 退出码：all_pass=0，blocked/needs_human=1
    if report["verdict"] == "all_pass":
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
