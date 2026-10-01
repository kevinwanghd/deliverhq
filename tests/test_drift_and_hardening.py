"""批次 B（DeliverHQ 副本漂移修复 + 入口加固）的行为固定测试。

覆盖三组改动：
1. human_checkpoint 配置深合并修复（skill + DeliverHQ 双侧）。
   线上 P0：仓库 governance.config.yml 的 human_checkpoints 条目不含 prompt 字段，
   旧的整体替换合并 `{**CHECKPOINTS, **custom}` 丢掉内置 prompt，
   run_checkpoint 执行到 cp["prompt"].format(...) 必现 KeyError: 'prompt'。
2. DeliverHQ 副本补齐：HK-V 关卡注册与渲染、HK-2.5 对抗式审查报告渲染与
   "有 blocking"/"暂停" 输入处理、adversarial_review 的 evidence JSON 写入。
3. 入口加固：goal_contract / reverse_spec_gate 支持 --help，
   不存在路径不再触发 record_from_arg 写副作用（旧逻辑会向 cwd 写 state.yml）；
   product 最小安装不再携带 ARC 运行时四件套；prd_sync 去除重复 import yaml。
"""
import importlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = ROOT / "skill" / "scripts"
DH_SCRIPTS = ROOT / "DeliverHQ" / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

human_checkpoint = importlib.import_module("human_checkpoint")

ISO_OFFSET_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")

SUBPROCESS_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}


def load_module(name, path):
    """按唯一模块名加载文件，避免与 skill 侧同名模块在 sys.modules 中冲突。"""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dh_hcp = load_module("dh_human_checkpoint_drift", DH_SCRIPTS / "human_checkpoint.py")
dh_adv = load_module("dh_adversarial_review_drift", DH_SCRIPTS / "adversarial_review.py")


def make_tmp(test):
    temp_dir = tempfile.TemporaryDirectory(prefix="deliverhq-drift-")
    test.addCleanup(temp_dir.cleanup)
    return Path(temp_dir.name)


def chdir(test, target):
    old = Path.cwd()
    os.chdir(target)
    test.addCleanup(os.chdir, old)


class SkillCheckpointDeepMergeTests(unittest.TestCase):
    """skill 侧深合并修复：配置条目只覆盖给出的字段，内置 prompt 保留。"""

    def test_deep_merge_keeps_builtin_prompt_for_partial_entries(self):
        cfg = make_tmp(self) / "governance.config.yml"
        cfg.write_text(
            "human_checkpoints:\n"
            "  - id: HK-0\n"
            "    name: 自定义现场快报\n",
            encoding="utf-8")
        merged = human_checkpoint.load_checkpoints_config(cfg)
        self.assertEqual("自定义现场快报", merged["HK-0"]["name"])
        self.assertEqual(
            human_checkpoint.CHECKPOINTS["HK-0"]["prompt"],
            merged["HK-0"]["prompt"],
            "配置未给 prompt 时必须保留内置 prompt（整体替换会丢字段）")
        self.assertIn("HK-V", merged, "未被配置覆盖的内置关卡保留")

    def test_run_checkpoint_with_repo_config_does_not_keyerror(self):
        # 线上 P0 回归：仓库配置的 human_checkpoints 条目不含 prompt，
        # 旧合并逻辑下 run_checkpoint 必现 KeyError: 'prompt'
        cfg_text = human_checkpoint.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
        self.assertIn("human_checkpoints:", cfg_text, "前提：仓库配置确实覆盖关卡定义")
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = human_checkpoint.run_checkpoint(
                "HK-0", context="验证深合并", auto_approve=True,
                config_path=human_checkpoint.DEFAULT_CONFIG_PATH)
        self.assertTrue(result["approved"])
        self.assertIn("验证深合并", buf.getvalue())


