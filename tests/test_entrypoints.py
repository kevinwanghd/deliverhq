import importlib.util
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


sys.dont_write_bytecode = True


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skill"
SCRIPTS = SKILL / "scripts"


def load_script(name):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPTS))
    return module


class GateWrapperEntrypointTests(unittest.TestCase):
    def test_every_gate_mapping_points_to_an_existing_script(self):
        wrapper = load_script("gate_wrapper.py")

        missing = {
            gate: script
            for gate, script in wrapper.GATE_SCRIPTS.items()
            if not (SCRIPTS / script).is_file()
        }

        self.assertEqual({}, missing)


class CliEntrypointTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            ["node", str(ROOT / "bin" / "cli.js"), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

    def test_version_matches_package_metadata(self):
        expected = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]
        result = self.run_cli("--version")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(expected, result.stdout.strip())

    def test_help_lists_public_entrypoints(self):
        result = self.run_cli("--help")

        self.assertEqual(0, result.returncode, result.stderr)
        for command in ("init-project", "doctor", "selftest", "route", "bootstrap"):
            self.assertIn(command, result.stdout)

    def test_bootstrap_is_read_only_and_deterministic(self):
        with tempfile.TemporaryDirectory(prefix="deliverhq-bootstrap-") as tmp:
            repo = Path(tmp)
            (repo / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (repo / "package.json").write_text(
                json.dumps({"name": "fixture", "scripts": {"test": "node --test"}}),
                encoding="utf-8",
            )
            before = sorted(path.relative_to(repo).as_posix() for path in repo.rglob("*"))
            first = self.run_cli("bootstrap", "--path", str(repo), "--json")
            second = self.run_cli("bootstrap", "--path", str(repo), "--json")
            after = sorted(path.relative_to(repo).as_posix() for path in repo.rglob("*"))

            self.assertEqual(0, first.returncode, first.stderr)
            self.assertEqual(0, second.returncode, second.stderr)
            self.assertEqual(before, after)
            first_payload = json.loads(first.stdout[first.stdout.find("{"):])
            second_payload = json.loads(second.stdout[second.stdout.find("{"):])
            self.assertEqual(first_payload, second_payload)
            self.assertEqual("npm run test", first_payload["report"]["commands"]["test"]["command"])

    def test_bootstrap_apply_never_overwrites_candidates(self):
        with tempfile.TemporaryDirectory(prefix="deliverhq-bootstrap-apply-") as tmp:
            repo = Path(tmp)
            home = repo / "DeliverHQ"
            home.mkdir()
            protected = home / "CONTEXT.candidate.md"
            protected.write_text("human\n", encoding="utf-8")
            result = self.run_cli(
                "bootstrap", "--path", str(repo), "--home", str(home), "--apply", "--json"
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("human\n", protected.read_text(encoding="utf-8"))
            payload = json.loads(result.stdout[result.stdout.find("{"):])
            conflicts = [item for item in payload["writes"] if item["status"] == "conflict"]
            self.assertTrue(conflicts)

    def test_bootstrap_rejects_home_outside_repository(self):
        with tempfile.TemporaryDirectory(prefix="deliverhq-bootstrap-scope-") as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            outside = Path(tmp) / "DeliverHQ"
            result = self.run_cli(
                "bootstrap", "--path", str(repo), "--home", str(outside), "--apply", "--json"
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("invalid_deliverhq_home", result.stdout)

    def test_bootstrap_apply_never_overwrites_canonical_context(self):
        with tempfile.TemporaryDirectory(prefix="deliverhq-bootstrap-canonical-") as tmp:
            repo = Path(tmp)
            home = repo / "DeliverHQ"
            home.mkdir()
            canonical = home / "CONTEXT.md"
            canonical.write_text("human canonical\n", encoding="utf-8")
            before = hashlib.sha256(canonical.read_bytes()).hexdigest()
            result = self.run_cli("bootstrap", "--path", str(repo), "--apply", "--json")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(before, hashlib.sha256(canonical.read_bytes()).hexdigest())

    def test_route_returns_machine_readable_decision(self):
        result = self.run_cli("route", "fix login bug", "--path", "skill", "--json")

        self.assertEqual(0, result.returncode, result.stderr)
        payload_start = result.stdout.find("{")
        self.assertGreaterEqual(payload_start, 0, result.stdout)
        payload = json.loads(result.stdout[payload_start:])
        self.assertIn(payload["lane"], {"quick", "standard", "strict", "legacy"})
        self.assertIn(payload["governance_lane"], {"fast", "standard", "high-risk", "legacy"})
        self.assertEqual("medium", payload["confidence"])
        self.assertIn("entry", payload)
        self.assertIn("required_gates", payload)
        self.assertIn("skipped_gates", payload)
        self.assertIn("estimated_cost", payload)
        self.assertEqual("medium", payload["estimated_cost"]["confidence"])
        self.assertFalse(set(payload["required_gates"]) & set(payload["skipped_gates"]))

    def test_route_cost_reflects_ui_and_schema_factors(self):
        result = self.run_cli("route", "design UI database migration", "--path", "skill", "--json")
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout[result.stdout.find("{"):])
        factors = payload["estimated_cost"]["factors"]
        self.assertIn("user-visible-ui:+20%", factors)
        self.assertIn("schema-change:+10%", factors)

    def test_token_budget_runs_without_utf8_environment_overrides(self):
        env = os.environ.copy()
        env.pop("PYTHONUTF8", None)
        env.pop("PYTHONIOENCODING", None)
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "token_budget.py")],
            cwd=SKILL,
            capture_output=True,
            timeout=30,
            env=env,
        )

        self.assertEqual(0, result.returncode, result.stderr.decode(errors="replace"))


class CommandConfigurationTests(unittest.TestCase):
    def assert_commands_are_unconfigured(self, content):
        commands = yaml.safe_load(content)
        for name in ("build", "test", "lint", "typecheck"):
            config = commands[name]
            self.assertFalse(config["enabled"], name)
            self.assertIsNone(config["command"], name)

    def test_packaged_commands_do_not_fake_success(self):
        self.assert_commands_are_unconfigured(
            (SKILL / "COMMANDS.yml").read_text(encoding="utf-8")
        )

    def test_generated_commands_do_not_assume_project_commands(self):
        init_project = load_script("init_project_structure.py")
        self.assert_commands_are_unconfigured(init_project.commands_content())


if __name__ == "__main__":
    unittest.main()
