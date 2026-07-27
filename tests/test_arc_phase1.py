"""
ARC Phase 1 单元测试。

覆盖:
    - agent_adapter: BaseAdapter 接口、AgentRunResult、tail_lines
    - adapter_mock: MockAdapter、ConfigurableMockAdapter
    - session_pack_builder: build()、截断、缺失文件
    - evidence_verifier: verify()、路径解析、文件范围检查
    - recovery_manager: 失败分类、假设生成
"""
import importlib.util
import sys
import tempfile
import unittest
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skill" / "scripts"


def load_script(name):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec.loader.exec_module(module)
    finally:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
    return module


# ---------------------------------------------------------------------------
# agent_adapter tests
# ---------------------------------------------------------------------------

class TestAgentRunResult(unittest.TestCase):
    def setUp(self):
        self.m = load_script("agent_adapter.py")

    def test_dataclass_fields(self):
        result = self.m.AgentRunResult(
            run_id="T1-r1",
            exit_kind="success",
            exit_code=0,
            elapsed_seconds=1.5,
            stdout_tail="output",
            stderr_tail="",
            adapter_name="mock",
        )
        self.assertEqual("T1-r1", result.run_id)
        self.assertEqual("success", result.exit_kind)
        self.assertEqual(0, result.exit_code)
        self.assertEqual(1.5, result.elapsed_seconds)
        self.assertEqual("output", result.stdout_tail)
        self.assertEqual("mock", result.adapter_name)

    def test_no_claimed_done_field(self):
        # claimed_done 已删除，不应该存在
        result = self.m.AgentRunResult(
            run_id="T1-r1", exit_kind="success", exit_code=0,
            elapsed_seconds=0.1, stdout_tail="", stderr_tail="", adapter_name="mock",
        )
        self.assertFalse(hasattr(result, "claimed_done"))

    def test_tail_lines_basic(self):
        text = "line1\nline2\nline3\nline4\nline5"
        result = self.m.tail_lines(text, 3)
        self.assertEqual("line3\nline4\nline5", result)

    def test_tail_lines_fewer_than_n(self):
        text = "line1\nline2"
        result = self.m.tail_lines(text, 10)
        self.assertEqual("line1\nline2", result)

    def test_tail_lines_empty(self):
        self.assertEqual("", self.m.tail_lines("", 5))

    def test_base_adapter_is_abstract(self):
        from abc import ABC
        self.assertTrue(issubclass(self.m.BaseAdapter, ABC))

    def test_base_adapter_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            self.m.BaseAdapter()


# ---------------------------------------------------------------------------
# adapter_mock tests
# ---------------------------------------------------------------------------

class TestMockAdapter(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(SCRIPTS))
        self.m = load_script("adapter_mock.py")

    def tearDown(self):
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))

    def test_name(self):
        adapter = self.m.MockAdapter()
        self.assertEqual("mock", adapter.name())

    def test_run_returns_success(self):
        adapter = self.m.MockAdapter()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            session_pack = tmp / "T1-r1.md"
            session_pack.write_text("# Session Pack — T1-r1\n")
            worktree = tmp / "worktree"
            worktree.mkdir()

            result = adapter.run(session_pack, worktree, run_id="T1-r1")

            self.assertEqual("success", result.exit_kind)
            self.assertEqual(0, result.exit_code)
            self.assertEqual("T1-r1", result.run_id)
            self.assertEqual("mock", result.adapter_name)

    def test_run_creates_agent_result_yml(self):
        adapter = self.m.MockAdapter()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            session_pack = tmp / "T2-r3.md"
            session_pack.write_text("# Session Pack — T2-r3\n")
            worktree = tmp / "worktree"
            worktree.mkdir()

            adapter.run(session_pack, worktree, run_id="T2-r3")

            result_yml = worktree / "agent-result.yml"
            self.assertTrue(result_yml.exists(), "agent-result.yml must be in worktree root")
            content = result_yml.read_text()
            self.assertIn("task_id: T2", content)
            self.assertIn("status: done", content)

    def test_run_extracts_task_id_from_run_id(self):
        adapter = self.m.MockAdapter()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            session_pack = tmp / "T5-r2.md"
            session_pack.write_text("# Session Pack — T5-r2\n")
            worktree = tmp / "worktree"
            worktree.mkdir()

            adapter.run(session_pack, worktree, run_id="T5-r2")

            content = (worktree / "agent-result.yml").read_text()
            self.assertIn("task_id: T5", content)

    def test_run_creates_mock_output_txt(self):
        adapter = self.m.MockAdapter()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            session_pack = tmp / "T1-r1.md"
            session_pack.write_text("# Session Pack\n")
            worktree = tmp / "worktree"
            worktree.mkdir()

            adapter.run(session_pack, worktree, run_id="T1-r1")

            self.assertTrue((worktree / "mock-output.txt").exists())

    def test_configurable_mock_timeout(self):
        adapter = self.m.ConfigurableMockAdapter(exit_kind="timeout", exit_code=-1)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            session_pack = tmp / "T1-r1.md"
            session_pack.write_text("# Session Pack\n")
            worktree = tmp / "worktree"
            worktree.mkdir()

            result = adapter.run(session_pack, worktree, run_id="T1-r1")

            self.assertEqual("timeout", result.exit_kind)
            self.assertEqual(-1, result.exit_code)

    def test_configurable_mock_no_result_yml(self):
        adapter = self.m.ConfigurableMockAdapter(write_result_yml=False)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            session_pack = tmp / "T1-r1.md"
            session_pack.write_text("# Session Pack\n")
            worktree = tmp / "worktree"
            worktree.mkdir()

            adapter.run(session_pack, worktree, run_id="T1-r1")

            self.assertFalse((worktree / "agent-result.yml").exists())


