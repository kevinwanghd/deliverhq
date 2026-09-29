"""skill/scripts 运行时缺陷修复的回归测试。

每个用例对应一个已验证缺陷：修复被回退时应当失败。
"""
import importlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

common = importlib.import_module("common")
retry_guard = importlib.import_module("retry_guard")
recovery_manager = importlib.import_module("recovery_manager")
baseline_comparison = importlib.import_module("baseline_comparison")
evidence_verifier = importlib.import_module("evidence_verifier")
confirm_reverse_spec = importlib.import_module("confirm_reverse_spec")

SUBPROCESS_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}


def make_tmp(test):
    temp_dir = tempfile.TemporaryDirectory(prefix="deliverhq-fix-")
    test.addCleanup(temp_dir.cleanup)
    return Path(temp_dir.name)


def write_ledger(cr, entries):
    path = cr / "evidence" / "retry-ledger.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"entries": entries}, allow_unicode=True), encoding="utf-8")
    return path


class RecordRetryAllowsUpToCapTests(unittest.TestCase):
    """缺陷1：同类失败的假设只依赖类别，第 2 次就被判为原地重复，重试上限形同 1。"""

    def test_same_failure_class_can_retry_until_cap(self):
        cr = make_tmp(self)
        details = {"exit_kind": "timeout", "blockers": []}

        results = [recovery_manager.record_retry(cr, "T1", details)[0] for _ in range(3)]

        # 默认 max_retries=3：前两次可继续，第三次耗尽转人工
        self.assertEqual([True, True, False], results)
        ledger = yaml.safe_load((cr / "evidence" / "retry-ledger.yml").read_text(encoding="utf-8"))
        hypotheses = [e["hypothesis"] for e in ledger["entries"]]
        self.assertEqual(3, len(set(hypotheses)), "每次尝试的假设必须带序号/失败摘要而互不相同")

    def test_manual_repeat_hypothesis_still_rejected(self):
        cr = make_tmp(self)
        with redirect_stdout(io.StringIO()):
            self.assertTrue(retry_guard.record_failure(cr, "QualityGate", "单元测试失败", "h1")[0])
            ok, reason = retry_guard.record_failure(cr, "QualityGate", "单元测试失败", "h1")
        self.assertFalse(ok)
        self.assertEqual("repeat_hypothesis", reason)


class LoadYamlTests(unittest.TestCase):
    """缺陷2/3：路径字符串被当 YAML 文本解析；非映射顶层原样返回；load_yaml_all 异常返回 {}。"""

    def test_missing_windows_absolute_path_returns_empty_dict(self):
        self.assertEqual({}, common.load_yaml(r"D:\definitely-missing\state.yml"))
        self.assertEqual({}, common.load_yaml("sub/dir/state.yml"))

    def test_non_mapping_top_level_returns_empty_dict(self):
        tmp = make_tmp(self)
        f = tmp / "list.yml"
        f.write_text("- a\n- b\n", encoding="utf-8")
        self.assertEqual({}, common.load_yaml(f))
        self.assertEqual({}, common.load_yaml("- a\n- b\n"))
        self.assertEqual({}, common.load_yaml("just-a-word"))

    def test_existing_file_and_yaml_text_still_parse(self):
        tmp = make_tmp(self)
        f = tmp / "ok.yml"
        f.write_text("name: 中文\n", encoding="utf-8")
        self.assertEqual({"name": "中文"}, common.load_yaml(f))
        self.assertEqual({"name": "中文"}, common.load_yaml(str(f)))
        self.assertEqual({"a": 1}, common.load_yaml("a: 1"))
        self.assertEqual({"a": 1, "b": 2}, common.load_yaml("a: 1\nb: 2\n"))

    def test_open_file_object_is_parsed(self):
        # create_sub_cr/gate_cache/lazy_load 等传入已打开文件；此前恒返回 {}，
        # 导致配置从未生效、gate_cache 回写时覆盖掉 state.yml 原有字段
        tmp = make_tmp(self)
        f = tmp / "state.yml"
        f.write_text("status: DEV\nname: 中文\n", encoding="utf-8")
        with open(f, "r", encoding="utf-8") as fh:
            self.assertEqual({"status": "DEV", "name": "中文"}, common.load_yaml(fh))

    def test_load_yaml_all_failure_returns_list(self):
        self.assertEqual([], common.load_yaml_all(12345))  # 非路径类型走通用异常分支
        self.assertEqual([{"a": 1}, {"b": 2}], common.load_yaml_all("a: 1\n---\nb: 2\n"))


