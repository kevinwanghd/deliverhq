import importlib
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skill" / "scripts"
# 全量 selftest 套件已下沉到 dev/scripts/（不随包发布）；测试从此处校验。
DEV_SCRIPTS = ROOT / "dev" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(DEV_SCRIPTS))


class ExecutionRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = importlib.import_module("execution_runtime")

    def make_script(self, source):
        temp_dir = tempfile.TemporaryDirectory(prefix="deliverhq-runtime-")
        script = Path(temp_dir.name) / "probe.py"
        script.write_text(source, encoding="utf-8")
        self.addCleanup(temp_dir.cleanup)
        return script

    def test_success_preserves_utf8_output(self):
        script = self.make_script("print('执行成功')\n")

        result = self.runtime.run_script(script, timeout=5)

        self.assertTrue(result.ok)
        self.assertEqual(0, result.returncode)
        self.assertEqual("执行成功", result.stdout.strip())
        self.assertFalse(result.timed_out)

    def test_nonzero_exit_preserves_code_and_stderr(self):
        script = self.make_script(
            "import sys\nprint('bad input', file=sys.stderr)\nsys.exit(7)\n"
        )

        result = self.runtime.run_script(script, timeout=5)

        self.assertFalse(result.ok)
        self.assertEqual(7, result.returncode)
        self.assertIn("bad input", result.stderr)
        self.assertFalse(result.timed_out)

    def test_timeout_returns_a_failure_result(self):
        script = self.make_script("import time\ntime.sleep(2)\n")

        result = self.runtime.run_script(script, timeout=0.05)

        self.assertFalse(result.ok)
        self.assertNotEqual(0, result.returncode)
        self.assertTrue(result.timed_out)
        self.assertIn("timed out", result.stderr.lower())

    def test_environment_is_merged_with_utf8_defaults(self):
        script = self.make_script(
            "import os\nprint(os.environ['PROBE_VALUE'])\nprint(os.environ['PYTHONIOENCODING'])\n"
        )

        result = self.runtime.run_script(
            script,
            env={"PROBE_VALUE": "present"},
            timeout=5,
        )

        self.assertTrue(result.ok)
        self.assertEqual(["present", "utf-8"], result.stdout.strip().splitlines())


