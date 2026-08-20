import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
# Add skill/scripts to path for common module imports
sys.path.insert(0, str(ROOT / "skill" / "scripts"))
SCRIPT = ROOT / "skill" / "scripts" / "arc_scheduler.py"
spec = importlib.util.spec_from_file_location("arc_scheduler", SCRIPT)
arc_scheduler = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = arc_scheduler
spec.loader.exec_module(arc_scheduler)


class Builder:
    def build(self, cr_path, task_id, run_id):
        path = cr_path / "runtime" / "session-packs" / f"{run_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("pack", encoding="utf-8")
        return path


class Adapter:
    def run(self, session_pack, worktree, run_id, timeout=1800):
        (worktree / "agent-result.yml").write_text("status: done", encoding="utf-8")
        return {"exit_kind": "success", "exit_code": 0}


class FailingAdapter(Adapter):
    def run(self, session_pack, worktree, run_id, timeout=1800):
        return {"exit_kind": "timeout", "exit_code": -1}


class Verifier:
    def verify(self, cr_path, task_id, run_id):
        return True, {"evidence_paths": [str(cr_path / "agent-result.yml")]}


class TestArcScheduler(unittest.TestCase):
    def test_serial_run_persists_done_and_resumes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "plan.yml").write_text(yaml.safe_dump({"tasks": [
                {"task_id": "T1", "goal": "one"},
                {"task_id": "T2", "goal": "two", "depends_on": ["T1"]},
            ]}), encoding="utf-8")
            scheduler = arc_scheduler.ArcScheduler(
                root, Adapter(), pack_builder=Builder(), verifier=Verifier(),
                recovery_manager=lambda *args: ("READY", "retry"),
            )
            first = scheduler.run_once()
            self.assertEqual("DONE", first["state"])
            self.assertEqual("T1", first["task_id"])
            self.assertEqual("DONE", yaml.safe_load((root / "controller-state.yml").read_text())["tasks"]["T1"]["state"])
            second = arc_scheduler.ArcScheduler(
                root, Adapter(), pack_builder=Builder(), verifier=Verifier(),
                recovery_manager=lambda *args: ("READY", "retry"),
            ).run_once()
            self.assertEqual("T2", second["task_id"])

    def test_non_success_never_reaches_verifier(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "plan.yml").write_text(yaml.safe_dump({"tasks": [{"task_id": "T1", "goal": "one"}]}), encoding="utf-8")
            calls = []
            verifier = lambda *args: (calls.append(True), (True, {}))[1]
            outcome = arc_scheduler.ArcScheduler(
                root, FailingAdapter(), pack_builder=Builder(), verifier=verifier,
                recovery_manager=lambda *args: ("NEEDS_HUMAN", "timeout"),
            ).run_once()
            self.assertEqual("NEEDS_HUMAN", outcome["state"])
            self.assertEqual([], calls)

    def test_inflight_state_is_requeued_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "plan.yml").write_text(yaml.safe_dump({"tasks": [{"task_id": "T1", "goal": "one"}]}), encoding="utf-8")
            runtime = root / "runtime"
            runtime.mkdir()
            (runtime / "controller-state.yml").write_text(yaml.safe_dump({
                "schema_version": "arc-controller/v1", "tasks": {"T1": {"state": "RUNNING", "attempt": 1}},
            }), encoding="utf-8")
            scheduler = arc_scheduler.ArcScheduler(root, Adapter(), pack_builder=Builder(), verifier=Verifier(), recovery_manager=lambda *args: ("READY", "retry"))
            self.assertEqual("T1", scheduler.select_task())


if __name__ == "__main__":
    unittest.main()
