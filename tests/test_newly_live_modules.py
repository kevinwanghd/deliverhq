"""新生效模块的行为固定测试。

背景：common.load_yaml 修复前，red_lines_check / gate_cache / create_sub_cr /
human_checkpoint 等模块向它传入已打开的文件对象，恒得到 {}——
governance.config.yml 的 red_lines / human_checkpoints 配置从未生效，
gate_cache 回写时还会清空 state.yml 原有字段。修复后配置首次真正加载，
本文件固定这些模块（以及 gate_contract_check 的目录隔离逻辑）的实际行为。
"""
import hashlib
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

import yaml

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

red_lines_check = importlib.import_module("red_lines_check")
gate_cache = importlib.import_module("gate_cache")
create_sub_cr = importlib.import_module("create_sub_cr")
human_checkpoint = importlib.import_module("human_checkpoint")
gate_contract_check = importlib.import_module("gate_contract_check")

SUBPROCESS_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}


def make_tmp(test):
    temp_dir = tempfile.TemporaryDirectory(prefix="deliverhq-live-")
    test.addCleanup(temp_dir.cleanup)
    return Path(temp_dir.name)


def missing_config(test):
    return make_tmp(test) / "missing.yml"


class RedLinesConfigTests(unittest.TestCase):
    """红线配置加载：配置缺失/无 red_lines 段/空段 → 内置默认；有配置 → 用配置。"""

    def write_config(self, text):
        cfg = make_tmp(self) / "governance.config.yml"
        cfg.write_text(text, encoding="utf-8")
        return cfg

    def test_missing_config_returns_builtin_defaults(self):
        lines = red_lines_check.load_red_lines(missing_config(self))
        self.assertEqual(6, len(lines["critical"]))
        self.assertEqual(8, len(lines["standard"]))
        self.assertEqual("RL-C01", lines["critical"][0]["id"])
        self.assertEqual("RL-S01", lines["standard"][0]["id"])

    def test_config_overrides_both_sections(self):
        cfg = self.write_config(
            "red_lines:\n"
            "  critical:\n"
            "    - id: RL-X01\n"
            "      title: 自定义关键红线\n"
            "  standard:\n"
            "    - id: RL-Y01\n"
            "      title: 自定义标准红线\n"
            "      phase: implement\n"
        )
        lines = red_lines_check.load_red_lines(cfg)
        self.assertEqual(["RL-X01"], [c["id"] for c in lines["critical"]])
        self.assertEqual(["RL-Y01"], [s["id"] for s in lines["standard"]])

    def test_config_without_red_lines_key_returns_defaults(self):
        lines = red_lines_check.load_red_lines(self.write_config("other: 1\n"))
        self.assertEqual(6, len(lines["critical"]))
        self.assertEqual(8, len(lines["standard"]))

    def test_empty_sections_fall_back_to_defaults(self):
        lines = red_lines_check.load_red_lines(
            self.write_config("red_lines:\n  critical: []\n  standard: []\n"))
        self.assertEqual(6, len(lines["critical"]))
        self.assertEqual(8, len(lines["standard"]))

    def test_repo_governance_config_is_actually_loaded(self):
        # skill/ 下无 governance.config.yml，DEFAULT_CONFIG_PATH 解析到仓库根目录配置。
        # 修复前 load_yaml(文件对象) 恒返回 {}，配置里的 RL-C07 从未生效。
        config = yaml.safe_load((ROOT / "governance.config.yml").read_text(encoding="utf-8"))
        expected = [c["id"] for c in config["red_lines"]["critical"]]
        self.assertIn("RL-C07", expected, "仓库配置应包含 RL-C07（本测试的前提）")

        lines = red_lines_check.load_red_lines()
        self.assertEqual(expected, [c["id"] for c in lines["critical"]])

    def test_check_phase_filters_standard_rules(self):
        red_lines = {
            "critical": [{"id": "C1"}],
            "standard": [
                {"id": "S1", "phase": "implement"},
                {"id": "S2", "phase": "verify"},
                {"id": "S3"},
            ],
        }
        result = red_lines_check.check_phase("implement", red_lines)
        self.assertEqual([{"id": "C1"}], result["critical"], "critical 全阶段适用")
        self.assertEqual(["S1"], [s["id"] for s in result["standard"]])
        self.assertEqual([], red_lines_check.check_phase("nonexistent", red_lines)["standard"])


class RedLinesCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "red_lines_check.py"), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=SUBPROCESS_ENV, timeout=60,
        )

    def test_list_critical_uses_repo_config(self):
        result = self.run_cli("list", "--type", "critical")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("RL-C07", result.stdout)  # 仓库配置生效的标志（内置默认只有 C01-C06）

    def test_check_without_context_exits_zero(self):
        result = self.run_cli("check", "--phase", "implement")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("RL-S01", result.stdout)  # implement 阶段红线来自仓库配置