# ---------------------------------------------------------------------------
# session_pack_builder tests
# ---------------------------------------------------------------------------

class TestSessionPackBuilder(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(SCRIPTS))
        self.m = load_script("session_pack_builder.py")

    def tearDown(self):
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))

    def _make_cr(self, tmp: Path, goal="Test goal", files=None, covers=None):
        """Create a minimal CR directory."""
        files = files or ["test.py"]
        covers = covers or ["AC-1"]
        (tmp / "plan.yml").write_text(yaml.dump({
            "tasks": [{
                "task_id": "T1",
                "goal": goal,
                "verify": "echo test",
                "done": "Test complete",
                "files": files,
                "covers": covers,
            }]
        }), encoding="utf-8")
        (tmp / "acceptance-spec.md").write_text("- AC-1: First acceptance criterion\n")
        (tmp / "context-summary.md").write_text("# Context\nSome context\n")

    def test_build_creates_session_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self._make_cr(tmp)

            pack = self.m.build(tmp, "T1", "T1-r1")

            self.assertTrue(pack.exists())
            self.assertEqual("T1-r1.md", pack.name)

    def test_build_pack_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self._make_cr(tmp)

            pack = self.m.build(tmp, "T1", "T1-r1")

            expected = tmp / "runtime" / "session-packs" / "T1-r1.md"
            self.assertEqual(expected, pack)

    def test_build_contains_task_id_and_run_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self._make_cr(tmp)

            pack = self.m.build(tmp, "T1", "T1-r1")
            content = pack.read_text()

            self.assertIn("task_id: T1", content)
            self.assertIn("run_id: T1-r1", content)

    def test_build_contains_goal(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self._make_cr(tmp, goal="Implement feature X")

            pack = self.m.build(tmp, "T1", "T1-r1")
            content = pack.read_text()

            self.assertIn("Implement feature X", content)

    def test_build_contains_file_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self._make_cr(tmp, files=["src/foo.py", "tests/test_foo.py"])

            pack = self.m.build(tmp, "T1", "T1-r1")
            content = pack.read_text()

            self.assertIn("src/foo.py", content)
            self.assertIn("tests/test_foo.py", content)

    def test_build_contains_required_output_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self._make_cr(tmp)

            pack = self.m.build(tmp, "T1", "T1-r1")
            content = pack.read_text()

            self.assertIn("Required Output", content)
            self.assertIn("agent-result.yml", content)
            self.assertIn("status: done", content)

    def test_build_missing_plan_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            with self.assertRaises(ValueError):
                self.m.build(tmp, "T1", "T1-r1")

    def test_build_missing_task_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self._make_cr(tmp)
            with self.assertRaises(ValueError):
                self.m.build(tmp, "T99", "T99-r1")

    def test_build_contains_input_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self._make_cr(tmp)

            pack = self.m.build(tmp, "T1", "T1-r1")
            content = pack.read_text()

            self.assertIn("input_hash: sha256:", content)
            self.assertNotIn("input_hash: <pending>", content)

    def test_build_idempotent_hash(self):
        """同样输入生成相同哈希（SOURCE_DATE_EPOCH 固定时）。"""
        import os
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self._make_cr(tmp)

            os.environ["SOURCE_DATE_EPOCH"] = "1700000000"
            try:
                pack1 = self.m.build(tmp, "T1", "T1-r1")
                hash1 = [l for l in pack1.read_text().splitlines() if "input_hash" in l][0]

                # rebuild (overwrite)
                pack2 = self.m.build(tmp, "T1", "T1-r1")
                hash2 = [l for l in pack2.read_text().splitlines() if "input_hash" in l][0]

                self.assertEqual(hash1, hash2)
            finally:
                del os.environ["SOURCE_DATE_EPOCH"]


# ---------------------------------------------------------------------------
# evidence_verifier tests
# ---------------------------------------------------------------------------

class TestEvidenceVerifier(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(SCRIPTS))
        self.m = load_script("evidence_verifier.py")

    def tearDown(self):
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))

    def _make_cr(self, tmp: Path, worktree: Path, write_result_yml=True, files=None):
        (tmp / "state.yml").write_text(
            yaml.dump({"worktree_path": str(worktree)}), encoding="utf-8"
        )
        (tmp / "plan.yml").write_text(yaml.dump({
            "tasks": [{"task_id": "T1", "files": files or ["test.py"]}]
        }), encoding="utf-8")
        if write_result_yml:
            (worktree / "agent-result.yml").write_text(yaml.dump({
                "task_id": "T1",
                "status": "done",
                "changed_files": ["test.py"],
                "test_command": "echo test",
            }), encoding="utf-8")

    def test_no_worktree_path_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "state.yml").write_text("worktree_path: null\n")
            passed, details = self.m.verify(tmp, "T1", "T1-r1")
            self.assertFalse(passed)
            self.assertTrue(any("worktree" in b for b in details["blockers"]))

    def test_missing_state_yml_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            passed, details = self.m.verify(tmp, "T1", "T1-r1")
            self.assertFalse(passed)

    def test_missing_agent_result_yml_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            worktree = tmp / "worktree"
            worktree.mkdir()
            self._make_cr(tmp, worktree, write_result_yml=False)

            passed, details = self.m.verify(tmp, "T1", "T1-r1")

            self.assertFalse(passed)
            self.assertTrue(any("agent-result.yml" in b for b in details["blockers"]))

    def test_out_of_scope_file_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            worktree = tmp / "worktree"
            worktree.mkdir()

            # Only test.py allowed, but changed other.py too
            (tmp / "state.yml").write_text(
                yaml.dump({"worktree_path": str(worktree)}), encoding="utf-8"
            )
            (tmp / "plan.yml").write_text(yaml.dump({
                "tasks": [{"task_id": "T1", "files": ["test.py"]}]
            }), encoding="utf-8")
            (worktree / "agent-result.yml").write_text(yaml.dump({
                "task_id": "T1",
                "status": "done",
                "changed_files": ["test.py", "other.py"],  # out of scope
                "test_command": "echo test",
            }), encoding="utf-8")

            passed, details = self.m.verify(tmp, "T1", "T1-r1")

            self.assertFalse(passed)
            self.assertTrue(any("范围" in b or "scope" in b.lower() for b in details["blockers"]))

    def test_verify_returns_structured_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            worktree = tmp / "worktree"
            worktree.mkdir()
            self._make_cr(tmp, worktree)

            passed, details = self.m.verify(tmp, "T1", "T1-r1")

            self.assertIn("blockers", details)
            self.assertIn("warnings", details)
            self.assertIn("evidence_paths", details)

    def test_agent_result_read_from_worktree_not_cr_root(self):
        """agent-result.yml 必须在 worktree，不是 CR 根目录。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            worktree = tmp / "worktree"
            worktree.mkdir()

            # Only put agent-result.yml in CR root (wrong location)
            (tmp / "state.yml").write_text(
                yaml.dump({"worktree_path": str(worktree)}), encoding="utf-8"
            )
            (tmp / "agent-result.yml").write_text("task_id: T1\nstatus: done\n")
            # worktree has NO agent-result.yml

            passed, details = self.m.verify(tmp, "T1", "T1-r1")

            self.assertFalse(passed)
            self.assertTrue(any("agent-result.yml" in b for b in details["blockers"]))


# ---------------------------------------------------------------------------
# recovery_manager tests
# ---------------------------------------------------------------------------

class TestRecoveryManager(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(SCRIPTS))
        self.m = load_script("recovery_manager.py")

    def tearDown(self):
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))

    def test_classify_timeout(self):
        cls = self.m._classify_failure({"exit_kind": "timeout"})
        self.assertEqual(self.m.RecoveryClass.TIMEOUT, cls)

    def test_classify_no_evidence(self):
        cls = self.m._classify_failure({
            "blockers": ["agent-result.yml 不存在，agent 未产出声明"]
        })
        self.assertEqual(self.m.RecoveryClass.NO_EVIDENCE, cls)

    def test_classify_anti_gaming(self):
        cls = self.m._classify_failure({
            "blockers": ["anti_gaming_check 失败: 检测到删除测试"]
        })
        self.assertEqual(self.m.RecoveryClass.ANTI_GAMING, cls)

    def test_classify_out_of_scope(self):
        cls = self.m._classify_failure({
            "blockers": ["文件范围检查失败: 改动了范围外文件: other.py"]
        })
        self.assertEqual(self.m.RecoveryClass.OUT_OF_SCOPE, cls)

    def test_classify_test_failure(self):
        cls = self.m._classify_failure({
            "blockers": ["verification-manifest 检查失败: test command not found"]
        })
        self.assertEqual(self.m.RecoveryClass.TEST_FAILURE, cls)

    def test_classify_unknown(self):
        cls = self.m._classify_failure({"exit_kind": "error"})
        self.assertEqual(self.m.RecoveryClass.UNKNOWN, cls)

    def test_generate_hypothesis_timeout(self):
        hyp = self.m._generate_hypothesis(self.m.RecoveryClass.TIMEOUT, {})
        self.assertIn("超时", hyp)

    def test_generate_hypothesis_no_evidence(self):
        hyp = self.m._generate_hypothesis(self.m.RecoveryClass.NO_EVIDENCE, {})
        self.assertIn("agent-result.yml", hyp)

    def test_recovery_class_values(self):
        self.assertEqual("arc:timeout", self.m.RecoveryClass.TIMEOUT.value)
        self.assertEqual("arc:no_evidence", self.m.RecoveryClass.NO_EVIDENCE.value)
        self.assertEqual("arc:anti_gaming", self.m.RecoveryClass.ANTI_GAMING.value)


# ---------------------------------------------------------------------------
# adapter_claude_code tests
# ---------------------------------------------------------------------------

class TestClaudeCodeAdapter(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(SCRIPTS))
        self.m = load_script("adapter_claude_code.py")

    def tearDown(self):
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))

    def test_name(self):
        adapter = self.m.ClaudeCodeAdapter()
        self.assertEqual("claude-code", adapter.name())

    def test_default_command(self):
        adapter = self.m.ClaudeCodeAdapter()
        self.assertEqual(["claude", "-p"], adapter.command)

    def test_custom_command(self):
        adapter = self.m.ClaudeCodeAdapter(command=["codex", "--input"])
        self.assertEqual(["codex", "--input"], adapter.command)

    def test_no_claimed_done_in_result(self):
        """ClaudeCodeAdapter 返回的 AgentRunResult 不应有 claimed_done 字段。"""
        import subprocess
        import unittest.mock as mock

        adapter = self.m.ClaudeCodeAdapter()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            session_pack = tmp / "T1-r1.md"
            session_pack.write_text("# Session Pack\n")
            worktree = tmp / "worktree"
            worktree.mkdir()

            # Mock subprocess.run to avoid needing claude CLI
            mock_result = mock.MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "DONE"
            mock_result.stderr = ""

            with mock.patch("subprocess.run", return_value=mock_result):
                result = adapter.run(session_pack, worktree, run_id="T1-r1", timeout=10)

            self.assertFalse(hasattr(result, "claimed_done"))
            self.assertEqual("success", result.exit_kind)
            self.assertEqual("claude-code", result.adapter_name)

    def test_timeout_returns_timeout_exit_kind(self):
        import subprocess
        import unittest.mock as mock

        adapter = self.m.ClaudeCodeAdapter()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            session_pack = tmp / "T1-r1.md"
            session_pack.write_text("# Session Pack\n")
            worktree = tmp / "worktree"
            worktree.mkdir()

            with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 10)):
                result = adapter.run(session_pack, worktree, run_id="T1-r1", timeout=10)

            self.assertEqual("timeout", result.exit_kind)
            self.assertEqual(-1, result.exit_code)


if __name__ == "__main__":
    unittest.main()
