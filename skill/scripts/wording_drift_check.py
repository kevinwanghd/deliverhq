#!/usr/bin/env python3
"""Detect wording drift between the capability registry and entry documents."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from deliverhq.capabilities import DEFAULT_MATRIX, RegistryError, assert_matrix_current  # noqa: E402


DEFAULT_DOCS = ("SKILL.md", "README.md", "AGENTS.md")
CAPABILITY_TABLE_RE = re.compile(
    r"(?ms)^\| .*(?:能力|capability).*\|\n^\|[-:| ]+\|\n(?:^\|.*\|\n?){3,}"
)


def check_wording_drift(root: Path | str = SKILL_ROOT, docs: tuple[str, ...] = DEFAULT_DOCS) -> dict:
    """Return blockers/warnings for duplicate or stale capability wording."""
    root_path = Path(root)
    blockers = []
    warnings = []

    try:
        matrix_path = root_path / DEFAULT_MATRIX.name
        assert_matrix_current(matrix_path)
    except RegistryError as exc:
        blockers.append(str(exc))

    for doc in docs:
        path = root_path / doc
        if not path.exists():
            warnings.append(f"{doc}: entry document missing")
            continue
        text = path.read_text(encoding="utf-8")
        if "CAPABILITY-MATRIX.md" not in text:
            blockers.append(f"{doc}: must reference CAPABILITY-MATRIX.md instead of duplicating status wording")
        if CAPABILITY_TABLE_RE.search(text):
            blockers.append(f"{doc}: duplicate capability table detected; use CAPABILITY-MATRIX.md")

    return {"blockers": blockers, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description="DeliverHQ wording drift check")
    parser.add_argument("--root", default=str(SKILL_ROOT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = check_wording_drift(args.root)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Blockers: {len(report['blockers'])}")
        print(f"Warnings: {len(report['warnings'])}")
    return 1 if report["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