class RuntimeAdoptionTests(unittest.TestCase):
    def test_anti_gaming_git_diff_decodes_utf8_explicitly(self):
        anti_gaming = importlib.import_module("anti_gaming_check")
        completed = type("Completed", (), {"returncode": 0, "stdout": "中文差异", "stderr": ""})()
        with patch.object(anti_gaming.subprocess, "run", return_value=completed) as run:
            code, output, error = anti_gaming._git(["diff", "HEAD"], ROOT)

        self.assertEqual((0, "中文差异", ""), (code, output, error))
        self.assertEqual("utf-8", run.call_args.kwargs["encoding"])
        self.assertEqual("replace", run.call_args.kwargs["errors"])

    def test_reviewgate_ignores_framework_self_development_cr_artifacts(self):
        reviewgate = importlib.import_module("reviewgate")
        changed = [
            "skill/change-requests/CR-007/acceptance-spec.md",
            "skill/deliverhq/go.py",
        ]

        self.assertEqual(["skill/deliverhq/go.py"], reviewgate._relevant_changed_files(changed))

    def test_gate_wrapper_uses_shared_execution_runtime(self):
        gate_wrapper = importlib.import_module("gate_wrapper")
        runtime = importlib.import_module("execution_runtime")

        self.assertIs(runtime.run_script, gate_wrapper.run_script)
        source = (SCRIPTS / "gate_wrapper.py").read_text(encoding="utf-8")
        self.assertNotIn("subprocess.run(", source)

    def test_orchestrator_core_uses_shared_execution_runtime(self):
        core = importlib.import_module("orchestrator_core")
        runtime = importlib.import_module("execution_runtime")

        self.assertIs(runtime.run_script, core.run_script)
        source = (SCRIPTS / "orchestrator_core.py").read_text(encoding="utf-8")
        self.assertNotIn("subprocess.run(", source)

    def test_orchestrator_reexports_extracted_routing_logic(self):
        orchestrator = importlib.import_module("skill_orchestrator")
        routing = importlib.import_module("orchestrator_routing")

        for name in (
            "estimate_cost",
            "has_gate_cache",
            "analyze_cr_size",
            "route_situation",
        ):
            self.assertIs(getattr(routing, name), getattr(orchestrator, name))

    def test_routing_module_does_not_depend_on_orchestrator(self):
        source = (SCRIPTS / "orchestrator_routing.py").read_text(encoding="utf-8")
        self.assertNotIn("import skill_orchestrator", source)
        self.assertNotIn("from skill_orchestrator", source)

    def test_public_entrypoints_are_thin(self):
        self.assertLessEqual(
            len((SCRIPTS / "skill_orchestrator.py").read_text(encoding="utf-8").splitlines()),
            80, "skill_orchestrator.py")
        # selftest 薄入口已随套件下沉到 dev/scripts/。
        self.assertLessEqual(
            len((DEV_SCRIPTS / "selftest.py").read_text(encoding="utf-8").splitlines()),
            80, "selftest.py")

    def test_selftest_contract_catalog_is_split_by_domain(self):
        package = DEV_SCRIPTS / "selftest_contracts"
        for name in ("core.py", "workflow.py", "governance.py"):
            self.assertTrue((package / name).is_file(), name)

    def test_packaging_hygiene_ignores_runtime_python_cache(self):
        suite = importlib.import_module("selftest_contracts.suite")
        temp = tempfile.TemporaryDirectory(prefix="deliverhq-package-hygiene-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        cache = root / "scripts" / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "module.cpython-313.pyc").write_bytes(b"cache")
        original_root = suite.ROOT
        self.addCleanup(setattr, suite, "ROOT", original_root)
        suite.ROOT = root

        self.assertTrue(suite.check_packaging_hygiene())

    def test_init_cr_materializes_core_files_lazily_by_default(self):
        init_cr = importlib.import_module("init_cr")
        temp = tempfile.TemporaryDirectory(prefix="deliverhq-init-cr-")
        self.addCleanup(temp.cleanup)
        home = Path(temp.name) / "DeliverHQ"

        ok = init_cr.init_cr(
            "CR-101",
            "Lazy materialization",
            requester="tester",
            lane="fast",
            use_worktree=False,
            home=str(home),
        )

        cr = home / "change-requests" / "CR-101"
        self.assertTrue(ok)
        self.assertTrue((cr / "request.md").is_file())
        self.assertTrue((cr / "template-manifest.yml").is_file())
        self.assertFalse((cr / "design" / "hi-fi-spec.md").exists())
        self.assertFalse((cr / "deployment-checklist.md").exists())

    def test_init_cr_full_template_preserves_legacy_copy_behavior(self):
        init_cr = importlib.import_module("init_cr")
        temp = tempfile.TemporaryDirectory(prefix="deliverhq-init-cr-full-")
        self.addCleanup(temp.cleanup)
        home = Path(temp.name) / "DeliverHQ"

        ok = init_cr.init_cr(
            "CR-102",
            "Full materialization",
            requester="tester",
            lane="fast",
            use_worktree=False,
            home=str(home),
            full_template=True,
        )

        cr = home / "change-requests" / "CR-102"
        self.assertTrue(ok)
        self.assertTrue((cr / "design" / "hi-fi-spec.md").is_file())
        self.assertTrue((cr / "deployment-checklist.md").is_file())
        self.assertFalse((cr / "template-manifest.yml").exists())

    def test_review_provenance_missing_warns_standard_but_blocks_high_risk(self):
        reviewgate = importlib.import_module("reviewgate")

        standard_blockers, standard_warnings = reviewgate.review_provenance_findings(
            "## Review\nAPPROVED\n",
            lane="standard",
        )
        high_risk_blockers, _ = reviewgate.review_provenance_findings(
            "## Review\nAPPROVED\n",
            lane="high-risk",
        )

        self.assertEqual([], standard_blockers)
        self.assertTrue(any("review provenance missing" in item for item in standard_warnings))
        self.assertTrue(any("review provenance missing" in item for item in high_risk_blockers))

    def test_review_provenance_accepts_fresh_agent_evidence(self):
        reviewgate = importlib.import_module("reviewgate")
        content = """## Review
```yaml
schema: deliverhq-review-provenance
version: 1
reviewer_mode: fresh-agent
author_role: dev-agent
reviewed_inputs:
  - git diff
  - acceptance-spec.md
excluded_inputs:
  - implementation self-assessment
```
"""

        blockers, warnings = reviewgate.review_provenance_findings(content, lane="high-risk")

        self.assertEqual([], blockers)
        self.assertEqual([], warnings)

    def test_deploy_ready_state_alias_loads_as_delivery_ready(self):
        cr_state = importlib.import_module("cr_state")
        temp = tempfile.TemporaryDirectory(prefix="deliverhq-state-")
        self.addCleanup(temp.cleanup)
        cr = Path(temp.name)
        (cr / "state.yml").write_text(
            yaml.safe_dump(
                {
                    "cr_id": "CR-103",
                    "title": "legacy state",
                    "lane": "standard",
                    "current_state": "deploy_ready",
                    "current_phase": "deploy",
                    "current_owner": "deploy-agent",
                },
                allow_unicode=True,
            ),
            encoding="utf-8",
        )

        state = cr_state.load_state(cr)

        self.assertEqual(cr_state.CRState.DELIVERY_READY, state.current_state)


class BrownfieldPlanEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.checker = importlib.import_module("plan_checker")

    def write_plan(self, task):
        temp = tempfile.TemporaryDirectory(prefix="deliverhq-plan-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "acceptance-spec.md").write_text("### AC-1: evidence\n", encoding="utf-8")
        data = {
            "schema": "deliverhq-plan", "version": 1, "project_mode": "brownfield",
            "tasks": [task],
        }
        (root / "plan.yml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        return root

    def valid_task(self):
        return {
            "task_id": "T1", "goal": "extend route", "files": ["route.py"],
            "read_files": ["existing.py"], "write_files": ["route.py"],
            "reuse_checks": [{"intent": "reuse", "command": "rg route .", "result": "existing.py"}],
            "destructive_change": {"detected": False, "signals": [], "reason": "additive change"},
            "depends_on": [], "covers": ["AC-1"], "verify": "python -m unittest", "done": "test exits 0",
        }

    def test_valid_brownfield_evidence_passes(self):
        passed, blockers, _ = self.checker.check_plan(str(self.write_plan(self.valid_task())))
        self.assertTrue(passed, blockers)

    def test_missing_reuse_evidence_blocks(self):
        task = self.valid_task()
        task["reuse_checks"] = []
        passed, blockers, _ = self.checker.check_plan(str(self.write_plan(task)))
        self.assertFalse(passed)
        self.assertTrue(any("reuse_checks" in item for item in blockers))

    def test_destructive_change_requires_reference_scan_and_approval(self):
        task = self.valid_task()
        task["goal"] = "rename public interface"
        task["destructive_change"] = {"detected": True, "affected_interfaces": ["route"]}
        passed, blockers, _ = self.checker.check_plan(str(self.write_plan(task)))
        self.assertFalse(passed)
        self.assertTrue(any("reference_scan" in item for item in blockers))
        self.assertTrue(any("human_decision" in item for item in blockers))

    def test_protected_write_requires_explicit_signal(self):
        task = self.valid_task()
        task["write_files"] = ["package.json"]
        passed, blockers, _ = self.checker.check_plan(str(self.write_plan(task)))
        self.assertFalse(passed)
        self.assertTrue(any("protected-path" in item for item in blockers))


class ContextHandoffEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = importlib.import_module("context_window_check")

    def fixture(self, phases=None, stale=False):
        temp = tempfile.TemporaryDirectory(prefix="deliverhq-context-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        source = root / "acceptance-spec.md"
        source.write_text("spec\n", encoding="utf-8")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if stale:
            digest = "0" * 64
        phases = phases or ["spec", "dev"]
        text = """## Handoff Evidence
```yaml
schema: deliverhq-context-handoff
version: 1
current_phase: dev
previous_phase: spec
full_context_phases: %s
input_hashes:
  acceptance-spec.md: "%s"
sources:
  - path: acceptance-spec.md
    sha256: "%s"
excluded_approaches:
  - approach: duplicate scanner
    reason: reuse legacy scan
next_action: implement tests
```
""" % (yaml.safe_dump(phases, default_flow_style=True).strip(), digest, digest)
        return root, text

    def test_current_handoff_evidence_passes(self):
        root, text = self.fixture()
        blockers, warnings = self.gate.validate_handoff_evidence(text, root)
        self.assertEqual([], blockers)
        self.assertEqual([], warnings)

    def test_stale_hash_blocks(self):
        root, text = self.fixture(stale=True)
        blockers, _ = self.gate.validate_handoff_evidence(text, root)
        self.assertTrue(any("hash stale" in item for item in blockers))

    def test_more_than_two_full_phases_blocks(self):
        root, text = self.fixture(phases=["spec", "design", "dev"])
        blockers, _ = self.gate.validate_handoff_evidence(text, root)
        self.assertTrue(any("最多 2" in item for item in blockers))


    def test_phase_outside_window_blocks(self):
        root, text = self.fixture(phases=["spec", "design"])
        blockers, _ = self.gate.validate_handoff_evidence(text, root)
        self.assertTrue(any("current_phase" in item for item in blockers))


if __name__ == "__main__":
    unittest.main()
