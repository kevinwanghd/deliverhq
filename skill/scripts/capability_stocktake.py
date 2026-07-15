#!/usr/bin/env python3
"""Require a reuse stocktake before adding a new DeliverHQ capability."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import sys
from typing import Sequence


SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from deliverhq.capabilities import Capability, load_registry  # noqa: E402


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]+", text or "")
        if len(token) >= 2
    }


def find_overlaps(intent: str, proposed_name: str, records: Sequence[Capability]) -> list[dict]:
    """Find registry entries that look reusable for the proposed capability."""
    wanted = _tokens(f"{intent} {proposed_name}")
    overlaps = []
    for record in records:
        existing = _tokens(f"{record.name} {record.description} {record.script}")
        shared = sorted(wanted.intersection(existing))
        if proposed_name.strip().lower() == record.name.strip().lower() or len(shared) >= 2:
            overlaps.append(
                {
                    "id": record.id,
                    "name": record.name,
                    "script": record.script,
                    "shared_terms": shared,
                }
            )
    return overlaps


def check_stocktake(
    intent: str,
    proposed_name: str,
    why_existing_insufficient: str = "",
    extend_existing: str = "",
    records: Sequence[Capability] | None = None,
) -> dict:
    """Return blockers/warnings for a proposed capability addition."""
    capabilities = list(records) if records is not None else load_registry()
    blockers = []
    warnings = []
    intent = (intent or "").strip()
    proposed_name = (proposed_name or "").strip()
    why_existing_insufficient = (why_existing_insufficient or "").strip()
    extend_existing = (extend_existing or "").strip()

    if not intent:
        blockers.append("intent is required")
    if not proposed_name:
        blockers.append("proposed_name is required")
    if not why_existing_insufficient and not extend_existing:
        blockers.append("record why existing capabilities cannot be reused, or name the existing capability to extend")

    overlaps = find_overlaps(intent, proposed_name, capabilities)
    duplicate = next(
        (item for item in overlaps if item["name"].strip().lower() == proposed_name.lower()),
        None,
    )
    if duplicate:
        blockers.append(f"proposed capability duplicates existing {duplicate['id']} {duplicate['name']}")
    elif overlaps and not why_existing_insufficient and not extend_existing:
        blockers.append("possible reusable capability found; document reuse/extension decision")
    elif overlaps and not extend_existing:
        warnings.append("possible reusable capability found; prefer extending before adding")

    return {
        "blockers": blockers,
        "warnings": warnings,
        "overlaps": overlaps,
        "count": len(capabilities),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="DeliverHQ capability stocktake")
    parser.add_argument("--intent", required=True, help="What the new capability should do")
    parser.add_argument("--proposed-name", required=True, help="Proposed capability name")
    parser.add_argument(
        "--why-existing-insufficient",
        default="",
        help="Why existing capabilities cannot be reused",
    )
    parser.add_argument(
        "--extend-existing",
        default="",
        help="Existing capability id/name that will be extended instead",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = check_stocktake(
        intent=args.intent,
        proposed_name=args.proposed_name,
        why_existing_insufficient=args.why_existing_insufficient,
        extend_existing=args.extend_existing,
    )
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Blockers: {len(report['blockers'])}")
        print(f"Warnings: {len(report['warnings'])}")
        print(f"Overlaps: {len(report['overlaps'])}")
    return 1 if report["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