class RetryLedgerFailClosedTests(unittest.TestCase):
    """缺陷4：损坏账本被静默当成空账本，下一次保存覆盖历史。"""

    def test_corrupt_ledger_is_backed_up_and_fails_closed(self):
        cr = make_tmp(self)
        ledger = cr / "evidence" / "retry-ledger.yml"
        ledger.parent.mkdir(parents=True)
        original = "entries: [ {signature: broken\n"
        ledger.write_text(original, encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "retry_guard.py"), str(cr), "record",
             "--gate", "QualityGate", "--blocker", "单元测试失败", "--hypothesis", "h"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", env=SUBPROCESS_ENV, timeout=60,
        )

        self.assertEqual(2, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual(original, ledger.read_text(encoding="utf-8"), "损坏账本不得被覆盖")
        backups = list(ledger.parent.glob("retry-ledger.yml.corrupt-*"))
        self.assertEqual(1, len(backups))
        self.assertEqual(original, backups[0].read_text(encoding="utf-8"))

    def test_non_mapping_ledger_raises(self):
        cr = make_tmp(self)
        ledger = cr / "evidence" / "retry-ledger.yml"
        ledger.parent.mkdir(parents=True)
        ledger.write_text("- a\n- b\n", encoding="utf-8")
        with self.assertRaises(retry_guard.LedgerCorruptError):
            retry_guard.load_ledger(cr)

    def test_missing_ledger_is_empty(self):
        self.assertEqual({"entries": []}, retry_guard.load_ledger(make_tmp(self)))


class RetryStatusScopedToTaskTests(unittest.TestCase):
    """缺陷5：status 输出里任何任务出现 needs_human 都会让本任务转人工。"""

    @staticmethod
    def entries(sig, count):
        return [{"signature": sig, "gate": sig.split("::")[0], "blocker": "b", "hypothesis": f"h{i}",
                 "attempt": i + 1, "timestamp": "2026-09-29T00:00:00"} for i in range(count)]

    def test_other_task_exhausted_does_not_block_this_task(self):
        cr = make_tmp(self)
        write_ledger(cr, self.entries("arc:T2::timeout", 3) + self.entries("arc:T10::timeout", 3)
                     + self.entries("arc:T1::timeout", 1))
        ok, reason = recovery_manager._call_retry_guard(cr, "T1", recovery_manager.RecoveryClass.TIMEOUT, "h")
        self.assertTrue(ok, reason)

    def test_this_task_exhausted_blocks(self):
        cr = make_tmp(self)
        write_ledger(cr, self.entries("arc:T1::timeout", 3))
        ok, reason = recovery_manager._call_retry_guard(cr, "T1", recovery_manager.RecoveryClass.TIMEOUT, "h")
        self.assertFalse(ok)
        self.assertIn("arc:T1::", reason)


class StashFailureEscalatesTests(unittest.TestCase):
    """现场未能 stash 时不得回 READY：重试会在残留产出上运行，证据基线失真。"""

    DETAILS = {"exit_kind": "error", "blockers": ["agent-result.yml 不存在"]}

    def _handle(self, stash_result):
        from unittest import mock
        cr = make_tmp(self)
        with mock.patch.object(recovery_manager, "_call_retry_guard", return_value=(True, "ok")), \
                mock.patch.object(recovery_manager, "_git_stash", return_value=stash_result):
            return recovery_manager.handle(cr, "T1", "run-1", self.DETAILS)

    def test_stash_failure_needs_human(self):
        state, reason = self._handle((False, "git stash 失败: index.lock exists"))
        self.assertEqual("NEEDS_HUMAN", state)
        self.assertIn("index.lock", reason)

    def test_stash_success_or_clean_tree_stays_ready(self):
        self.assertEqual("READY", self._handle((True, "已 stash 现场: arc-recovery:run-1"))[0])
        self.assertEqual("READY", self._handle((True, "无改动，跳过 stash"))[0])


class BaselineRunCommandTests(unittest.TestCase):
    """缺陷6：超时/命令不存在直接抛异常中断整个 baseline；路径白名单用字符串前缀。"""

    def test_missing_command_is_reported_not_raised(self):
        result = baseline_comparison._run_command("x", "test", "definitely-not-a-real-cmd-xyz --v", ".", 10)
        self.assertFalse(result.success)
        self.assertEqual(-1, result.returncode)
        self.assertIn("无法执行", result.stderr)

    def test_timeout_is_reported_not_raised(self):
        command = f'"{sys.executable}" -c "import time; time.sleep(10)"'
        result = baseline_comparison._run_command("slow", "test", command, ".", 1)
        self.assertFalse(result.success)
        self.assertIn("超时", result.stderr)

    def test_sibling_directory_with_common_prefix_is_not_within_root(self):
        tmp = make_tmp(self)
        self.assertFalse(baseline_comparison._is_within(tmp / "repo2", tmp / "repo"))
        self.assertTrue(baseline_comparison._is_within(tmp / "repo" / "sub", tmp / "repo"))
        if os.name == "nt":
            upper = Path(str(tmp / "repo" / "Sub").upper())
            self.assertTrue(baseline_comparison._is_within(upper, tmp / "repo"))


class SplitCommandTests(unittest.TestCase):
    """缺陷7：Windows 下 shlex POSIX 模式吃掉反斜杠（tests\\unit → testsunit）。"""

    @unittest.skipUnless(os.name == "nt", "Windows 专属行为")
    def test_windows_backslashes_and_quotes(self):
        self.assertEqual(["pytest", r"tests\unit"], common.split_command(r"pytest tests\unit"))
        self.assertEqual([r"C:\Program Files\Python\python.exe", "-m", "pytest"],
                         common.split_command(r'"C:\Program Files\Python\python.exe" -m pytest'))

    @unittest.skipIf(os.name == "nt", "POSIX 专属行为")
    def test_posix_quotes(self):
        self.assertEqual(["python", "-c", "print(1)"], common.split_command("python -c 'print(1)'"))

    def test_list_passthrough(self):
        self.assertEqual(["a", "b"], common.split_command(["a", "b"]))


def _git(repo, *args):
    subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
                   cwd=str(repo), check=True, capture_output=True, timeout=30)


