import importlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS))


class WorktreeManagerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = importlib.import_module("worktree_manager")

    def manager(self):
        temp = tempfile.TemporaryDirectory(prefix="deliverhq-worktree-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / ".git").mkdir()
        return self.module.WorktreeManager(str(root))

    def test_invalid_cr_id_is_rejected_before_git(self):
        manager = self.manager()
        manager._run_git = mock.Mock()

        for invalid in ("CR001", "cr-001", "CR-", "CR-A_B", "CR-../X"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    manager.create(invalid)

        manager._run_git.assert_not_called()

    def test_default_base_branch_is_discovered_from_head(self):
        manager = self.manager()
        calls = []

        def fake_git(args, cwd=None):
            calls.append(args)
            if args == ["symbolic-ref", "--quiet", "--short", "HEAD"]:
                return subprocess.CompletedProcess(args, 0, "main\n", "")
            return subprocess.CompletedProcess(args, 0, "", "")

        manager._run_git = fake_git
        info = manager.create("CR-007")

        self.assertEqual("feature/CR-007", info.branch)
        add_call = next(args for args in calls if args[:2] == ["worktree", "add"])
        self.assertEqual("main", add_call[-1])

    def test_semantic_example_ids_remain_supported(self):
        manager = self.manager()
        manager._run_git = lambda args, cwd=None: subprocess.CompletedProcess(args, 0, "main\n", "")

        info = manager.create("CR-BLOCKED-EXAMPLE")

        self.assertEqual("CR-BLOCKED-EXAMPLE", info.cr_id)


if __name__ == "__main__":
    unittest.main()
