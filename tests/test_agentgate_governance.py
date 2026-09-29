import datetime as dt
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class AgentGateGovernanceTests(unittest.TestCase):
    def test_required_agentgate_files_are_installed(self):
        required = {
            "governance.config.yml",
            ".github/workflows/governance.yml",
            "docs/governance/mr-spec.md",
            "docs/governance/risk-types.md",
            "governance/scripts/governance_common.py",
            "governance/scripts/scan_risks.py",
            "governance/scripts/check_tested.py",
            "governance/scripts/validate_mr.py",
            "governance/scripts/record_test_run.py",
            "governance/scripts/collect_ai_usage.py",
        }

        missing = [path for path in required if not (ROOT / path).is_file()]

        self.assertEqual([], missing)

    def test_config_excludes_vendored_governance_scripts(self):
        config = yaml.safe_load((ROOT / "governance.config.yml").read_text(encoding="utf-8"))

        self.assertEqual("hard", config["risk_annotations"]["enforcement"])
        self.assertIn("governance/scripts/**", config["risk_annotations"]["scan_exclude_paths"])
        self.assertTrue(config["deliverhq_integration"]["enabled"])

    def _scan_fixture(self, source_lines):
        """在临时目录写入真实源文件与对应 diff, 以临时目录为 cwd 运行 scan_risks。"""
        with tempfile.TemporaryDirectory(prefix="deliverhq-agentgate-") as temp:
            source = Path(temp) / "src" / "service.py"
            source.parent.mkdir(parents=True)
            source.write_text("\n".join(source_lines) + "\n", encoding="utf-8")
            diff = Path(temp) / "risk.diff"
            diff.write_text(
                "\n".join(
                    ["+++ b/src/service.py", f"@@ -0,0 +1,{len(source_lines)} @@"]
                    + ["+" + line for line in source_lines]
                )
                + "\n",
                encoding="utf-8",
            )
            return subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "governance" / "scripts" / "scan_risks.py"),
                    "--diff-file",
                    str(diff),
                    "--config",
                    str(ROOT / "governance.config.yml"),
                ],
                cwd=temp,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )

    # risk:test-removal reason:"旧版用例因源文件缺失而误判通过，已原地重写为同名用例并新增注解合规正例" owner:@deliverhq reviewed:2026-09-29
    def test_risk_scan_blocks_new_unannotated_risk(self):
        result = self._scan_fixture(['if user_id == "626786582b50ab8ec08b0fa0": pass'])
        output = result.stdout + result.stderr

        self.assertNotEqual(0, result.returncode, output)
        # 必须是因缺注解而阻断, 而不是因读不到源文件
        self.assertIn("未找到 risk: 注解", output)
        self.assertNotIn("无法读取源文件", output)

    def test_risk_scan_passes_properly_annotated_risk(self):
        today = dt.date.today().isoformat()
        result = self._scan_fixture(
            [
                f'# risk:auth-bypass reason:"回归夹具用于验证认证比较扫描规则" owner:@deliverhq reviewed:{today}',
                f'# risk:magic-id reason:"回归夹具用于验证硬编码标识扫描规则" owner:@deliverhq reviewed:{today}',
                'if user_id == "626786582b50ab8ec08b0fa0": pass',
            ]
        )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_governance_workflow_uses_pr_base_ref(self):
        workflow = (ROOT / ".github" / "workflows" / "governance.yml").read_text(encoding="utf-8")

        self.assertIn("github.event.pull_request.base.ref", workflow)
        self.assertIn("governance/scripts/scan_risks.py", workflow)
        self.assertIn("governance/scripts/check_tested.py", workflow)


if __name__ == "__main__":
    unittest.main()
