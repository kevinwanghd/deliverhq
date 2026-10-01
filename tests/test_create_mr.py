"""create_mr.py 提交链路与子进程 UTF-8 解码的行为测试。

覆盖历史缺陷：glab --fill 与 --title 同用直接报错、GitHub 仓库误选 glab、
CLI 提交失败无降级路径、EDITOR 带引号路径在 Windows 下不可执行、
evidence_verifier / init_cr 的子进程按 GBK 解码 UTF-8 输出。
"""
import importlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "governance" / "scripts"))
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

create_mr = importlib.import_module("create_mr")
evidence_verifier = importlib.import_module("evidence_verifier")
init_cr = importlib.import_module("init_cr")


def make_tmp(test):
    temp_dir = tempfile.TemporaryDirectory(prefix="deliverhq-mr-")
    test.addCleanup(temp_dir.cleanup)
    return Path(temp_dir.name)


def fake_which(available):
    return lambda name: f"/usr/bin/{name}" if name in available else None


class DetectCliTests(unittest.TestCase):
    """CLI 选择必须认远端：GitHub 优先 gh，GitLab 优先 glab，首选缺失再退而求其次。"""

    def detect(self, remote, available):
        with mock.patch.object(create_mr.shutil, "which", side_effect=fake_which(available)):
            return create_mr.detect_cli(remote)

    def test_github_remote_prefers_gh(self):
        self.assertEqual("gh", self.detect("git@github.com:owner/repo.git", {"gh", "glab"}))
        self.assertEqual("gh", self.detect("https://github.com/owner/repo.git", {"gh", "glab"}))

    def test_gitlab_remote_prefers_glab(self):
        self.assertEqual("glab", self.detect("https://gitlab.example.com/g/r.git", {"gh", "glab"}))
        self.assertEqual("glab", self.detect("git@gitlab.com:g/r.git", {"gh", "glab"}))

    def test_unknown_remote_keeps_legacy_order(self):
        self.assertEqual("glab", self.detect("", {"gh", "glab"}))

    def test_preferred_missing_falls_back_to_other(self):
        self.assertEqual("glab", self.detect("https://github.com/o/r.git", {"glab"}))
        self.assertEqual("gh", self.detect("https://gitlab.com/o/r.git", {"gh"}))

    def test_no_cli_returns_none(self):
        self.assertIsNone(self.detect("https://github.com/o/r.git", set()))


class SubmitMrCmdTests(unittest.TestCase):
    """submit_mr 命令构造：glab 不带 --fill、目标分支去掉 origin/ 前缀、exe 解析全路径。"""

    def run_submit(self, cli, target="main", rc=0, available=("glab", "gh")):
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            if "--body-file" in cmd:
                captured["body"] = Path(cmd[cmd.index("--body-file") + 1]).read_text(encoding="utf-8")
                captured["body_file"] = cmd[cmd.index("--body-file") + 1]
            return subprocess.CompletedProcess(cmd, rc)

        with mock.patch.object(create_mr.shutil, "which", side_effect=fake_which(set(available))), \
                mock.patch.object(create_mr.subprocess, "run", side_effect=fake_run):
            result = create_mr.submit_mr("标题", "描述正文", target, cli)
        return result, captured

    def test_glab_cmd_has_no_fill_and_strips_origin_prefix(self):
        rc, captured = self.run_submit("glab", target="origin/main")
        self.assertEqual(0, rc)
        self.assertNotIn("--fill", captured["cmd"], "glab 不允许 --fill 与 --title 同用")
        self.assertEqual("main", captured["cmd"][captured["cmd"].index("--target-branch") + 1])
        self.assertIn("--description", captured["cmd"])

    def test_gh_cmd_uses_body_file_and_cleans_up(self):
        rc, captured = self.run_submit("gh", target="origin/main")
        self.assertEqual(0, rc)
        self.assertEqual("描述正文", captured["body"])
        self.assertEqual("main", captured["cmd"][captured["cmd"].index("--base") + 1])
        self.assertFalse(Path(captured["body_file"]).exists(), "临时描述文件必须清理")

    def test_returncode_passthrough(self):
        rc, _ = self.run_submit("gh", rc=3)
        self.assertEqual(3, rc)


class SubmitWithFallbackTests(unittest.TestCase):
    """首选 CLI 失败时换另一个 CLI 重试；都不可用返回原失败码。"""

    def test_falls_back_to_other_cli(self):
        calls = []

        def submit_fn(title, description, target, cli):
            calls.append(cli)
            return 1 if cli == "glab" else 0

        with mock.patch.object(create_mr.shutil, "which", side_effect=fake_which({"gh", "glab"})), \
                redirect_stdout(io.StringIO()):
            rc = create_mr.submit_with_fallback("t", "d", "main", "glab", submit_fn=submit_fn)
        self.assertEqual(0, rc)
        self.assertEqual(["glab", "gh"], calls)

    def test_both_fail_returns_failure(self):
        with mock.patch.object(create_mr.shutil, "which", side_effect=fake_which({"gh", "glab"})), \
                redirect_stdout(io.StringIO()):
            rc = create_mr.submit_with_fallback("t", "d", "main", "gh",
                                                submit_fn=lambda *a: 1)
        self.assertEqual(1, rc)

    def test_other_cli_missing_returns_original_rc(self):
        with mock.patch.object(create_mr.shutil, "which", side_effect=fake_which({"glab"})), \
                redirect_stdout(io.StringIO()):
            rc = create_mr.submit_with_fallback("t", "d", "main", "glab",
                                                submit_fn=lambda *a: 2)
        self.assertEqual(2, rc)


