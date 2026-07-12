import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NpmPackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        if npm is None:
            raise AssertionError("npm executable was not found")
        result = subprocess.run(
            [npm, "pack", "--dry-run", "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        cls.pack = payload[0]
        cls.files = {item["path"].replace("\\", "/") for item in cls.pack["files"]}

    def test_packaged_file_budget_is_enforced(self):
        self.assertLessEqual(len(self.files), 260)
        self.assertLessEqual(self.pack["unpackedSize"], 1_200_000)

    def test_internal_working_material_is_excluded(self):
        forbidden_prefixes = (
            "skill/change-requests/CR-001/",
            "skill/change-requests/CR-002/",
            "skill/change-requests/CR-003/",
            "skill/change-requests/CR-004/",
            "skill/change-requests/CR-005/",
            "skill/_archived/",
            "skill/docs/superpowers/",
            "skill/examples/self-development/",
        )
        offenders = sorted(
            path for path in self.files if any(path.startswith(prefix) for prefix in forbidden_prefixes)
        )

        self.assertEqual([], offenders)

    def test_required_runtime_files_are_packaged(self):
        required = {
            "bin/cli.js",
            "skill/SKILL.md",
            "skill/scripts/selftest.py",
            "skill/deliverhq/__init__.py",
            "skill/capabilities.yml",
            "skill/change-requests/CR-TEMPLATE/request.md",
            "skill/change-requests/CR-EXAMPLE/request.md",
            "skill/change-requests/CR-BLOCKED-EXAMPLE/README.md",
        }

        self.assertEqual(set(), required - self.files)


if __name__ == "__main__":
    unittest.main()
