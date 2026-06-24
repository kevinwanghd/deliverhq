#!/usr/bin/env python3
"""
CR State Machine - CR 状态机管理

每个 CR 维护 lane、phase、owner、last_gate、blocked_by、next_required_gate，
避免多 Agent 协作时靠猜。
"""


from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from runtime_support import write_gate_evidence

STATE_FILE = "state.yml"
DEFAULT_LANE = "standard"
GATE_TO_STATE = {
    "spec": "spec_review",
    "design": "design",
    "architecture": "design",
    "context": "design",
    "dev": "dev",
    "review": "code_review",
    "quality": "testing",
    "deploy": "deploy_ready",
    "writeback": "archived",
    "permission": "blocked",
}
GATE_SEQUENCE = ["spec", "design", "architecture", "context", "pre_dev", "dev", "review", "quality", "deploy", "writeback"]


class CRState(Enum):
    """CR 状态枚举"""

    DRAFT = "draft"
    SPEC_REVIEW = "spec_review"
    DESIGN = "design"
    DEV = "dev"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    DEPLOY_READY = "deploy_ready"
    DEPLOYED = "deployed"
    ARCHIVED = "archived"
    BLOCKED = "blocked"
    NEEDS_HUMAN = "needs_human"
    CANCELLED = "cancelled"


class GateStatus(Enum):
    """Gate 状态枚举"""

    PENDING = "pending"
    RUNNING = "running"
    PASS = "pass"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


@dataclass
class StateTransition:
    """状态转换记录"""

    from_state: str
    to_state: str
    timestamp: str
    trigger: str
    operator: str


@dataclass
class CRStateSnapshot:
    """CR 状态快照"""

    cr_id: str
    title: str
    lane: str
    current_state: CRState
    current_phase: str
    current_owner: str
    goal: str = ""
    current_plan: Optional[str] = None
    completed_steps: List[str] = field(default_factory=list)
    blocking_reason: Optional[str] = None
    blocked_by: List[str] = field(default_factory=list)
    last_gate: Optional[str] = None
    next_gate: Optional[str] = None
    next_required_gate: Optional[str] = None
    requires_human: bool = False
    worktree_path: Optional[str] = None
    gate_status: Dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    transitions: List[StateTransition] = field(default_factory=list)


def _now() -> str:
    return datetime.now().isoformat()


def _state_file(cr_path: Path) -> Path:
    return cr_path / STATE_FILE


def _coerce_state(value: str) -> CRState:
    try:
        return CRState(value)
    except ValueError:
        return CRState.DRAFT


def _next_gate(gate_name: Optional[str]) -> Optional[str]:
    if not gate_name:
        return None

    try:
        index = GATE_SEQUENCE.index(gate_name)
    except ValueError:
        return None

    if index >= len(GATE_SEQUENCE) - 1:
        return None
    return GATE_SEQUENCE[index + 1]


def _serialize_state(state: CRStateSnapshot) -> Dict:
    next_gate = state.next_required_gate or state.next_gate

    return {
        "cr_id": state.cr_id,
        "title": state.title,
        "lane": state.lane,
        "current_state": state.current_state.value,
        "current_phase": state.current_phase,
        "current_owner": state.current_owner,
        "goal": state.goal,
        "current_plan": state.current_plan,
        "completed_steps": list(state.completed_steps),
        "blocking_reason": state.blocking_reason,
        "blocked_by": list(state.blocked_by),
        "last_gate": state.last_gate,
        "next_gate": next_gate,
        "next_required_gate": next_gate,
        "requires_human": state.requires_human,
        "worktree_path": state.worktree_path,
        "gate_status": dict(state.gate_status),
        "created_at": state.created_at,
        "updated_at": state.updated_at,
        "started_at": state.started_at,
        "completed_at": state.completed_at,
        "transitions": [
            {
                "from_state": transition.from_state,
                "to_state": transition.to_state,
                "timestamp": transition.timestamp,
                "trigger": transition.trigger,
                "operator": transition.operator,
            }
            for transition in state.transitions
        ],
    }


def create_state(
    cr_path: Path,
    cr_id: str,
    title: str,
    lane: str = DEFAULT_LANE,
    owner: str = "human",
    goal: str = "",
) -> CRStateSnapshot:
    """创建并保存初始 CR 状态。"""

    snapshot = CRStateSnapshot(
        cr_id=cr_id,
        title=title,
        lane=lane,
        current_state=CRState.DRAFT,
        current_phase="request",
        current_owner=owner,
        goal=goal,
        current_plan=None,
        completed_steps=[],
        blocking_reason=None,
        blocked_by=[],
        last_gate=None,
        next_gate="spec",
        next_required_gate="spec",
        requires_human=lane == "high-risk",
        worktree_path=None,
        gate_status={},
        created_at=_now(),
        updated_at=_now(),
        started_at=_now(),
        completed_at=None,
        transitions=[],
    )
    save_state(cr_path, snapshot)
    return snapshot