class EditorSplitTests(unittest.TestCase):
    """EDITOR 拆分：Windows 保留反斜杠并剥引号。"""

    def test_plain_command(self):
        self.assertEqual(["code", "--wait"], create_mr._split_editor_command("code --wait"))

    def test_default_editor(self):
        expected = ["notepad"] if os.name == "nt" else ["vi"]
        self.assertEqual(expected, create_mr._split_editor_command(None))

    @unittest.skipUnless(os.name == "nt", "Windows 专属行为")
    def test_quoted_windows_path(self):
        self.assertEqual(
            [r"C:\Program Files\App\code.exe", "--wait"],
            create_mr._split_editor_command(r'"C:\Program Files\App\code.exe" --wait'),
        )


class ManualFallbackUrlTests(unittest.TestCase):
    """手动创建链接：GitHub 用 compare，GitLab 用 merge_requests/new。"""

    def test_project_web_url_parses_ssh_and_https(self):
        self.assertEqual("https://github.com/o/r",
                         create_mr._project_web_url("git@github.com:o/r.git"))
        self.assertEqual("https://github.com/o/r",
                         create_mr._project_web_url("https://github.com/o/r.git"))
        self.assertEqual("https://gitlab.example.com/g/r",
                         create_mr._project_web_url("git@gitlab.example.com:g/r.git"))
        self.assertEqual("", create_mr._project_web_url(""))
        self.assertEqual("", create_mr._project_web_url("not-a-url"))

    def test_github_compare_url(self):
        url = create_mr._manual_mr_url("https://github.com/o/r", "feat/x", "main")
        self.assertEqual("https://github.com/o/r/compare/main...feat%2Fx?expand=1", url)

    def test_gitlab_mr_new_url(self):
        url = create_mr._manual_mr_url("https://gitlab.example.com/g/r", "feat/x", "main")
        self.assertTrue(url.startswith("https://gitlab.example.com/g/r/-/merge_requests/new?"))
        self.assertIn("merge_request[source_branch]=feat%2Fx", url)
        self.assertIn("merge_request[target_branch]=main", url)
        self.assertIn("issuable_template=default", url)


class OriginUrlTests(unittest.TestCase):
    def test_origin_url_reads_remote(self):
        url = create_mr._origin_url()
        self.assertIsInstance(url, str)
        self.assertIn("deliverhq", url, "本仓库 origin 应指向 deliverhq")


class AntiGamingSubprocessEncodingTests(unittest.TestCase):
    """evidence_verifier 调用 anti_gaming_check：子进程 UTF-8 输出不得被 GBK 解码。"""

    def test_utf8_child_output_decoded_cleanly(self):
        cr = make_tmp(self)
        # 子进程继承 PYTHONIOENCODING=utf-8 → 输出 UTF-8；修复前父进程按 GBK 解码会报 codec 错误
        with mock.patch.dict(os.environ, {"PYTHONIOENCODING": "utf-8"}):
            ok, msg = evidence_verifier._check_anti_gaming(cr)
        self.assertNotIn("codec", msg)
        self.assertNotIn("decode", msg)
        self.assertIsInstance(ok, bool)

    def test_subprocess_kwargs_force_utf8(self):
        captured = {}

        def fake_run(cmd, **kwargs):
            captured.update(kwargs)
            return subprocess.CompletedProcess(cmd, 0, stdout="通过", stderr="")

        with mock.patch.object(evidence_verifier.subprocess, "run", side_effect=fake_run):
            ok, msg = evidence_verifier._check_anti_gaming(make_tmp(self))
        self.assertEqual((True, "pass"), (ok, msg))  # rc=0 时固定返回 "pass"，不取 stdout
        self.assertEqual("utf-8", captured["encoding"])
        self.assertEqual("replace", captured["errors"])
        self.assertEqual("utf-8", captured["env"]["PYTHONIOENCODING"])


class CreateWorktreeEncodingTests(unittest.TestCase):
    """init_cr 调用 worktree_manager：解码参数与结果处理。"""

    def run_create(self, rc, stderr=""):
        captured = {}

        def fake_run(cmd, **kwargs):
            captured.update(kwargs)
            return subprocess.CompletedProcess(cmd, rc, stdout="", stderr=stderr)

        with mock.patch.object(init_cr.subprocess, "run", side_effect=fake_run), \
                redirect_stdout(io.StringIO()):
            try:
                result = init_cr._create_worktree("CR-1", make_tmp(self), fail_on_error=False)
                error = None
            except RuntimeError as exc:
                result, error = None, exc
        return result, error, captured

    def test_subprocess_kwargs_force_utf8(self):
        _, _, captured = self.run_create(1, "失败")
        self.assertEqual("utf-8", captured["encoding"])
        self.assertEqual("replace", captured["errors"])
        self.assertEqual("utf-8", captured["env"]["PYTHONIOENCODING"])

    def test_failure_without_fail_on_error_returns_none(self):
        result, error, _ = self.run_create(1, "index.lock 存在")
        self.assertIsNone(result)
        self.assertIsNone(error)

    def test_success_returns_worktree_path(self):
        tmp = make_tmp(self)

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with mock.patch.object(init_cr.subprocess, "run", side_effect=fake_run), \
                redirect_stdout(io.StringIO()):
            result = init_cr._create_worktree("CR-1", tmp)
        self.assertEqual(tmp / ".claude" / "worktrees" / "CR-1", result)


if __name__ == "__main__":
    unittest.main()