class PorcelainParsingTests(unittest.TestCase):
    """缺陷12：porcelain 输出对中文/空格路径加引号，按行切分后路径对不上。"""

    def test_parse_porcelain_z_handles_rename_and_spaces(self):
        out = "R  new name.py\0old name.py\0?? 中文 文件.txt\0 M src/a.py\0"
        self.assertEqual(["new name.py", "中文 文件.txt", "src/a.py"], common.parse_porcelain_z(out))

    def test_git_files_reports_unquoted_unicode_paths(self):
        repo = make_tmp(self)
        try:
            _git(repo, "init", "-q")
        except (OSError, subprocess.CalledProcessError) as exc:
            self.skipTest(f"git 不可用: {exc}")
        (repo / "old.txt").write_text("x\n", encoding="utf-8")
        _git(repo, "add", "old.txt")
        _git(repo, "commit", "-q", "-m", "init")
        _git(repo, "mv", "old.txt", "改名 后.txt")
        (repo / "新 文件.txt").write_text("y\n", encoding="utf-8")

        files = evidence_verifier._git_files(repo)

        self.assertIsNotNone(files)
        self.assertIn("改名 后.txt", files)
        self.assertIn("新 文件.txt", files)
        self.assertFalse(any(f.startswith('"') for f in files), files)


class ReverseSpecTimeoutTests(unittest.TestCase):
    """缺陷13：created_at 为 datetime / 带时区字符串时 TypeError 被静默吞掉。"""

    @staticmethod
    def data(created):
        return {"candidates": [{"id": "RC-1", "review_required": True, "source": {"module": "m"},
                                "human_decision": {"status": "unconfirmed", "created_at": created}}]}

    def ids(self, created):
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = confirm_reverse_spec.check_timeout(self.data(created), timeout_hours=48)
        return [r[0] for r in result], buf.getvalue()

    def test_accepts_datetime_and_timezone_strings(self):
        old = datetime.now(timezone.utc) - timedelta(hours=100)
        self.assertEqual(["RC-1"], self.ids(old)[0])  # PyYAML 解析出的 aware datetime
        self.assertEqual(["RC-1"], self.ids(old.replace(tzinfo=None) - timedelta(hours=24))[0])  # naive
        self.assertEqual(["RC-1"], self.ids(old.strftime("%Y-%m-%dT%H:%M:%SZ"))[0])
        self.assertEqual(["RC-1"], self.ids(old.isoformat())[0])
        self.assertEqual([], self.ids(datetime.now(timezone.utc).isoformat())[0])

    def test_unparseable_created_at_warns(self):
        ids, output = self.ids("not-a-date")
        self.assertEqual([], ids)
        self.assertIn("RC-1", output)


if __name__ == "__main__":
    unittest.main()
