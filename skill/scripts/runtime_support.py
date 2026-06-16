#!/usr/bin/env python3
"""
DeliverHQ runtime helpers.

Shared helpers for:
1. Console encoding compatibility on Windows.
2. CR runtime directory creation.
3. Gate evidence JSON persistence.
"""


import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from failure_attribution import classify_failure


RUNTIME_DIRS = ("workspace", "outputs", "evidence", "artifacts")


def configure_console() -> None:
    """Best-effort stdout/stderr reconfiguration for Windows terminals."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def ensure_cr_runtime_dirs(cr_path: Path) -> List[Path]:
    """Ensure the standard CR runtime directories exist."""
    created: List[Path] = []
    for name in RUNTIME_DIRS:
        directory = cr_path / name
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created.append(directory)
    return created


def write_gate_evidence(
    cr_path: Path,
    gate_name: str,
    result: str,
    blocking_items: Optional[Iterable[str]] = None,
    warnings: Optional[Iterable[str]] = None,
    commands_run: Optional[Iterable[str]] = None,
    artifacts: Optional[Iterable[str]] = None,
    next_action: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Path:
    """Write a machine-readable gate result into evidence/<gate>-result.json."""
    ensure_cr_runtime_dirs(cr_path)
    output_path = cr_path / "evidence" / f"{gate_name}-result.json"

    blockers = list(blocking_items or [])
    attributions = []
    if result == "blocked" or blockers:
        for blocker in blockers:
            attribution = classify_failure(gate_name, blocker)
            attributions.append({
                "gate": attribution.gate_name,
                "failure_type": attribution.failure_type.value,
                "repair_action": attribution.repair_action.value,
                "evidence": attribution.evidence,
                "next_step": attribution.next_step,
                "is_blocker": attribution.is_blocker,
            })

    payload = {
        "gate_name": gate_name,
        "result": result,
        "timestamp": datetime.now().isoformat(),
        "blocking_items": blockers,
        "warnings": list(warnings or []),
        "commands_run": list(commands_run or []),
        "artifacts": list(artifacts or []),
        "next_action": next_action or "",
        "failure_attribution": attributions,
        "metadata": metadata or {},
    }

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path
