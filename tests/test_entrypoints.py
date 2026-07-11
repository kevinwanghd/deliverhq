import importlib.util
import json
import os
import subprocess
import sys
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
        for command in ("init-project", "doctor", "selftest", "route"):
            self.assertIn(command, result.stdout)

    def test_route_returns_machine_readable_decision(self):
        result = self.run_cli("route", "fix login bug", "--path", "skill", "--json")

        self.assertEqual(0, result.returncode, result.stderr)
        payload_start = result.stdout.find("{")
        self.assertGreaterEqual(payload_start, 0, result.stdout)
        payload = json.loads(result.stdout[payload_start:])
        self.assertIn(payload["lane"], {"quick", "standard", "strict", "legacy"})
        self.assertIn("entry", payload)

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