class DeliverHQCheckpointParityTests(unittest.TestCase):
    """DeliverHQ 副本：同样的深合并修复 + HK-V/HK-2.5 独有逻辑。"""

    def run_dh_hk(self, checkpoint_id, **kwargs):
        kwargs.setdefault("config_path", make_tmp(self) / "missing.yml")
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = dh_hcp.run_checkpoint(checkpoint_id, **kwargs)
        return result, buf.getvalue()

    def make_cr_with_report(self, report_text):
        tmp = make_tmp(self)
        evidence = tmp / "DeliverHQ" / "change-requests" / "CR-T" / "evidence"
        evidence.mkdir(parents=True)
        (evidence / "adversarial_review_report.md").write_text(report_text, encoding="utf-8")
        chdir(self, tmp)
        return tmp

    def test_deep_merge_keeps_builtin_prompt(self):
        cfg = make_tmp(self) / "governance.config.yml"
        cfg.write_text(
            "human_checkpoints:\n"
            "  - id: HK-0\n"
            "    name: 自定义现场快报\n",
            encoding="utf-8")
        merged = dh_hcp.load_checkpoints_config(cfg)
        self.assertEqual("自定义现场快报", merged["HK-0"]["name"])
        self.assertEqual(dh_hcp.CHECKPOINTS["HK-0"]["prompt"], merged["HK-0"]["prompt"])

    def test_run_checkpoint_with_repo_config_does_not_keyerror(self):
        # DeliverHQ 副本默认配置即仓库根 governance.config.yml（含无 prompt 条目）
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = dh_hcp.run_checkpoint("HK-0", context="验证深合并", auto_approve=True)
        self.assertTrue(result["approved"])

    def test_hk_v_registered_with_renderable_prompt(self):
        self.assertIn("HK-V", dh_hcp.CHECKPOINTS)
        prompt = dh_hcp.CHECKPOINTS["HK-V"]["prompt"]
        self.assertIn("{layer_report_summary}", prompt)
        self.assertIn("{blockers}", prompt)

    def test_hk_v_renders_json_context(self):
        context = json.dumps(
            {"summary": "Layer 3 quality 失败", "blockers_text": "- 缺 build evidence"},
            ensure_ascii=False)
        result, output = self.run_dh_hk("HK-V", context=context, auto_approve=True)
        self.assertTrue(result["approved"])
        self.assertIn("Layer 3 quality 失败", output)
        self.assertIn("缺 build evidence", output)

    def test_hk_v_bad_json_falls_back_to_raw_context(self):
        _, output = self.run_dh_hk("HK-V", context="裸文本阻断说明", auto_approve=True)
        self.assertIn("裸文本阻断说明", output)

    def test_hk25_renders_report_verdict_and_findings(self):
        self.make_cr_with_report(
            "# 对抗式审查报告\n\nverdict: FAIL\n\n"
            "## 发现\n- [CRITICAL] RL-C01 明文密钥\n- [HIGH] 吞异常\n")
        _, output = self.run_dh_hk("HK-2.5", cr_id="CR-T", auto_approve=True)
        self.assertIn("verdict: FAIL", output)
        self.assertIn("2 条", output)
        self.assertIn("[CRITICAL] RL-C01 明文密钥", output)
        self.assertIn("[HIGH] 吞异常", output)

    def test_hk25_pass_report_shows_no_findings(self):
        self.make_cr_with_report("# 报告\n\nverdict: PASS\n\n无发现。\n")
        _, output = self.run_dh_hk("HK-2.5", cr_id="CR-T", auto_approve=True)
        self.assertIn("verdict: PASS", output)
        self.assertIn("无 CRITICAL/HIGH 发现", output)

    def test_hk25_missing_report_shows_placeholder(self):
        chdir(self, make_tmp(self))
        _, output = self.run_dh_hk("HK-2.5", cr_id="CR-T", auto_approve=True)
        self.assertIn("未找到对抗式审查报告", output)

    def test_hk25_blocking_input_rejects(self):
        self.make_cr_with_report("verdict: PASS\n")
        with mock.patch("builtins.input", side_effect=["有 blocking: 两条未解决"]):
            result, _ = self.run_dh_hk("HK-2.5", cr_id="CR-T")
        self.assertFalse(result["approved"])
        self.assertIn("blocking 未解决", result["message"])

    def test_pause_input_pauses(self):
        with mock.patch("builtins.input", side_effect=["暂停"]):
            result, _ = self.run_dh_hk("HK-0")
        self.assertFalse(result["approved"])
        self.assertIn("暂停", result["message"])