class GateCacheTests(unittest.TestCase):
    """Gate 缓存：fingerprint 稳定、随内容变化；跳过条件；回写不清空 state.yml。"""

    def write_state(self, cr, state):
        (cr / "state.yml").write_text(
            yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def read_state(self, cr):
        return yaml.safe_load((cr / "state.yml").read_text(encoding="utf-8"))

    def test_fingerprint_order_independent_and_deterministic(self):
        cr = make_tmp(self)
        (cr / "a.md").write_text("A", encoding="utf-8")
        (cr / "b.md").write_text("B", encoding="utf-8")
        fp1 = gate_cache.calculate_fingerprint(cr, ["b.md", "a.md"])
        fp2 = gate_cache.calculate_fingerprint(cr, ["a.md", "b.md"])
        self.assertEqual(fp1, fp2)
        self.assertEqual(fp1, gate_cache.calculate_fingerprint(cr, ["a.md", "b.md"]))

    def test_fingerprint_tracks_content_changes(self):
        cr = make_tmp(self)
        target = cr / "a.md"
        target.write_text("A", encoding="utf-8")
        fp1 = gate_cache.calculate_fingerprint(cr, ["a.md"])
        target.write_text("A2", encoding="utf-8")
        self.assertNotEqual(fp1, gate_cache.calculate_fingerprint(cr, ["a.md"]))

    def test_missing_dependencies_are_skipped(self):
        cr = make_tmp(self)
        self.assertEqual(
            hashlib.sha256(b"").hexdigest(),
            gate_cache.calculate_fingerprint(cr, ["nope.md"]),
        )

    def test_wildcard_dependency_matches_report_files(self):
        cr = make_tmp(self)
        (cr / "spec-report.md").write_text("r1", encoding="utf-8")
        (cr / "notes.txt").write_text("n", encoding="utf-8")
        fp1 = gate_cache.calculate_fingerprint(cr, ["*-report.md"])
        (cr / "notes.txt").write_text("n2", encoding="utf-8")
        self.assertEqual(fp1, gate_cache.calculate_fingerprint(cr, ["*-report.md"]),
                         "非匹配文件变化不影响 fingerprint")
        (cr / "design-report.md").write_text("r2", encoding="utf-8")
        self.assertNotEqual(fp1, gate_cache.calculate_fingerprint(cr, ["*-report.md"]))

    def test_should_skip_requires_pass_status_and_matching_fingerprint(self):
        cr = make_tmp(self)
        (cr / "request.md").write_text("需求", encoding="utf-8")
        fp = gate_cache.get_gate_fingerprint(cr, "spec")

        self.assertFalse(gate_cache.should_skip_gate(cr, "spec"), "无 state.yml 不得跳过")

        self.write_state(cr, {"gate_status": {"spec": "blocked"}, "gates": {"spec": {"fingerprint": fp}}})
        self.assertFalse(gate_cache.should_skip_gate(cr, "spec"), "非 pass 状态不得跳过")

        self.write_state(cr, {"gate_status": {"spec": "pass"}})
        self.assertFalse(gate_cache.should_skip_gate(cr, "spec"), "无缓存 fingerprint 不得跳过")

        self.write_state(cr, {"gate_status": {"spec": "pass"}, "gates": {"spec": {"fingerprint": fp}}})
        self.assertTrue(gate_cache.should_skip_gate(cr, "spec"))

        (cr / "acceptance-spec.md").write_text("新验收标准", encoding="utf-8")
        self.assertFalse(gate_cache.should_skip_gate(cr, "spec"), "依赖文件变化后必须重跑")

    def test_update_preserves_existing_state_fields(self):
        cr = make_tmp(self)
        self.write_state(cr, {"cr_id": "CR-1", "current_phase": "implement",
                              "gate_status": {"spec": "pass"}})
        gate_cache.update_gate_fingerprint(cr, "spec", "passed")
        state = self.read_state(cr)
        # load_yaml(文件对象) 修复前，这里读回的是 {}，以下字段会被清空
        self.assertEqual("CR-1", state["cr_id"])
        self.assertEqual("implement", state["current_phase"])
        self.assertEqual({"spec": "pass"}, state["gate_status"])
        self.assertEqual(gate_cache.get_gate_fingerprint(cr, "spec"),
                         state["gates"]["spec"]["fingerprint"])

    def test_invalidate_downstream_clears_only_later_gates(self):
        cr = make_tmp(self)
        self.write_state(cr, {"gates": {
            "spec": {"fingerprint": "a"},
            "design": {"fingerprint": "b"},
            "architecture": {"fingerprint": "c"},
            "quality": {"fingerprint": "d"},
        }})
        gate_cache.invalidate_downstream_gates(cr, "design")
        gates = self.read_state(cr)["gates"]
        self.assertEqual("a", gates["spec"]["fingerprint"])
        self.assertEqual("b", gates["design"]["fingerprint"], "自身缓存保留")
        self.assertNotIn("fingerprint", gates["architecture"])
        self.assertNotIn("fingerprint", gates["quality"])
        gate_cache.invalidate_downstream_gates(cr, "not-a-gate")  # 未知 gate 不报错


class CreateSubCrTests(unittest.TestCase):
    """子 CR 创建：ID 序号、sub-crs.yml 读写、模板复制与 state 初始化。"""

    def setUp(self):
        self.tmp = make_tmp(self)
        self.addCleanup(setattr, create_sub_cr, "DELIVERHQ_ROOT", create_sub_cr.DELIVERHQ_ROOT)
        create_sub_cr.DELIVERHQ_ROOT = self.tmp
        self.cr_root = self.tmp / "change-requests"
        epic = self.cr_root / "CR-001"
        epic.mkdir(parents=True)
        (epic / "state.yml").write_text(
            yaml.safe_dump({"title": "Epic 标题"}, allow_unicode=True), encoding="utf-8")
        template = self.cr_root / "CR-TEMPLATE"
        template.mkdir()
        (template / "marker.txt").write_text("模板占位\n", encoding="utf-8")

    def test_next_sub_cr_id_sequences(self):
        next_id = create_sub_cr.next_sub_cr_id
        self.assertEqual("CR-001-01", next_id("CR-001", []))
        self.assertEqual("CR-001-03", next_id("CR-001", [{"id": "CR-001-01"}, {"id": "CR-001-02"}]))
        self.assertEqual("CR-001-04", next_id("CR-001", [{"id": "CR-001-01"}, {"id": "CR-001-03"}]),
                         "编号有空洞时取 max+1")
        self.assertEqual("CR-001-02", next_id("CR-001", [{"id": "CR-001-01"}, {"id": "CR-001-beta"}]),
                         "非数字后缀忽略")
        self.assertEqual("CR-001-11", next_id("CR-001", [{"id": f"CR-001-{i:02d}"} for i in range(1, 11)]),
                         "超过 09 继续递增，无上限")

    def test_load_sub_crs_missing_returns_default(self):
        data = create_sub_cr.load_sub_crs(self.cr_root / "CR-001")
        self.assertEqual("CR-001", data["epic"])
        self.assertEqual([], data["sub_crs"])
        self.assertIn("created_at", data)

    def test_load_sub_crs_adds_missing_sub_crs_key(self):
        epic = self.cr_root / "CR-001"
        (epic / "sub-crs.yml").write_text("epic: CR-001\ntitle: 已有\n", encoding="utf-8")
        data = create_sub_cr.load_sub_crs(epic)
        self.assertEqual("已有", data["title"])
        self.assertEqual([], data["sub_crs"])

    def test_create_sub_cr_scaffolds_from_template(self):
        with redirect_stdout(io.StringIO()):
            first = create_sub_cr.create_sub_cr("CR-001", "OAuth 集成")
        self.assertEqual("CR-001-01", first)

        sub = self.cr_root / "CR-001-01"
        self.assertEqual("模板占位\n", (sub / "marker.txt").read_text(encoding="utf-8"),
                         "CR-TEMPLATE 内容应被复制")
        request = (sub / "request.md").read_text(encoding="utf-8")
        self.assertIn("OAuth 集成", request)
        self.assertIn("CR-001", request)
        parent = yaml.safe_load((sub / "parent.yml").read_text(encoding="utf-8"))
        self.assertEqual("CR-001", parent["parent"])
        self.assertEqual([], parent["depends_on"])
        state = yaml.safe_load((sub / "state.yml").read_text(encoding="utf-8"))
        self.assertEqual("draft", state["current_state"])
        self.assertEqual("CR-001", state["parent"])
        self.assertEqual("spec", state["next_required_gate"])

        ledger = yaml.safe_load((self.cr_root / "CR-001" / "sub-crs.yml").read_text(encoding="utf-8"))
        self.assertEqual("Epic 标题", ledger["title"], "Epic 标题应读自 Epic 的 state.yml")
        self.assertEqual(["CR-001-01"], [s["id"] for s in ledger["sub_crs"]])
        self.assertEqual("pending", ledger["sub_crs"][0]["status"])

        with redirect_stdout(io.StringIO()):
            second = create_sub_cr.create_sub_cr("CR-001", "JWT 管理", ["CR-001-01"])
        self.assertEqual("CR-001-02", second)
        parent2 = yaml.safe_load((self.cr_root / "CR-001-02" / "parent.yml").read_text(encoding="utf-8"))
        self.assertEqual(["CR-001-01"], parent2["depends_on"])

    def test_create_sub_cr_missing_epic_exits(self):
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                create_sub_cr.create_sub_cr("CR-999", "x")
        self.assertEqual(1, ctx.exception.code)


class HumanCheckpointTests(unittest.TestCase):
    """人工硬关卡：未知关卡拒绝；auto-approve；交互输入 go/N:/stop；配置合并。"""

    def run_hk(self, checkpoint_id, **kwargs):
        kwargs.setdefault("config_path", missing_config(self))
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = human_checkpoint.run_checkpoint(checkpoint_id, **kwargs)
        return result, buf.getvalue()

    def test_unknown_checkpoint_rejected(self):
        result, _ = self.run_hk("HK-99")
        self.assertFalse(result["approved"])
        self.assertIn("未知关卡", result["message"])

    def test_auto_approve_passes_without_input(self):
        result, output = self.run_hk("HK-0", context="已完成分析", auto_approve=True)
        self.assertTrue(result["approved"])
        self.assertIn("已完成分析", output)

    def test_go_input_approves(self):
        with mock.patch("builtins.input", side_effect=["go"]):
            result, _ = self.run_hk("HK-0")
        self.assertTrue(result["approved"])

    def test_modification_input_rejects(self):
        with mock.patch("builtins.input", side_effect=["N: 范围不对"]):
            result, _ = self.run_hk("HK-0")
        self.assertFalse(result["approved"])
        self.assertIn("范围不对", result["message"])

    def test_stop_input_pauses(self):
        with mock.patch("builtins.input", side_effect=["stop"]):
            result, _ = self.run_hk("HK-0")
        self.assertFalse(result["approved"])
        self.assertIn("暂停", result["message"])

    def test_unrecognized_input_reprompts(self):
        with mock.patch("builtins.input", side_effect=["???", "继续"]) as mocked:
            result, _ = self.run_hk("HK-0")
        self.assertTrue(result["approved"])
        self.assertEqual(2, mocked.call_count)

    def test_custom_config_overrides_and_merges(self):
        cfg = make_tmp(self) / "governance.config.yml"
        cfg.write_text(
            "human_checkpoints:\n"
            "  - id: HK-0\n"
            "    name: 自定义现场快报\n"
            "    description: d\n"
            "    wait_for: w\n",
            encoding="utf-8")
        checkpoints = human_checkpoint.load_checkpoints_config(cfg)
        self.assertEqual("自定义现场快报", checkpoints["HK-0"]["name"])
        self.assertIn("HK-V", checkpoints, "内置默认关卡应保留")

    def test_repo_config_merges_with_builtin_defaults(self):
        # DEFAULT_CONFIG_PATH 解析到仓库根目录 governance.config.yml（skill/ 下无同名文件）
        checkpoints = human_checkpoint.load_checkpoints_config(human_checkpoint.DEFAULT_CONFIG_PATH)
        self.assertIn("HK-2.5", checkpoints, "HK-2.5 来自仓库配置，修复前从未加载")
        self.assertIn("HK-V", checkpoints, "HK-V 是内置默认")

    def test_hk3_extracts_code_gen_rate_from_context(self):
        _, output = self.run_hk("HK-3", context="feat: 提交\n\n代码生成率：85%", auto_approve=True)
        self.assertIn("85%", output)

    def test_hk1_without_cr_shows_empty_pending(self):
        _, output = self.run_hk("HK-1", cr_id=None, auto_approve=True)
        self.assertIn("无 PENDING 条目", output)


class GateContractIsolationTests(unittest.TestCase):
    """gate_contract_check 单独运行时不得触碰真实 skill/change-requests。"""

    def test_explicit_root_arg_wins(self):
        root, explicit = gate_contract_check._resolve_root(["prog", "some/dir"])
        self.assertTrue(explicit)
        self.assertEqual(Path("some/dir").resolve(), root)

    def test_default_root_is_real_skill_and_not_explicit(self):
        root, explicit = gate_contract_check._resolve_root(["prog"])
        self.assertFalse(explicit)
        self.assertEqual((ROOT / "skill").resolve(), root.resolve())

    def test_staged_example_crs_are_restored_after_run(self):
        fake_root = make_tmp(self)
        result = subprocess.run(
            [sys.executable, str(ROOT / "dev" / "scripts" / "gate_contract_check.py"), str(fake_root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=SUBPROCESS_ENV, timeout=120,
        )
        self.assertEqual(1, result.returncode, "fake root 缺 gate 脚本应快速失败: " + result.stdout[-500:])
        self.assertFalse((fake_root / "change-requests" / "CR-EXAMPLE").exists(),
                         "暂存的示例 CR 必须被清理")
        self.assertFalse((fake_root / "change-requests" / "CR-BLOCKED-EXAMPLE").exists())


if __name__ == "__main__":
    unittest.main()
