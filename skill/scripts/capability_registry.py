#!/usr/bin/env python3
"""Check, render, and migrate the DeliverHQ capability registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from deliverhq.capabilities import (  # noqa: E402
    Capability,
    DEFAULT_MATRIX,
    DEFAULT_REGISTRY,
    RegistryError,
    assert_matrix_current,
    load_registry,
    records_to_yaml,
    render_matrix_document,
)


VALID_STATUSES = {"stable", "experimental", "placeholder", "roadmap"}


def _parse_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def migrate_markdown_matrix(matrix_path: Path = DEFAULT_MATRIX) -> list[Capability]:
    rows: list[Capability] = []
    for line in matrix_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip().replace("\\|", "|") for cell in stripped.strip("|").split("|")]
        if len(cells) < 7:
            continue
        if cells[2] not in VALID_STATUSES:
            continue
        rows.append(
            Capability(
                id=f"cap-{len(rows) + 1:03d}",
                name=cells[0],
                script=cells[1],
                status=cells[2],
                integrated=cells[3],
                default_enabled=_parse_bool(cells[4]),
                allowed_in_pipeline=_parse_bool(cells[5]),
                description=cells[6],
            )
        )
    if not rows:
        raise RegistryError(f"no capability rows found in {matrix_path}")
    return rows


def command_check(args: argparse.Namespace) -> int:
    try:
        records = load_registry()
        matrix_current = True
        try:
            assert_matrix_current()
        except RegistryError:
            matrix_current = False
            if not args.json:
                raise
        if args.json:
            print(
                json.dumps(
                    {"count": len(records), "matrix_current": matrix_current},
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(f"OK: {len(records)} capabilities")
        return 0 if matrix_current else 1
    except RegistryError as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def command_render(args: argparse.Namespace) -> int:
    try:
        current = DEFAULT_MATRIX.read_text(encoding="utf-8")
        rendered = render_matrix_document(current, load_registry())
        if args.write:
            DEFAULT_MATRIX.write_text(rendered, encoding="utf-8")
        else:
            print(rendered)
        return 0
    except RegistryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def command_migrate(args: argparse.Namespace) -> int:
    try:
        records = migrate_markdown_matrix()
        yaml_text = records_to_yaml(records)
        if args.write:
            DEFAULT_REGISTRY.write_text(yaml_text, encoding="utf-8")
            current = DEFAULT_MATRIX.read_text(encoding="utf-8")
            DEFAULT_MATRIX.write_text(render_matrix_document(current, records), encoding="utf-8")
        else:
            print(yaml_text)
        return 0
    except RegistryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="DeliverHQ capability registry")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="validate registry and generated matrix")
    check.add_argument("--json", action="store_true")
    check.set_defaults(func=command_check)

    render = subparsers.add_parser("render", help="render CAPABILITY-MATRIX.md from YAML")
    render.add_argument("--write", action="store_true")
    render.set_defaults(func=command_render)

    migrate = subparsers.add_parser("migrate", help="one-time migration from current Markdown matrix")
    migrate.add_argument("--write", action="store_true")
    migrate.set_defaults(func=command_migrate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