def ensure_state(
    cr_path: Path,
    cr_id: Optional[str] = None,
    title: Optional[str] = None,
    lane: str = DEFAULT_LANE,
    owner: str = "human",
) -> CRStateSnapshot:
    """加载状态；不存在时创建默认状态。"""

    state = load_state(cr_path)
    if state:
        return state

    resolved_cr_id = cr_id or cr_path.name
    resolved_title = title or resolved_cr_id
    return create_state(cr_path, resolved_cr_id, resolved_title, lane=lane, owner=owner)


def load_state(cr_path: Path) -> Optional[CRStateSnapshot]:
    """加载 CR 状态。"""

    state_file = _state_file(cr_path)
    if not state_file.exists():
        return None

    with open(state_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    gate_status = data.get("gate_status", {}) or {}
    transitions = [StateTransition(**item) for item in data.get("transitions", []) or []]
    next_gate = data.get("next_required_gate") or data.get("next_gate")

    return CRStateSnapshot(
        cr_id=data.get("cr_id", cr_path.name),
        title=data.get("title", cr_path.name),
        lane=data.get("lane", DEFAULT_LANE),
        current_state=_coerce_state(data.get("current_state", CRState.DRAFT.value)),
        current_phase=data.get("current_phase", "request"),
        current_owner=data.get("current_owner", "human"),
        goal=data.get("goal", "") or "",
        current_plan=data.get("current_plan"),
        completed_steps=data.get("completed_steps", []) or [],
        blocking_reason=data.get("blocking_reason"),
        blocked_by=data.get("blocked_by", []) or [],
        last_gate=data.get("last_gate"),
        next_gate=next_gate,
        next_required_gate=next_gate,
        requires_human=data.get("requires_human", False),
        worktree_path=data.get("worktree_path"),
        gate_status=gate_status,
        created_at=data.get("created_at", _now()),
        updated_at=data.get("updated_at", _now()),
        started_at=data.get("started_at"),
        completed_at=data.get("completed_at"),
        transitions=transitions,
    )


def save_state(cr_path: Path, state: CRStateSnapshot):
    """保存 CR 状态。"""

    state_file = _state_file(cr_path)
    state_file.parent.mkdir(parents=True, exist_ok=True)

    payload = _serialize_state(state)
    with open(state_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False)


def transition_state(
    cr_path: Path,
    new_state: CRState,
    trigger: str,
    operator: str = "system",
) -> CRStateSnapshot:
    """状态转换。"""

    state = ensure_state(cr_path)
    transition = StateTransition(
        from_state=state.current_state.value,
        to_state=new_state.value,
        timestamp=_now(),
        trigger=trigger,
        operator=operator,
    )

    state.transitions.append(transition)
    state.current_state = new_state
    state.updated_at = _now()
    state.completed_at = _now() if new_state == CRState.ARCHIVED else state.completed_at
    save_state(cr_path, state)
    return state


def update_gate_status(
    cr_path: Path,
    gate_name: str,
    status: GateStatus,
    blockers: Optional[List[str]] = None,
    state_after_pass: Optional[str] = None,
    current_phase: Optional[str] = None,
    current_owner: Optional[str] = None,
    next_required_gate: Optional[str] = None,
    requires_human: Optional[bool] = None,
    warnings: Optional[List[str]] = None,
    commands_run: Optional[List[str]] = None,
    artifacts: Optional[List[str]] = None,
    next_action: Optional[str] = None,
    metadata: Optional[Dict] = None,
):
    """更新 Gate 状态并写回 state.yml。"""

    state = ensure_state(cr_path)
    state.last_gate = gate_name
    state.gate_status[gate_name] = status.value
    state.updated_at = _now()

    if requires_human is not None:
        state.requires_human = requires_human

    if status == GateStatus.BLOCKED:
        state.current_state = CRState.BLOCKED
        state.blocking_reason = blockers[0] if blockers else f"{gate_name} failed"
        state.blocked_by = list(blockers or [gate_name])
        state.next_gate = next_required_gate or gate_name
        state.next_required_gate = state.next_gate
    else:
        state.blocking_reason = None
        state.blocked_by = []
        if state_after_pass:
            state.current_state = _coerce_state(state_after_pass)
        if current_phase:
            state.current_phase = current_phase
        if current_owner:
            state.current_owner = current_owner
        state.next_gate = next_required_gate or _next_gate(gate_name)
        state.next_required_gate = state.next_gate

    save_state(cr_path, state)
    write_gate_evidence(
        cr_path=cr_path,
        gate_name=gate_name,
        result=status.value,
        blocking_items=blockers,
        warnings=warnings,
        commands_run=commands_run,
        artifacts=artifacts,
        next_action=next_action or (
            f"Run {state.next_required_gate}" if state.next_required_gate else "No further gate required"
        ),
        metadata=metadata or {
            "current_state": state.current_state.value,
            "current_phase": state.current_phase,
            "current_owner": state.current_owner,
            "requires_human": state.requires_human,
            "worktree_path": state.worktree_path,
        },
    )
    return state


def _warn_if_cr_outside_home(cr_path: Path) -> None:
    """warning-first：CR 目录不在任何 DeliverHQ/ 内时告警，提示归位（不阻断）。

    DeliverHQ 产物应集中在 <项目根>/DeliverHQ/ 下。若 agent 手动把 CR 建在别处
    （根目录 / skill 安装目录），这里提醒归位，但不阻断既有流程。
    skill 自身自检（CR 在 skill 包的 change-requests/）属预期，不告警。
    """
    try:
        p = Path(cr_path).resolve()
        parts = p.parts
        if "DeliverHQ" in parts:
            return  # 已在 DeliverHQ/ 内，正常
        # skill 包自身布局：scripts/ 与 change-requests/ 同级（自检场景），放行不告警
        skill_root = Path(__file__).resolve().parent.parent
        try:
            p.relative_to(skill_root)
            return
        except ValueError:
            pass
        print(
            "⚠ [DeliverHQ Home] CR 目录不在 DeliverHQ/ 内: %s\n"
            "  建议归位到 <项目根>/DeliverHQ/change-requests/ ，"
            "用 init_cr.py（自动定位 DeliverHQ home）创建 CR。" % p
        )
    except Exception:
        pass  # 校验失败绝不影响主流程


def update_gate_from_result(
    cr_path: Path,
    gate_name: str,
    passed: bool,
    blockers: Optional[List[str]] = None,
    state_after_pass: Optional[str] = None,
    current_phase: Optional[str] = None,
    current_owner: Optional[str] = None,
    next_required_gate: Optional[str] = None,
    requires_human: Optional[bool] = None,
    warnings: Optional[List[str]] = None,
    commands_run: Optional[List[str]] = None,
    artifacts: Optional[List[str]] = None,
    next_action: Optional[str] = None,
    metadata: Optional[Dict] = None,
):
    """根据 Gate 结果写回状态。"""

    _warn_if_cr_outside_home(cr_path)

    status = GateStatus.PASS if passed else GateStatus.BLOCKED
    return update_gate_status(
        cr_path=cr_path,
        gate_name=gate_name,
        status=status,
        blockers=blockers,
        state_after_pass=state_after_pass,
        current_phase=current_phase,
        current_owner=current_owner,
        next_required_gate=next_required_gate,
        requires_human=requires_human,
        warnings=warnings,
        commands_run=commands_run,
        artifacts=artifacts,
        next_action=next_action,
        metadata=metadata,
    )


def set_worktree_path(cr_path: Path, worktree_path: Optional[str]) -> CRStateSnapshot:
    """Persist the worktree path associated with the CR."""
    state = ensure_state(cr_path)
    state.worktree_path = worktree_path
    state.updated_at = _now()
    save_state(cr_path, state)
    return state


def format_state_report(state: CRStateSnapshot) -> str:
    """格式化状态报告。"""

    report = [
        "╔════════════════════════════════════════════════════════╗",
        f"║  CR 状态快照: {state.cr_id}",
        "╚════════════════════════════════════════════════════════╝",
        "",
        f"标题: {state.title}",
        f"流程: {state.lane.upper()} Lane",
        f"当前状态: {state.current_state.value}",
        f"当前阶段: {state.current_phase}",
        f"当前负责: {state.current_owner}",
    ]

    if state.last_gate:
        report.append(f"最后执行 Gate: {state.last_gate}")
    if state.blocking_reason:
        report.append(f"🚫 阻塞原因: {state.blocking_reason}")
    if state.blocked_by:
        report.append(f"🚧 blocked_by: {', '.join(state.blocked_by)}")
    if state.next_required_gate:
        report.append(f"📍 下一个 Gate: {state.next_required_gate}")
    if state.requires_human:
        report.append("⚠️  需要人工确认")

    report.append("")
    report.append("Gate 状态:")
    for gate, status in state.gate_status.items():
        icon = "✅" if status == "pass" else "❌" if status == "blocked" else "⏳"
        report.append(f"  {icon} {gate}: {status}")

    report.append("")
    report.append(f"创建时间: {state.created_at}")
    report.append(f"更新时间: {state.updated_at}")

    if state.transitions:
        report.append("")
        report.append("状态历史 (最近 5 条):")
        for transition in state.transitions[-5:]:
            report.append(
                f"  {transition.timestamp[:19]} | {transition.from_state} → {transition.to_state} | {transition.trigger}"
            )

    return "\n".join(report)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python cr_state.py <CR目录>")
        sys.exit(1)

    cr_path = Path(sys.argv[1])
    state = load_state(cr_path)

    if state:
        print(format_state_report(state))
    else:
        print(f"⚠️  未找到状态文件: {cr_path}/state.yml")
