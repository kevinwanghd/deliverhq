"""Read-only project-aware routing and artifact preflight for ``deliverhq go``."""

import re
import shlex
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


INACTIVE_STATES = {"archived", "completed", "deployed", "done"}
VERB_ARTIFACTS = {
    "spec": ("request.md", "acceptance-spec.md"),
    "design": ("acceptance-spec.md", "architecture-design.md"),
    "dev": (
        "acceptance-spec.md",
        "architecture-design.md",
        "context-summary.md",
        "traceability.yml",
    ),
    "verify": (
        "acceptance-spec.md",
        "review-report.md",
        "quality-report.md",
        "verification-manifest.yml",
    ),
    "archive": ("writeback-report.md",),
}
GATE_TO_VERB = {
    "spec": "spec",
    "drift": "spec",
    "design": "design",
    "architecture": "design",
    "context": "dev",
    "pre_dev": "dev",
    "predev": "dev",
    "permission": "dev",
    "dev": "dev",
    "review": "verify",
    "quality": "verify",
    "anti_gaming": "verify",
    "writeback": "archive",
    "archive": "archive",
}


def find_deliverhq_home(project_root: Path, explicit_home: Optional[Path] = None) -> Optional[Path]:
    candidates = [explicit_home] if explicit_home else []
    candidates.append(project_root / "DeliverHQ")
    for candidate in candidates:
        if candidate and (candidate / "change-requests").is_dir():
            return candidate.resolve()
    return explicit_home.resolve() if explicit_home and explicit_home.exists() else None


def _load_state(cr_dir: Path) -> Optional[dict]:
    state_file = cr_dir / "state.yml"
    if not state_file.is_file():
        return None
    try:
        data = yaml.safe_load(state_file.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else None
    except (OSError, yaml.YAMLError):
        return None


def discover_active_crs(home: Optional[Path]) -> List[Tuple[Path, dict]]:
    if not home:
        return []
    results = []
    for cr_dir in sorted((home / "change-requests").glob("CR-*")):
        if not cr_dir.is_dir():
            continue
        state = _load_state(cr_dir)
        if not state:
            continue
        status = str(state.get("current_state") or state.get("status") or "").lower()
        if status not in INACTIVE_STATES:
            results.append((cr_dir, state))
    return results


def select_active_cr(prompt: str, active: List[Tuple[Path, dict]]):
    explicit = re.search(r"\bCR-[A-Z0-9]+(?:-[A-Z0-9]+)*\b", prompt.upper())
    if explicit:
        return next((item for item in active if item[0].name == explicit.group(0)), None)
    return active[0] if len(active) == 1 else None


def infer_target_verb(state: dict) -> str:
    signal = str(
        state.get("next_required_gate")
        or state.get("next_gate")
        or state.get("current_phase")
        or "spec"
    ).lower().replace("-", "_")
    return GATE_TO_VERB.get(signal, "spec")


def artifact_preflight(cr_dir: Path, verb: str) -> dict:
    required = list(VERB_ARTIFACTS.get(verb, ()))
    present = [name for name in required if (cr_dir / name).is_file()]
    missing = [name for name in required if name not in present]
    recovery = None
    if missing:
        recovery = (
            "先由对应 Agent 产出 " + ", ".join(missing)
            + f"，再重新运行 deliverhq go（目标动词：{verb}；go 本身不会生成工件或执行 Gate）"
        )
    return {
        "required": required,
        "present": present,
        "missing": missing,
        "can_proceed": not missing,
        "recovery_action": recovery,
    }


def _command(core_dir: Path, cr_dir: Path, verb: str) -> str:
    script = core_dir / "scripts" / "skill_orchestrator.py"
    return "python {script} verb {verb} {cr}".format(
        script=shlex.quote(str(script)), verb=verb, cr=shlex.quote(str(cr_dir))
    )


def build_go_decision(
    route_decision: Dict,
    prompt: str,
    project_root: Path,
    core_dir: Path,
    home: Optional[Path] = None,
) -> Dict:
    """Enrich the existing route payload with project state and preflight evidence."""
    project_root = project_root.resolve()
    home = find_deliverhq_home(project_root, home)
    active = discover_active_crs(home)
    selected = select_active_cr(prompt, active)
    active_names = [item[0].name for item in active]
    result = dict(route_decision)
    result.update({
        "project_root": str(project_root),
        "deliverhq_home": str(home) if home else None,
        "active_crs": active_names,
        "current_cr": selected[0].name if selected else None,
        "target_verb": None,
        "target_phase": None,
        "engagement_mode": route_decision.get("lane"),
        "risk_lane": route_decision.get("governance_lane"),
        "artifact_preflight": None,
        "needs_human": False,
        "recommended_command": None,
        "read_only": True,
    })

    if len(active) > 1 and selected is None:
        result["needs_human"] = True
        result["artifact_preflight"] = {
            "required": ["unambiguous active CR"],
            "present": active_names,
            "missing": ["explicit CR-ID"],
            "can_proceed": False,
            "recovery_action": "指定一个活跃 CR-ID：" + ", ".join(active_names),
        }
        return result

    if selected is None:
        if route_decision.get("deliverhq_required"):
            result["target_verb"] = "spec"
            result["target_phase"] = "spec"
            result["artifact_preflight"] = {
                "required": ["active CR"],
                "present": [],
                "missing": ["active CR"],
                "can_proceed": False,
                "recovery_action": "先使用 init_cr.py 创建 CR 并填写 request.md",
            }
        else:
            result["artifact_preflight"] = {
                "required": [], "present": [], "missing": [],
                "can_proceed": True, "recovery_action": None,
            }
        return result

    cr_dir, state = selected
    verb = infer_target_verb(state)
    preflight = artifact_preflight(cr_dir, verb)
    result["target_verb"] = verb
    result["target_phase"] = verb
    result["artifact_preflight"] = preflight
    result["governance_lane"] = state.get("lane") or result.get("governance_lane")
    result["risk_lane"] = result["governance_lane"]
    result["engagement_mode"] = {
        "fast": "quick", "standard": "standard", "high-risk": "strict", "legacy": "legacy"
    }.get(result["risk_lane"], result["engagement_mode"])
    result["needs_human"] = bool(state.get("requires_human"))
    if preflight["can_proceed"] and not result["needs_human"]:
        result["recommended_command"] = _command(core_dir.resolve(), cr_dir.resolve(), verb)
    return result
