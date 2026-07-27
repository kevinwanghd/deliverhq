"""Persistent, serial ARC task scheduler.

The scheduler is deliberately a small orchestration layer.  It owns task state
and recovery decisions, while session-pack building, agent execution and
evidence verification remain replaceable collaborators.
"""
from __future__ import annotations

import importlib
import os
import tempfile
import argparse
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import yaml


class ArcState(str, Enum):
    READY = "READY"
    PACKED = "PACKED"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    DONE = "DONE"
    RECOVERABLE = "RECOVERABLE"
    NEEDS_HUMAN = "NEEDS_HUMAN"


STATES = tuple(s.value for s in ArcState)


class RunOutcome:
    def __init__(self, task_id: str | None, state: str, run_id: str | None = None,
                 reason: str = "", details: dict[str, Any] | None = None):
        self.task_id, self.state, self.run_id = task_id, state, run_id
        self.reason, self.details = reason, details

    def as_dict(self) -> dict[str, Any]:
        return {"task_id": self.task_id, "state": self.state, "run_id": self.run_id,
                "reason": self.reason, "details": self.details}


def _load_module(name: str):
    """Load a sibling script in both package and script execution modes."""
    try:
        return importlib.import_module(name)
    except ImportError:
        return importlib.import_module(f"skill.scripts.{name}")


