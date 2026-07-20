#!/usr/bin/env python3
"""Validate the agent-friendly DeliverHQ PRD contract.

The PRD remains the product-intent source. This validator only checks that
the document exposes the stable fields required to derive agent artifacts; it
does not decide whether the product decision itself is correct.
"""

import argparse
import json
import re
import sys
from pathlib import Path


STATUSES = {"draft", "reviewed", "approved", "frozen", "superseded"}
FEATURE_STATUSES = {"draft", "pending_confirmation", "confirmed", "deferred", "deprecated"}
REQUIRED_FEATURE_FIELDS = (
    "REQ ID",
    "状态",
    "优先级",
    "负责人",
    "目标平台",
    "来源证据",
    "依赖",
    "范围内",
    "范围外",
    "验收条件索引",
    "业务不变式",
    "研发交付映射",
    "待确认问题",
)


def _metadata(text: str) -> dict:
    match = re.search(r"```yaml\s*(.*?)\s*```", text, re.S)
    if not match:
        return {}
    values = {}
    for line in match.group(1).splitlines():
        item = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*?)\s*$", line)
        if item:
            values[item.group(1)] = item.group(2).strip().strip('"\'')
    return values


def _features(text: str):
    matches = list(re.finditer(r"^##\s+\[(PRD-[A-Z0-9][A-Z0-9-]*)\]\s+.+$", text, re.M))
    result = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result.append((match.group(1), text[match.start():end]))
    return result


TEMPLATE_ANCHORS = {"PRD-SAMPLE", "PRD-XXX", "PRD-YYY"}
TEMPLATE_MARKERS = ("示例锚点", "(同上结构)")


def is_template_feature(anchor: str, section: str) -> bool:
    """Identify the illustrative sections shipped in the PRD template.

    Only the anchors and prose markers the template actually ships count as
    template stubs. A leftover ``{{...}}`` no longer classifies a whole section
    as a template — that would silently drop a real, fully-filled feature that
    merely quotes template syntax (e.g. ``{{ user }}``) in its prose. Unresolved
    braces are surfaced by ``validate`` as explicit placeholders instead.
    """
    if anchor in TEMPLATE_ANCHORS:
        return True
    return any(marker in section for marker in TEMPLATE_MARKERS)


def validate(path: Path, strict: bool = False):
    text = path.read_text(encoding="utf-8")
    blockers, warnings = [], []
    meta = _metadata(text)

    if meta.get("schema") != "deliverhq-prd":
        blockers.append("缺少 schema: deliverhq-prd 元数据")
    if meta.get("schema_version") != "2":
        blockers.append("schema_version 必须为 2")
    if meta.get("status") not in STATUSES:
        blockers.append("元数据 status 必须为 draft/reviewed/approved/frozen/superseded")

    features = _features(text)
    real_features = [item for item in features if not is_template_feature(*item)]
    if not real_features:
        blockers.append("至少需要一个已填写的真实功能锚点")

    anchor_ids = [item[0] for item in real_features]
    if len(anchor_ids) != len(set(anchor_ids)):
        blockers.append("功能锚点 ID 重复")

    req_ids = []
    for anchor, section in real_features:
        if is_template_feature(anchor, section):
            continue
        for field in REQUIRED_FEATURE_FIELDS:
            if field not in section:
                blockers.append(f"{anchor} 缺少字段: {field}")
        if not re.search(r"\bAC-[A-Z0-9][A-Z0-9-]*\s*:", section):
            blockers.append(f"{anchor} 至少需要一条验收条件")
        if not re.search(r"\|\s*QA-[A-Z0-9][A-Z0-9-]*\s*\|", section):
            blockers.append(f"{anchor} 必须包含 QA 验收任务")
        req_match = re.search(r"\*\*REQ ID\*\*:\s*(REQ-[A-Z0-9][A-Z0-9-]*)", section)
        if not req_match or req_match.group(1) in {"REQ-XXX", "REQ-YYY"}:
            blockers.append(f"{anchor} 缺少合法 REQ ID")
        else:
            req_ids.append(req_match.group(1))
        status_match = re.search(r"\*\*状态\*\*:\s*([^\n]+)", section)
        if status_match:
            status = status_match.group(1).strip().split("|")[0].strip()
            if status not in FEATURE_STATUSES:
                blockers.append(f"{anchor} 状态无效: {status}")

    if len(req_ids) != len(set(req_ids)):
        blockers.append("REQ ID 重复")

    placeholder_tokens = ["待确认", "TO" + "DO", "NEEDS CLARIFICATION"]
    unresolved = re.findall(r"\[(?:" + "|".join(placeholder_tokens) + r")[^\]]*\]", text, re.I)
    # Unfilled {{...}} template variables inside real (non-template) features are
    # unresolved placeholders too — surface them explicitly instead of silently
    # treating the whole feature as a template stub.
    brace_placeholders = 0
    for anchor, section in real_features:
        brace_placeholders += len(re.findall(r"\{\{[^}]*\}\}", section))
    total_unresolved = len(unresolved) + brace_placeholders
    if total_unresolved:
        message = f"存在 {total_unresolved} 个显式未确认占位符"
        if meta.get("status") in {"approved", "frozen"} or strict:
            blockers.append(message)
        else:
            warnings.append(message)

    result = {
        "path": str(path),
        "ok": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "feature_count": len(real_features),
        "req_ids": req_ids,
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Validate an agent-friendly DeliverHQ PRD")
    parser.add_argument("prd", help="path to PRD.md")
    parser.add_argument("--strict", action="store_true", help="treat unresolved placeholders as blockers")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    result = validate(Path(args.prd), strict=args.strict)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("=== DeliverHQ PRD Validate ===")
        print(f"功能锚点: {result['feature_count']}")
        for item in result["blockers"]:
            print(f"✗ {item}")
        for item in result["warnings"]:
            print(f"⚠ {item}")
        print("✅ PASS" if result["ok"] else "❌ BLOCKED")
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
