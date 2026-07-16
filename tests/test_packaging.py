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
        # 开发资产已物理移到仓库根 dev/（不在 skill/ 内，天然不进包）。
        # _archived/ 现作为空运行时目录随包发布（check_skeleton 需要该目录），
        # 其历史脚本已移入 dev/archived-scripts/，故不再列入禁发前缀。
        forbidden_prefixes = (
            "skill/change-requests/CR-001/",
            "skill/change-requests/CR-002/",
            "skill/change-requests/CR-003/",
            "skill/change-requests/CR-004/",
            "skill/change-requests/CR-005/",
            "skill/change-requests/CR-EXAMPLE/",
            "skill/change-requests/CR-BLOCKED-EXAMPLE/",
            "skill/docs/superpowers/",
            "skill/examples/",
            "skill/evals/",
            "skill/scripts/selftest.py",
            "skill/scripts/selftest_contracts/",
            "skill/scripts/eval_routing.py",
            "skill/scripts/gate_contract_check.py",
            "dev/",
        )
        offenders = sorted(
            path for path in self.files if any(path.startswith(prefix) for prefix in forbidden_prefixes)
        )

        self.assertEqual([], offenders)

    def test_required_runtime_files_are_packaged(self):
        required = {
            "bin/cli.js",
            "skill/SKILL.md",
            "skill/scripts/health_check.py",
            "skill/deliverhq/__init__.py",
            "skill/capabilities.yml",
            "skill/structure-profiles/governance-only.yml",
            "skill/structure-profiles/fullstack-web.yml",
            "skill/change-requests/CR-TEMPLATE/request.md",
        }

        self.assertEqual(set(), required - self.files)


if __name__ == "__main__":
    unittest.main()
