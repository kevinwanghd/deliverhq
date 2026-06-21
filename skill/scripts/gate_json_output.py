#!/usr/bin/env python3
"""
Gate JSON Output - canonical minimal Gate evidence schema.

This module owns the machine-readable schema used by
runtime_support.write_gate_evidence().  It deliberately stays small: no
Dashboard, no viewer, no per-Gate rewrites.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Optional
import json


GATE_SCHEMA_VERSION = "deliverhq-gate-result/v1"
VALID_GATE_RESULTS = {"pass", "pass_with_warnings", "blocked", "error"}
REQUIRED_GATE_RESULT_FIELDS = (
    "schema_version",
    "gate_name",
    "result",
    "timestamp",
    "blocking_items",
    "warnings",
    "commands_run",
    "artifacts",
    "next_action",
    "failure_attribution",
    "metadata",
)


class GateResult(Enum):
    """Gate result enum."""

    PASS = "pass"
    PASS_WITH_WARNINGS = "pass_with_warnings"
    BLOCKED = "blocked"
    ERROR = "error"


class Severity(Enum):
    """Issue severity enum kept for backward-compatible formatting helpers."""

    P0 = "p0"
    P1 = "p1"
    P2 = "p2"
    INFO = "info"


@dataclass
class BlockingItem:
    """Backward-compatible human formatting item."""

    message: str
    severity: str
    file: Optional[str] = None
    line: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass
class GateOutput:
    """Backward-compatible human formatting object."""

    gate_name: str
    result: str
    cr_id: str
    timestamp: str
    blocking_items: List[BlockingItem]
    warnings: List[str]
    next_action: str
    metadata: Optional[dict] = None


def _as_list(values: Optional[Iterable]) -> List:
    return list(values or [])


def build_gate_result_payload(
    gate_name: str,
    result: str,
    timestamp: str,
    blocking_items: Optional[Iterable[str]] = None,
    warnings: Optional[Iterable[str]] = None,
    commands_run: Optional[Iterable[str]] = None,
    artifacts: Optional[Iterable[str]] = None,
    next_action: Optional[str] = None,
    failure_attribution: Optional[Iterable[Dict]] = None,
    metadata: Optional[Dict] = None,
) -> Dict:
    """Build a canonical minimal Gate evidence payload.

    Compatibility note: blocking_items intentionally remains list[str].  Older
    evidence consumers and fixtures already expect strings, not BlockingItem
    objects.
    """

    return {
        "schema_version": GATE_SCHEMA_VERSION,
        "gate_name": gate_name,
        "result": result,
        "timestamp": timestamp,
        "blocking_items": _as_list(blocking_items),
        "warnings": _as_list(warnings),
        "commands_run": _as_list(commands_run),
        "artifacts": _as_list(artifacts),
        "next_action": next_action or "",
        "failure_attribution": _as_list(failure_attribution),
        "metadata": metadata or {},
    }


def validate_gate_result_payload(payload: Dict) -> List[str]:
    """Return validation errors for a Gate evidence payload."""

    errors: List[str] = []
    for field in REQUIRED_GATE_RESULT_FIELDS:
        if field not in payload:
            errors.append("missing field: %s" % field)

    if payload.get("schema_version") != GATE_SCHEMA_VERSION:
        errors.append("invalid schema_version: %s" % payload.get("schema_version"))

    if payload.get("result") not in VALID_GATE_RESULTS:
        errors.append("invalid result: %s" % payload.get("result"))

    list_fields = [
        "blocking_items",
        "warnings",
        "commands_run",
        "artifacts",
        "failure_attribution",
    ]
    for field in list_fields:
        if field in payload and not isinstance(payload[field], list):
            errors.append("%s must be a list" % field)

    if "metadata" in payload and not isinstance(payload["metadata"], dict):
        errors.append("metadata must be a dict")

    if "gate_name" in payload and not isinstance(payload["gate_name"], str):
        errors.append("gate_name must be a string")

    if "timestamp" in payload and not isinstance(payload["timestamp"], str):
        errors.append("timestamp must be a string")

    if "next_action" in payload and not isinstance(payload["next_action"], str):
        errors.append("next_action must be a string")

    return errors


def save_gate_result_json(payload: Dict, output_path) -> None:
    """Validate and save a canonical Gate evidence payload."""

    errors = validate_gate_result_payload(payload)
    if errors:
        raise ValueError("invalid gate result payload: " + "; ".join(errors))

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_gate_result_json(json_path) -> Dict:
    """Load a canonical Gate evidence payload as a dict."""

    return json.loads(Path(json_path).read_text(encoding="utf-8"))


def format_gate_output(output: GateOutput) -> str:
    """Format legacy GateOutput as human-readable text."""

    lines = []
    lines.append("=== %s 检查结果 ===" % output.gate_name)
    lines.append("CR: %s" % output.cr_id)
    lines.append("时间: %s" % output.timestamp)
    lines.append("")

    if output.result == "pass":
        lines.append("✅ PASS")
    elif output.result == "pass_with_warnings":
        lines.append("⚠️  PASS WITH WARNINGS")
    elif output.result == "blocked":
        lines.append("❌ BLOCKED")
    else:
        lines.append("🔥 ERROR")

    lines.append("")

    if output.blocking_items:
        lines.append("阻塞项:")
        for item in output.blocking_items:
            icon = "🚫" if item.severity == "p0" else "⚠️" if item.severity == "p1" else "💡"
            lines.append("  %s [%s] %s" % (icon, item.severity.upper(), item.message))
            if item.file:
                location = item.file
                if item.line:
                    location += ":%s" % item.line
                lines.append("     位置: %s" % location)
            if item.suggestion:
                lines.append("     建议: %s" % item.suggestion)
        lines.append("")

    if output.warnings:
        lines.append("警告:")
        for warning in output.warnings:
            lines.append("  ⚠️  %s" % warning)
        lines.append("")

    lines.append("下一步: %s" % output.next_action)
    return "\n".join(lines)


def save_gate_output_json(output: GateOutput, output_path: str) -> None:
    """Save the legacy GateOutput JSON shape without data loss."""

    data = {
        "gate_name": output.gate_name,
        "result": output.result,
        "cr_id": output.cr_id,
        "timestamp": output.timestamp,
        "blocking_items": [
            {
                "message": item.message,
                "severity": item.severity,
                "file": item.file,
                "line": item.line,
                "suggestion": item.suggestion,
            }
            for item in output.blocking_items
        ],
        "warnings": output.warnings,
        "next_action": output.next_action,
        "metadata": output.metadata or {},
    }
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_gate_output_json(json_path: str) -> GateOutput:
    """Load legacy GateOutput JSON, with canonical payload compatibility."""

    payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
    raw_items = payload.get("blocking_items", [])
    blocking_items: List[BlockingItem] = []
    for item in raw_items:
        if isinstance(item, dict):
            blocking_items.append(BlockingItem(**item))
        else:
            blocking_items.append(BlockingItem(message=str(item), severity="p0"))

    return GateOutput(
        gate_name=payload["gate_name"],
        result=payload["result"],
        cr_id=payload.get("cr_id", payload.get("metadata", {}).get("cr_id", "")),
        timestamp=payload["timestamp"],
        blocking_items=blocking_items,
        warnings=payload["warnings"],
        next_action=payload["next_action"],
        metadata=payload.get("metadata"),
    )


if __name__ == "__main__":
    from datetime import datetime

    payload = build_gate_result_payload(
        gate_name="SpecGate",
        result="blocked",
        timestamp=datetime.now().isoformat(),
        blocking_items=["包含 3 处 [待确认] 或 [TODO] 未解决"],
        warnings=["包含模糊词但无量化指标: 优化"],
        commands_run=["specgate.py"],
        artifacts=["acceptance-spec.md"],
        next_action="修复 P0 阻塞项后重新运行 SpecGate",
        metadata={"cr_id": "CR-001"},
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
