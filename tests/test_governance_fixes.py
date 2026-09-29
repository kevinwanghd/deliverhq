"""治理脚本缺陷修复的回归测试: 每个用例对应一个曾经的错误行为。"""
import contextlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GOV_SCRIPTS = ROOT / "governance" / "scripts"
DHQ_SCRIPTS = ROOT / "DeliverHQ" / "scripts"
if str(GOV_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(GOV_SCRIPTS))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=30,
    ).stdout


@contextlib.contextmanager
def temp_repo(commit=True, branch="main"):
    with tempfile.TemporaryDirectory(prefix="deliverhq-govfix-") as temp:
        repo = Path(temp)
        git(repo, "init", "-q", "-b", branch)
        git(repo, "config", "user.email", "t@example.com")
        git(repo, "config", "user.name", "t")
        git(repo, "config", "core.autocrlf", "false")
        if commit:
            (repo / "a.txt").write_text("base\n", encoding="utf-8")
            git(repo, "add", "a.txt")
            git(repo, "commit", "-q", "-m", "init")
        yield repo


@contextlib.contextmanager
def chdir(path):
    old = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


class HumanCheckpointConfigPathTests(unittest.TestCase):
    def test_default_config_points_to_repo_root(self):
        # 旧实现指向不存在的 DeliverHQ/governance.config.yml, 导致配置被静默忽略
        module = load_module("human_checkpoint_under_test", DHQ_SCRIPTS / "human_checkpoint.py")
        self.assertEqual(
            (ROOT / "governance.config.yml").resolve(),
            Path(module.DEFAULT_CONFIG_PATH).resolve(),
        )


class ReviewerAgentDiffTests(unittest.TestCase):
    def test_diff_includes_staged_and_untracked_chinese_changes(self):
        # 旧实现只看 unstaged diff, 且 cp936 下中文 diff 解码失败返回 None
        module = load_module("reviewer_agent_under_test", DHQ_SCRIPTS / "reviewer_agent.py")
        with temp_repo() as repo:
            (repo / "a.txt").write_text("已暂存的中文改动\n", encoding="utf-8")
            git(repo, "add", "a.txt")
            (repo / "new.py").write_text("# 未跟踪的中文文件\n", encoding="utf-8")

            diff = module.get_git_diff(repo)
            files = module.get_changed_files(repo)

        self.assertIn("已暂存的中文改动", diff)
        self.assertIn("未跟踪的中文文件", diff)
        self.assertEqual(["a.txt", "new.py"], sorted(files))


class DetectLargeChangeTests(unittest.TestCase):
    def test_missing_diff_base_fails_closed(self):
        # 旧实现在基准缺失时返回 (False, []), 让规模未知的变更绕过风险段落要求
        validate_mr = load_module("validate_mr_under_test", GOV_SCRIPTS / "validate_mr.py")
        cfg = {"large_change": {"line_threshold": 500}}
        with temp_repo() as repo, chdir(repo):
            is_large, reasons = validate_mr.detect_large_change(cfg, "origin/does-not-exist")

        self.assertTrue(is_large)
        self.assertTrue(any("无法计算 diff" in r for r in reasons), reasons)


class RepositoryStateTests(unittest.TestCase):
    def test_state_is_same_from_subdirectory_and_tracks_content(self):
        import governance_common

        with temp_repo() as repo:
            sub = repo / "pkg" / "inner"
            sub.mkdir(parents=True)
            (repo / "pkg" / "mod.py").write_text("x = 1\n", encoding="utf-8")
            with chdir(repo):
                from_root = governance_common.repository_state()
            with chdir(sub):
                from_sub = governance_common.repository_state()
            (repo / "pkg" / "mod.py").write_text("x = 2\n", encoding="utf-8")
            with chdir(sub):
                after_edit = governance_common.repository_state()

        self.assertEqual(from_root, from_sub)
        # 从子目录运行时也必须读到真实文件内容, 内容变化要反映到状态里
        self.assertNotEqual(from_sub, after_edit)


class RecordTestRunNoHeadTests(unittest.TestCase):
    def test_repo_without_head_records_no_head_state(self):
        with temp_repo(commit=False) as repo:
            evidence = repo / "ev.jsonl"
            result = subprocess.run(
                [sys.executable, str(GOV_SCRIPTS / "record_test_run.py"),
                 "--evidence", str(evidence), "--",
                 sys.executable, "-c", "print('1 passed')"],
                cwd=repo, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=60,
            )
            lines = evidence.read_text(encoding="utf-8").splitlines()
            records = [json.loads(line) for line in lines]

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("no-head", records[-1]["git_state"])


class DefaultTargetBranchTests(unittest.TestCase):
    def setUp(self):
        self.create_mr = load_module("create_mr_under_test", GOV_SCRIPTS / "create_mr.py")

    def test_prefers_origin_head(self):
        with temp_repo() as repo, chdir(repo):
            git(repo, "update-ref", "refs/remotes/origin/develop", "HEAD")
            git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/develop")
            self.assertEqual("develop", self.create_mr.default_target_branch())

    def test_falls_back_to_main_then_master(self):
        # 旧默认值硬编码 master, 在 main 仓库里会生成错误的 diff 基准和 MR 目标
        with temp_repo(branch="main") as repo, chdir(repo):
            self.assertEqual("main", self.create_mr.default_target_branch())
        with temp_repo(branch="master") as repo, chdir(repo):
            self.assertEqual("master", self.create_mr.default_target_branch())


if __name__ == "__main__":
    unittest.main()
