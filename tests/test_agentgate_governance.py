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

    def test_risk_scan_blocks_new_unannotated_risk(self):
        with tempfile.TemporaryDirectory(prefix="deliverhq-agentgate-") as temp:
            diff = Path(temp) / "risk.diff"
            diff.write_text(
                "\n".join(
                    [
                        "+++ b/src/service.py",
                        "@@ -0,0 +1,3 @@",
                        '+# risk:auth-bypass reason:"AgentGate regression fixture intentionally exercises auth scanner" owner:@kevinwanghd reviewed:2026-07-15',
                        '+# risk:magic-id reason:"AgentGate regression fixture intentionally exercises magic id scanner" owner:@kevinwanghd reviewed:2026-07-15',
                        '+if user_id == "626786582b50ab8ec08b0fa0": pass',
                    ]
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "governance" / "scripts" / "scan_risks.py"),
                    "--diff-file",
                    str(diff),
                    "--config",
                    str(ROOT / "governance.config.yml"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)

    def test_governance_workflow_uses_pr_base_ref(self):
        workflow = (ROOT / ".github" / "workflows" / "governance.yml").read_text(encoding="utf-8")

        self.assertIn("github.event.pull_request.base.ref", workflow)
        self.assertIn("governance/scripts/scan_risks.py", workflow)
        self.assertIn("governance/scripts/check_tested.py", workflow)


if __name__ == "__main__":
    unittest.main()