class ArcScheduler:
    """Run at most one task per :meth:`run_once` invocation.

    ``controller-state.yml`` is updated after every transition, so an
    interrupted process can safely be resumed by constructing a new scheduler.
    Collaborators can be modules (the production API) or callables/objects
    (convenient for tests).
    """

    def __init__(
        self,
        cr_path: str | Path,
        adapter: Any,
        *,
        state_path: str | Path | None = None,
        pack_builder: Any | None = None,
        verifier: Any | None = None,
        recovery_manager: Any | None = None,
        timeout: int = 1800,
    ) -> None:
        self.cr_path = Path(cr_path)
        self.state_path = Path(state_path) if state_path else self.cr_path / "runtime" / "controller-state.yml"
        self.legacy_state_path = self.cr_path / "controller-state.yml"
        self.adapter = adapter
        self.pack_builder = pack_builder or _load_module("session_pack_builder")
        self.verifier = verifier or _load_module("evidence_verifier")
        self.recovery_manager = recovery_manager or _load_module("recovery_manager")
        self.timeout = timeout
        self.state = self._read_state()

    def _read_state(self) -> dict[str, Any]:
        source = self.state_path if self.state_path.exists() else self.legacy_state_path
        if source.exists():
            loaded = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict) and isinstance(loaded.get("tasks"), dict):
                changed = False
                for task_id, record in loaded["tasks"].items():
                    if record.get("state") in {ArcState.PACKED.value, ArcState.RUNNING.value, ArcState.VERIFYING.value}:
                        receipt = self.cr_path / "runtime" / "receipts" / f"{task_id}.yml"
                        receipt_run_id = None
                        if receipt.exists():
                            try:
                                receipt_run_id = (yaml.safe_load(receipt.read_text(encoding="utf-8")) or {}).get("run_id")
                            except (OSError, yaml.YAMLError):
                                receipt_run_id = None
                        if receipt_run_id and receipt_run_id == record.get("run_id"):
                            record["state"] = ArcState.DONE.value
                        else:
                            record["state"] = ArcState.READY.value
                            record["recovery_reason"] = "interrupted_run_resumed"
                        changed = True
                if changed:
                    self._write_state(loaded)
                return loaded
        plan_path = self.cr_path / "plan.yml"
        plan = yaml.safe_load(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else {}
        tasks: dict[str, Any] = {}
        for task in (plan or {}).get("tasks", []):
            task_id = str(task.get("task_id", ""))
            if task_id:
                initial = str(task.get("arc_state", task.get("state", task.get("status", "READY")))).upper()
                if initial not in STATES or initial == "DONE":
                    initial = ArcState.READY.value if initial != "DONE" else ArcState.DONE.value
                tasks[task_id] = {"state": initial, "attempt": 0}
        state = {"schema_version": "arc-controller/v1", "tasks": tasks, "active_task": None}
        self._write_state(state)
        return state

    def _write_state(self, state: dict[str, Any] | None = None) -> None:
        payload = state or self.state
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=self.state_path.name + ".", dir=str(self.state_path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                yaml.safe_dump(payload, handle, allow_unicode=True, sort_keys=False)
            os.replace(temp_name, self.state_path)
            # Compatibility mirror for older integrations; runtime/ is canonical.
            self.legacy_state_path.parent.mkdir(parents=True, exist_ok=True)
            self.legacy_state_path.write_text(
                yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def _tasks_from_plan(self) -> dict[str, dict[str, Any]]:
        plan_path = self.cr_path / "plan.yml"
        plan = yaml.safe_load(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else {}
        return {str(t.get("task_id")): t for t in (plan or {}).get("tasks", []) if t.get("task_id")}

    def select_task(self, requested_task: str | None = None) -> str | None:
        plan_tasks = self._tasks_from_plan()
        if requested_task:
            record = self.state.get("tasks", {}).get(requested_task)
            if not record or record.get("state") != ArcState.READY.value:
                return None
            task = plan_tasks.get(requested_task, {})
            deps = task.get("depends_on", task.get("dependencies", [])) or []
            return requested_task if all(
                self.state.get("tasks", {}).get(str(dep), {}).get("state") == ArcState.DONE.value
                for dep in deps
            ) else None
        for task_id, record in self.state.get("tasks", {}).items():
            if record.get("state") != ArcState.READY.value:
                continue
            task = plan_tasks.get(task_id, {})
            deps = task.get("depends_on", task.get("dependencies", [])) or []
            if all(self.state.get("tasks", {}).get(str(dep), {}).get("state") == ArcState.DONE.value for dep in deps):
                return task_id
        return None

    def _transition(self, task_id: str, state: ArcState | str, **fields: Any) -> None:
        value = state.value if isinstance(state, ArcState) else str(state).upper()
        if value not in STATES:
            raise ValueError(f"unknown ARC state: {value}")
        record = self.state.setdefault("tasks", {}).setdefault(task_id, {})
        record.update(fields, state=value)
        self.state["active_task"] = task_id if value in ("PACKED", "RUNNING", "VERIFYING") else None
        self.state["last_transition"] = {"task_id": task_id, "state": value}
        self._write_state()

    @staticmethod
    def _call_builder(builder: Any, cr_path: Path, task_id: str, run_id: str) -> Path:
        fn = getattr(builder, "build", builder)
        return Path(fn(cr_path, task_id, run_id))

    @staticmethod
    def _call_verify(verifier: Any, cr_path: Path, task_id: str, run_id: str) -> tuple[bool, dict[str, Any]]:
        fn = getattr(verifier, "verify", verifier)
        return fn(cr_path, task_id, run_id)

    def run_once(self, requested_task: str | None = None) -> dict[str, Any]:
        task_id = self.select_task(requested_task)
        if task_id is None:
            return RunOutcome(None, "IDLE", reason="no READY task").as_dict()
        record = self.state["tasks"][task_id]
        attempt = int(record.get("attempt", 0)) + 1
        run_id = f"{task_id}-r{attempt}"
        self._transition(task_id, ArcState.PACKED, attempt=attempt, run_id=run_id)
        try:
            pack = self._call_builder(self.pack_builder, self.cr_path, task_id, run_id)
            self._transition(task_id, ArcState.RUNNING, session_pack=str(pack))
            worktree = self._worktree()
            stale_result = worktree / "agent-result.yml"
            if stale_result.exists():
                stale_result.unlink()
            result = self.adapter.run(pack, worktree, run_id=run_id, timeout=self.timeout)
            result_dict = asdict(result) if hasattr(result, "__dataclass_fields__") else dict(result or {})
            self._transition(task_id, ArcState.VERIFYING, agent_result=result_dict)
            if result_dict.get("exit_kind") != "success":
                failure = dict(result_dict)
                failure.setdefault("blockers", []).append("agent process did not exit successfully")
                self._transition(task_id, ArcState.RECOVERABLE, verification=failure)
                return self._recover(task_id, run_id, failure)
            passed, details = self._call_verify(self.verifier, self.cr_path, task_id, run_id)
            if passed:
                self._transition(task_id, ArcState.DONE, verification=details)
                return RunOutcome(task_id, ArcState.DONE.value, run_id, details=details).as_dict()
            failure = dict(result_dict)
            failure.update(details or {})
            self._transition(task_id, ArcState.RECOVERABLE, verification=details)
            return self._recover(task_id, run_id, failure)
        except Exception as exc:
            failure = {"exit_kind": "error", "blockers": [str(exc)]}
            self._transition(task_id, ArcState.RECOVERABLE, error=str(exc))
            return self._recover(task_id, run_id, failure)

    def _recover(self, task_id: str, run_id: str, details: dict[str, Any]) -> dict[str, Any]:
        record_retry = getattr(self.recovery_manager, "record_retry", None)
        if record_retry:
            can_record, record_reason = record_retry(self.cr_path, task_id, details)
            if not can_record:
                self._transition(task_id, ArcState.NEEDS_HUMAN, reason=record_reason)
                return RunOutcome(task_id, ArcState.NEEDS_HUMAN.value, run_id, reason=record_reason, details=details).as_dict()
        fn = getattr(self.recovery_manager, "handle", self.recovery_manager)
        next_state, reason = fn(self.cr_path, task_id, run_id, details)
        next_state = str(next_state).upper()
        if next_state not in (ArcState.READY.value, ArcState.NEEDS_HUMAN.value):
            next_state = ArcState.NEEDS_HUMAN.value
        self._transition(task_id, next_state, reason=reason)
        return RunOutcome(task_id, next_state, run_id, reason=reason, details=details).as_dict()

    def _worktree(self) -> Path:
        state_path = self.cr_path / "state.yml"
        if state_path.exists():
            data = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
            if data.get("worktree_path"):
                path = Path(data["worktree_path"])
                if not path.is_absolute():
                    path = self.cr_path / path
                path.mkdir(parents=True, exist_ok=True)
                return path
        self.cr_path.mkdir(parents=True, exist_ok=True)
        return self.cr_path


def run_once(cr_path: str | Path, adapter: Any, **kwargs: Any) -> dict[str, Any]:
    """Convenience API for one serial scheduling step."""
    return ArcScheduler(cr_path, adapter, **kwargs).run_once()


__all__ = ["ArcState", "ArcScheduler", "RunOutcome", "run_once"]


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Run one serial ARC task")
    parser.add_argument("--path", required=True, help="change request directory")
    parser.add_argument("--task", required=True, help="task id, for example T1")
    parser.add_argument("--adapter", choices=("mock", "claude-code"), default="mock")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()

    module_name = "adapter_claude_code" if args.adapter == "claude-code" else "adapter_mock"
    module = _load_module(module_name)
    adapter_cls = module.ClaudeCodeAdapter if args.adapter == "claude-code" else module.MockAdapter
    outcome = ArcScheduler(args.path, adapter_cls(), timeout=args.timeout).run_once(args.task)
    print(yaml.safe_dump(outcome, allow_unicode=True, sort_keys=False).strip())
    return 0 if outcome.get("state") in {ArcState.DONE.value, "IDLE"} else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
