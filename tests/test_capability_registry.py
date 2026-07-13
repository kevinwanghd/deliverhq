import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skill"
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SKILL))
sys.path.insert(0, str(SCRIPTS))


class CapabilityRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = importlib.import_module("deliverhq.capabilities")

    def test_loads_valid_registry_with_stable_unique_ids(self):
        records = self.registry.load_registry()
        ids = [record.id for record in records]

        self.assertGreaterEqual(len(records), 40)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(record.id.startswith("cap-") for record in records))
        self.assertTrue(any(record.default_enabled for record in records))

    def test_rejects_duplicate_ids_and_invalid_status(self):
        with tempfile.TemporaryDirectory(prefix="deliverhq-capabilities-") as temp:
            path = Path(temp) / "capabilities.yml"
            path.write_text(
                "\n".join(
                    [
                        "capabilities:",
                        "  - id: cap-001",
                        "    name: One",
                        "    script: scripts/one.py",
                        "    status: stable",
                        "    integrated: integrated",
                        "    default_enabled: true",
                        "    allowed_in_pipeline: false",
                        "    description: first",
                        "  - id: cap-001",
                        "    name: Two",
                        "    script: scripts/two.py",
                        "    status: unknown",
                        "    integrated: integrated",
                        "    default_enabled: false",
                        "    allowed_in_pipeline: false",
                        "    description: second",
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaises(self.registry.RegistryError):
                self.registry.load_registry(path)

    def test_matrix_is_checked_generated_output(self):
        matrix = (SKILL / "CAPABILITY-MATRIX.md").read_text(encoding="utf-8")
        rendered = self.registry.render_matrix_document(matrix, self.registry.load_registry())

        self.assertEqual(rendered, matrix)
        self.assertIn("BEGIN GENERATED CAPABILITIES", matrix)
        self.assertIn("END GENERATED CAPABILITIES", matrix)

    def test_capability_tiers_reads_registry_not_markdown(self):
        tiers = importlib.import_module("capability_tiers")
        records = self.registry.load_registry()
        rows = tiers.parse_matrix("not a markdown table")
        core, on_demand = tiers.classify(rows)

        self.assertEqual(len(records), len(rows))
        self.assertEqual(len(core), sum(1 for record in records if record.default_enabled))
        self.assertEqual(len(on_demand), sum(1 for record in records if not record.default_enabled))

    def test_registry_cli_outputs_json_counts(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "capability_registry.py"), "check", "--json"],
            cwd=SKILL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertGreaterEqual(payload["count"], 40)
        self.assertTrue(payload["matrix_current"])


if __name__ == "__main__":
    unittest.main()

