import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS))


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
        for name in ("skill_orchestrator.py", "selftest.py"):
            lines = (SCRIPTS / name).read_text(encoding="utf-8").splitlines()
            self.assertLessEqual(len(lines), 80, name)

    def test_selftest_contract_catalog_is_split_by_domain(self):
        package = SCRIPTS / "selftest_contracts"
        for name in ("core.py", "workflow.py", "governance.py"):
            self.assertTrue((package / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
