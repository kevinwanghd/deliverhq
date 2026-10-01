"""DeliverHQ/scripts 自包含副本的同步测试。

DeliverHQ/scripts 下的副本不依赖 skill/scripts/common（无 common 包），
与 skill 侧各自带有独有逻辑，漂移是双向的。本文件固定同步过去的修复：
- 时间戳统一为带本地时区偏移的 ISO-8601（_now_iso 内联助手）
- evidence_gate 对格式损坏的 evidence JSON 不再抛 JSONDecodeError
- tech_spec_manager 删除无引用的 load/save_yaml_robust
- skill 侧 adversarial_review / evidence_gate 的 git 子进程强制 UTF-8 解码
"""
import importlib
import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
DH_SCRIPTS = ROOT / "DeliverHQ" / "scripts"
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

ISO_OFFSET_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")


def load_module(name, path):
    """按唯一模块名加载文件，避免与 skill 侧同名模块在 sys.modules 中冲突。"""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dh_adversarial = load_module("dh_adversarial_review", DH_SCRIPTS / "adversarial_review.py")
dh_evidence_gate = load_module("dh_evidence_gate", DH_SCRIPTS / "evidence_gate.py")
dh_tech_spec = load_module("dh_tech_spec_manager", DH_SCRIPTS / "tech_spec_manager.py")
skill_adversarial = importlib.import_module("adversarial_review")
skill_evidence_gate = importlib.import_module("evidence_gate")


def make_tmp(test):
    temp_dir = tempfile.TemporaryDirectory(prefix="deliverhq-dh-")
    test.addCleanup(temp_dir.cleanup)
    return Path(temp_dir.name)


class NowIsoTests(unittest.TestCase):
    """三个副本的时间戳与 common.timeutil.now_iso 格式一致：秒精度 + 本地偏移。"""

    def test_now_iso_format(self):
        for module in (dh_adversarial, dh_evidence_gate, dh_tech_spec):
            with self.subTest(module=module.__name__):
                self.assertRegex(module._now_iso(), ISO_OFFSET_RE)


class EvidenceGateRobustnessTests(unittest.TestCase):
    """格式损坏的 evidence JSON：verify 返回错误 dict，check_all 跳过不中断。"""

    def write_evidence(self, directory, evidence_type, content):
        (directory / f"{evidence_type}.json").write_text(content, encoding="utf-8")

    def test_verify_malformed_json_returns_error(self):
        evidence_dir = make_tmp(self)
        self.write_evidence(evidence_dir, "test", "{broken json")
        with mock.patch.object(dh_evidence_gate, "get_evidence_dir", return_value=evidence_dir):
            result = dh_evidence_gate.verify_evidence("CR-T", "test")
        self.assertFalse(result["success"])
        self.assertFalse(result["verified"])
        self.assertIn("格式错误", result["error"])

    def test_check_all_skips_malformed_json(self):
        evidence_dir = make_tmp(self)
        self.write_evidence(evidence_dir, "test", "{broken json")
        self.write_evidence(evidence_dir, "build",
                            '{"type": "build", "verified": true, "recorded_at": "2026-09-30"}')
        with mock.patch.object(dh_evidence_gate, "get_evidence_dir", return_value=evidence_dir):
            results = dh_evidence_gate.check_all_evidence("CR-T")
        types = [e["type"] for e in results["evidences"]]
        self.assertNotIn("test", types, "损坏的 test.json 应被跳过")
        self.assertIn("build", types, "有效的 build.json 保留")


class TechSpecParityTests(unittest.TestCase):
    def test_dead_yaml_helpers_removed(self):
        self.assertFalse(hasattr(dh_tech_spec, "load_yaml_robust"))
        self.assertFalse(hasattr(dh_tech_spec, "save_yaml_robust"))


class SkillGitUtf8Tests(unittest.TestCase):
    """skill 侧两个模块的 git 子进程必须强制 UTF-8 解码（与 DeliverHQ 副本一致）。"""

    def fake_run(self, captured):
        def run(cmd, **kwargs):
            captured.update(kwargs)
            return subprocess.CompletedProcess(cmd, 0, stdout="中文输出", stderr="")
        return run

    def test_adversarial_run_git_forces_utf8(self):
        captured = {}
        with mock.patch.object(skill_adversarial.subprocess, "run",
                               side_effect=self.fake_run(captured)):
            rc, out, _ = skill_adversarial.run_git(["git", "status"])
        self.assertEqual(0, rc)
        self.assertEqual("中文输出", out)
        self.assertEqual("utf-8", captured["encoding"])
        self.assertEqual("replace", captured["errors"])

    def test_evidence_gate_run_git_forces_utf8(self):
        captured = {}
        with mock.patch.object(skill_evidence_gate.subprocess, "run",
                               side_effect=self.fake_run(captured)):
            rc, out, _ = skill_evidence_gate.run_git_command(["git", "status"])
        self.assertEqual(0, rc)
        self.assertEqual("中文输出", out)
        self.assertEqual("utf-8", captured["encoding"])
        self.assertEqual("replace", captured["errors"])


if __name__ == "__main__":
    unittest.main()