class DeliverHQAdversarialEvidenceTests(unittest.TestCase):
    """DeliverHQ 副本 adversarial_review 的 evidence JSON 写入（verify 分层报告依赖）。"""

    def make_repo(self, with_evidence=True):
        tmp = make_tmp(self)
        if with_evidence:
            (tmp / "DeliverHQ" / "change-requests" / "CR-T" / "evidence").mkdir(parents=True)
        return tmp

    def write_evidence(self, tmp, verdict, blocking):
        buf = io.StringIO()
        with mock.patch.object(dh_adv, "get_repo_root", return_value=tmp):
            with redirect_stdout(buf):
                dh_adv._write_evidence_json(
                    "CR-T", "staged", ["src/a.py"], verdict, blocking, "report.md")
        return tmp / "DeliverHQ" / "change-requests" / "CR-T" / "evidence" / "anti_gaming-result.json"

    def test_evidence_output_prefers_deliverhq_layout(self):
        tmp = self.make_repo()
        with mock.patch.object(dh_adv, "get_repo_root", return_value=tmp):
            out = dh_adv._evidence_output_for_cr("CR-T")
        self.assertIsNotNone(out)
        self.assertEqual("anti_gaming-result.json", out.name)

    def test_evidence_output_none_without_evidence_dir(self):
        tmp = self.make_repo(with_evidence=False)
        with mock.patch.object(dh_adv, "get_repo_root", return_value=tmp):
            self.assertIsNone(dh_adv._evidence_output_for_cr("CR-T"))

    def test_write_pass_payload(self):
        tmp = self.make_repo()
        ev_json = self.write_evidence(tmp, "PASS", [])
        payload = json.loads(ev_json.read_text(encoding="utf-8"))
        self.assertEqual("deliverhq-gate-result/v1", payload["schema_version"])
        self.assertEqual("adversarial_review", payload["gate_name"])
        self.assertEqual("pass", payload["result"])
        self.assertRegex(payload["timestamp"], ISO_OFFSET_RE)
        self.assertEqual([], payload["blocking_items"])
        self.assertEqual("CR-T", payload["metadata"]["cr_id"])
        self.assertEqual("PASS", payload["metadata"]["verdict"])

    def test_write_blocked_payload_formats_blocking_items(self):
        tmp = self.make_repo()
        blocking = [{"severity": "CRITICAL", "type": "明文密钥"},
                    {"severity": "HIGH", "type": "吞异常"}]
        ev_json = self.write_evidence(tmp, "FAIL", blocking)
        payload = json.loads(ev_json.read_text(encoding="utf-8"))
        self.assertEqual("blocked", payload["result"])
        self.assertEqual(["[CRITICAL] 明文密钥", "[HIGH] 吞异常"], payload["blocking_items"])
        self.assertEqual(2, payload["metadata"]["blocking_findings"])

    def test_write_without_evidence_dir_is_noop(self):
        tmp = self.make_repo(with_evidence=False)
        buf = io.StringIO()
        with mock.patch.object(dh_adv, "get_repo_root", return_value=tmp):
            with redirect_stdout(buf):
                dh_adv._write_evidence_json("CR-T", "staged", [], "PASS", [], "report.md")
        self.assertEqual([], list(tmp.rglob("*.json")), "无 evidence 目录时不得创建文件")


class PrdSyncStaticTests(unittest.TestCase):
    def test_single_import_yaml(self):
        src = (SKILL_SCRIPTS / "prd_sync.py").read_text(encoding="utf-8")
        self.assertEqual(
            1, len(re.findall(r"^import yaml$", src, re.M)),
            "prd_sync.py 只能有一处 import yaml（重复导入已清理）")


