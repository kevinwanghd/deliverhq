import importlib
import os
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

    def test_registry_path_is_anchored_to_project_root_not_cwd(self):
        manager = self.manager()
        manager._run_git = lambda args, cwd=None: subprocess.CompletedProcess(args, 0, "main\n", "")
        elsewhere = tempfile.TemporaryDirectory(prefix="deliverhq-cwd-")
        self.addCleanup(elsewhere.cleanup)
        old_cwd = os.getcwd()
        os.chdir(elsewhere.name)
        self.addCleanup(os.chdir, old_cwd)

        info = manager.create("CR-008")

        expected = (manager.project_root / ".claude" / "worktrees" / "CR-008").resolve()
        self.assertEqual(expected, Path(info.path))
        self.assertEqual(str(expected), manager._load_registry()["CR-008"].path)

    def test_git_worktree_add_failure_raises_and_is_not_registered(self):
        manager = self.manager()

        def fake_git(args, cwd=None):
            if args[:2] == ["worktree", "add"]:
                return subprocess.CompletedProcess(args, 128, "", "fatal: branch exists")
            return subprocess.CompletedProcess(args, 0, "main\n", "")

        manager._run_git = fake_git
        with self.assertRaisesRegex(RuntimeError, "branch exists"):
            manager.create("CR-009")
        self.assertNotIn("CR-009", manager._load_registry())

    def test_active_registry_entry_blocks_duplicate_create(self):
        manager = self.manager()
        manager._run_git = lambda args, cwd=None: subprocess.CompletedProcess(args, 0, "main\n", "")
        manager.create("CR-010")

        with self.assertRaisesRegex(RuntimeError, "already exists"):
            manager.create("CR-010")

    def test_max_worktrees_limit_is_enforced(self):
        manager = self.manager()
        manager._run_git = lambda args, cwd=None: subprocess.CompletedProcess(args, 0, "main\n", "")
        manager.config.max_worktrees = 2
        manager.create("CR-011")
        manager.create("CR-012")

        with self.assertRaisesRegex(RuntimeError, "Maximum worktrees limit"):
            manager.create("CR-013")
        self.assertNotIn("CR-013", manager._load_registry())


if __name__ == "__main__":
    unittest.main()
