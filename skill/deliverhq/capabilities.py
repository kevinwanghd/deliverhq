"""Machine-readable capability registry and Markdown renderer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable, List, Sequence

import yaml


SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = SKILL_ROOT / "capabilities.yml"
DEFAULT_MATRIX = SKILL_ROOT / "CAPABILITY-MATRIX.md"

BEGIN_MARKER = "<!-- BEGIN GENERATED CAPABILITIES -->"
END_MARKER = "<!-- END GENERATED CAPABILITIES -->"

STATUSES = {"stable", "experimental", "placeholder", "roadmap"}
INTEGRATION_STATUSES = {"integrated", "not_integrated"}
REQUIRED_FIELDS = (
    "id",
    "name",
    "script",
    "status",
    "integrated",
    "default_enabled",
    "allowed_in_pipeline",
    "description",
)


class RegistryError(ValueError):
    """Raised when the capability registry is malformed."""


@dataclass(frozen=True)
class Capability:
    id: str
    name: str
    script: str
    status: str
    integrated: str
    default_enabled: bool
    allowed_in_pipeline: bool
    description: str


def _require_string(raw: dict, field: str, index: int) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"capability[{index}] field {field!r} must be a non-empty string")
    return value.strip()


def _require_bool(raw: dict, field: str, index: int) -> bool:
    value = raw.get(field)
    if not isinstance(value, bool):
        raise RegistryError(f"capability[{index}] field {field!r} must be boolean")
    return value


def _validate_record(raw: object, index: int) -> Capability:
    if not isinstance(raw, dict):
        raise RegistryError(f"capability[{index}] must be a mapping")
    missing = [field for field in REQUIRED_FIELDS if field not in raw]
    if missing:
        raise RegistryError(f"capability[{index}] missing fields: {', '.join(missing)}")

    status = _require_string(raw, "status", index)
    if status not in STATUSES:
        raise RegistryError(f"capability[{index}] has invalid status: {status}")
    integrated = _require_string(raw, "integrated", index)
    if integrated not in INTEGRATION_STATUSES:
        raise RegistryError(f"capability[{index}] has invalid integrated value: {integrated}")

    cap_id = _require_string(raw, "id", index)
    if not re.fullmatch(r"cap-[0-9]{3}", cap_id):
        raise RegistryError(f"capability[{index}] id must match cap-###: {cap_id}")

    return Capability(
        id=cap_id,
        name=_require_string(raw, "name", index),
        script=_require_string(raw, "script", index),
        status=status,
        integrated=integrated,
        default_enabled=_require_bool(raw, "default_enabled", index),
        allowed_in_pipeline=_require_bool(raw, "allowed_in_pipeline", index),
        description=_require_string(raw, "description", index),
    )


def load_registry(path: Path | str | None = None) -> List[Capability]:
    """Load and validate the YAML capability registry."""
    registry_path = Path(path) if path is not None else DEFAULT_REGISTRY
    if not registry_path.exists():
        raise RegistryError(f"registry does not exist: {registry_path}")
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    records = payload.get("capabilities")
    if not isinstance(records, list):
        raise RegistryError("registry must contain a capabilities list")

    capabilities = [_validate_record(record, index) for index, record in enumerate(records, start=1)]
    seen = set()
    duplicates = []
    for capability in capabilities:
        if capability.id in seen:
            duplicates.append(capability.id)
        seen.add(capability.id)
    if duplicates:
        raise RegistryError(f"duplicate capability ids: {', '.join(sorted(set(duplicates)))}")
    return capabilities


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|")


def render_matrix(records: Sequence[Capability] | None = None) -> str:
    """Render the generated capability table."""
    capabilities = list(records) if records is not None else load_registry()
    lines = [
        "| 能力 | 脚本/文档 | status | integrated | default_enabled | allowed_in_pipeline | 说明 |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for record in capabilities:
        lines.append(
            "| {name} | {script} | {status} | {integrated} | {default_enabled} | {allowed_in_pipeline} | {description} |".format(
                name=_cell(record.name),
                script=_cell(record.script),
                status=record.status,
                integrated=record.integrated,
                default_enabled=str(record.default_enabled).lower(),
                allowed_in_pipeline=str(record.allowed_in_pipeline).lower(),
                description=_cell(record.description),
            )
        )
    return "\n".join(lines)


def _generated_block(records: Sequence[Capability]) -> str:
    return f"{BEGIN_MARKER}\n{render_matrix(records)}\n{END_MARKER}"


def render_matrix_document(document: str, records: Sequence[Capability] | None = None) -> str:
    """Replace or insert the generated capability table inside a matrix document."""
    capabilities = list(records) if records is not None else load_registry()
    block = _generated_block(capabilities)
    if BEGIN_MARKER in document or END_MARKER in document:
        pattern = re.compile(
            rf"{re.escape(BEGIN_MARKER)}.*?{re.escape(END_MARKER)}",
            flags=re.DOTALL,
        )
        if not pattern.search(document):
            raise RegistryError("generated capability markers are incomplete")
        return pattern.sub(block, document, count=1)

    table_pattern = re.compile(
        r"(?ms)^\| .+?status.+?default_enabled.+?\n"
        r"^\|[-:| ]+\|\n"
        r"(?:^\|.*\n)+",
    )
    if not table_pattern.search(document):
        raise RegistryError("capability matrix table was not found")
    return table_pattern.sub(block + "\n", document, count=1)


def assert_matrix_current(matrix_path: Path | str = DEFAULT_MATRIX) -> None:
    path = Path(matrix_path)
    current = path.read_text(encoding="utf-8")
    rendered = render_matrix_document(current, load_registry())
    if current != rendered:
        raise RegistryError(f"{path} is not current; run capability_registry.py render --write")


def records_to_yaml(records: Iterable[Capability]) -> str:
    payload = {
        "schema": "deliverhq-capabilities",
        "version": 1,
        "capabilities": [record.__dict__ for record in records],
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)