class ProductProfileArcExclusionTests(unittest.TestCase):
    """product 最小安装不含 ARC 运行时四件套（依赖链不随包，装上即死文件）。"""

    ARC_SCRIPTS = ("session_pack_builder.py", "evidence_verifier.py",
                   "recovery_manager.py", "arc_scheduler.py")

    def test_product_profile_excludes_arc_runtime(self):
        src = (ROOT / "bin" / "cli.js").read_text(encoding="utf-8")
        product_block = src[src.index("product: {"):src.index("mappings:")]
        for name in self.ARC_SCRIPTS:
            self.assertNotIn(
                "'scripts/%s'" % name, product_block,
                "product 文件清单不得包含 %s" % name)

    def test_arc_run_still_uses_skill_source(self):
        src = (ROOT / "bin" / "cli.js").read_text(encoding="utf-8")
        self.assertIn("SKILL_SRC, 'scripts', 'arc_scheduler.py'", src,
                      "CLI arc-run 走完整包 SKILL_SRC，不受 product 精简影响")


class GateScriptArgHandlingTests(unittest.TestCase):
    """goal_contract / reverse_spec_gate：--help 与不存在路径不得产生写副作用。"""

    def run_script(self, script, *args, cwd):
        return subprocess.run(
            [sys.executable, str(SKILL_SCRIPTS / script), *args],
            cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            env=SUBPROCESS_ENV, timeout=60,
        )

    def assert_cwd_clean(self, cwd):
        self.assertEqual([], list(cwd.iterdir()),
                         "不存在路径/--help 不得在 cwd 产生任何文件")

    def test_goal_contract_help_exits_zero_without_writes(self):
        cwd = make_tmp(self)
        result = self.run_script("goal_contract.py", "--help", cwd=cwd)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("用法", result.stdout)
        self.assert_cwd_clean(cwd)

    def test_goal_contract_missing_path_has_no_side_effects(self):
        cwd = make_tmp(self)
        result = self.run_script("goal_contract.py", "nonexistent-cr", cwd=cwd)
        self.assertEqual(1, result.returncode)
        self.assert_cwd_clean(cwd)

    def test_goal_contract_valid_cr_writes_evidence(self):
        # 存在路径的正常行为不变：写 evidence/goal-contract-result.json
        cr_dir = make_tmp(self) / "CR-T"
        cr_dir.mkdir()
        (cr_dir / "goal-contract.yml").write_text(
            "goal: 验证入口参数处理\n"
            "success_criteria:\n"
            "  metrics:\n"
            "    - id: M1\n"
            "      command: echo ok\n"
            "      expect: ok\n"
            "  invariants:\n"
            "    - 不修改仓库外文件\n"
            "verification_commands:\n"
            "  - echo ok\n"
            "boundaries:\n"
            "  forbidden_actions:\n"
            "    - 删除用户文件\n"
            "on_failure:\n"
            "  max_retries: 1\n"
            "escalate_to_human_when:\n"
            "  - 连续失败\n",
            encoding="utf-8")
        result = self.run_script("goal_contract.py", str(cr_dir), cwd=make_tmp(self))
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        ev_json = cr_dir / "evidence" / "goal-contract-result.json"
        self.assertTrue(ev_json.is_file())
        self.assertEqual("pass", json.loads(ev_json.read_text(encoding="utf-8"))["result"])

    def test_reverse_spec_gate_help_exits_zero_without_writes(self):
        cwd = make_tmp(self)
        result = self.run_script("reverse_spec_gate.py", "--help", cwd=cwd)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("用法", result.stdout)
        self.assert_cwd_clean(cwd)

    def test_reverse_spec_gate_missing_path_has_no_side_effects(self):
        cwd = make_tmp(self)
        result = self.run_script("reverse_spec_gate.py", "nonexistent-cr", cwd=cwd)
        self.assertEqual(1, result.returncode)
        self.assert_cwd_clean(cwd)

    def test_reverse_spec_gate_empty_candidates_passes(self):
        cr_dir = make_tmp(self) / "CR-T"
        cr_dir.mkdir()
        (cr_dir / "reverse-spec-candidates.yml").write_text(
            "candidates: []\n", encoding="utf-8")
        result = self.run_script("reverse_spec_gate.py", str(cr_dir), cwd=make_tmp(self))
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
