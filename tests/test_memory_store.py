import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skill" / "scripts" / "memory_store.py"


def load_module():
    spec = importlib.util.spec_from_file_location("deliverhq_memory_store", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MemoryStoreLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def store(self):
        temp = tempfile.TemporaryDirectory(prefix="deliverhq-memory-")
        self.addCleanup(temp.cleanup)
        return self.module.MemoryStore(Path(temp.name) / "memory")

    def test_legacy_index_loads_with_lifecycle_defaults(self):
        temp = tempfile.TemporaryDirectory(prefix="deliverhq-memory-legacy-")
        self.addCleanup(temp.cleanup)
        storage = Path(temp.name)
        legacy = {
            "legacy-id": {
                "id": "legacy-id",
                "type": "mistake",
                "content": "test failed",
                "context": "fix fixture",
                "cr_id": "CR-001",
                "tags": ["test"],
                "created_at": "2026-01-01T00:00:00",
                "updated_at": "2026-01-01T00:00:00",
                "references": [],
            }
        }
        (storage / "index.json").write_text(json.dumps(legacy), encoding="utf-8")

        store = self.module.MemoryStore(storage)
        entry = store.get("legacy-id")

        self.assertEqual("active", entry.status)
        self.assertEqual(1, entry.occurrences)
        self.assertTrue(entry.fingerprint)

    def test_same_root_cause_merges_and_increments_occurrences(self):
        store = self.store()

        first = store.add(
            "QualityGate reports 65 percent coverage",
            "mistake",
            root_cause="boundary tests missing",
            applies_to="pytest",
            evidence=["CR-001/quality-report.md"],
        )
        second = store.add(
            "Coverage remains below threshold",
            "mistake",
            root_cause="Boundary tests missing",
            applies_to="pytest",
            evidence=["CR-002/quality-report.md"],
        )

        self.assertEqual(first.id, second.id)
        self.assertEqual(1, len(store.entries))
        self.assertEqual(2, second.occurrences)
        self.assertEqual(
            ["CR-001/quality-report.md", "CR-002/quality-report.md"],
            second.evidence,
        )

    def test_lifecycle_transitions_are_explicit(self):
        store = self.store()
        old = store.add("old rule", "rule")
        replacement = store.add("new rule", "rule")

        store.supersede(old.id, replacement.id)
        store.deprecate(replacement.id, "runtime upgraded")
        obsolete = store.add("obsolete workaround", "pattern")
        store.obsolete(obsolete.id, "the supported adapter replaced this workaround")

        self.assertEqual("superseded", store.get(old.id).status)
        self.assertEqual(replacement.id, store.get(old.id).superseded_by)
        self.assertEqual("deprecated", store.get(replacement.id).status)
        self.assertEqual("runtime upgraded", store.get(replacement.id).revalidate_when)
        self.assertEqual("obsolete", store.get(obsolete.id).status)
        with self.assertRaises(ValueError):
            store.add("bad", "mistake", status="unknown")

    def test_lifecycle_audit_reports_promotion_and_missing_evidence(self):
        store = self.store()
        first = store.add(
            "same failure",
            "mistake",
            root_cause="repeatable root cause",
            evidence=["missing/evidence.md"],
        )
        store.add("same failure again", "mistake", root_cause="repeatable root cause")
        store.add("same failure third", "mistake", root_cause="repeatable root cause")

        with tempfile.TemporaryDirectory(prefix="deliverhq-memory-root-") as tmp:
            report = store.audit_lifecycle(root=tmp, min_occurrences=3)

        self.assertEqual([], report["blockers"])
        self.assertIn(first.id, report["promotion_candidates"])
        self.assertTrue(any("ready for promotion" in item for item in report["warnings"]))
        self.assertTrue(any("evidence path missing" in item for item in report["warnings"]))

    def test_lifecycle_audit_blocks_broken_superseded_reference(self):
        store = self.store()
        entry = store.add("old rule", "rule")
        entry.status = "superseded"
        entry.superseded_by = "missing"
        store._save_index()

        report = store.audit_lifecycle()

        self.assertTrue(any("superseded_by target" in item for item in report["blockers"]))

    def test_default_storage_uses_deliverhq_home_not_agent_directory(self):
        with tempfile.TemporaryDirectory(prefix="deliverhq-home-") as tmp:
            home = Path(tmp) / "DeliverHQ"
            home.mkdir()
            with mock.patch.dict(os.environ, {"DELIVERHQ_HOME": str(home)}):
                store = self.module.MemoryStore()

            self.assertEqual(home / "memory", store.storage_path)
            self.assertNotIn(".claude", str(store.storage_path))

    def test_export_preserves_existing_human_document(self):
        store = self.store()
        store.add("decision", "decision")
        with tempfile.TemporaryDirectory(prefix="deliverhq-docs-") as tmp:
            docs = Path(tmp)
            canonical = docs / "decisions.md"
            canonical.write_text("human\n", encoding="utf-8")

            store.export_to_docs(str(docs))

            self.assertEqual("human\n", canonical.read_text(encoding="utf-8"))
            self.assertTrue((docs / "decisions.generated.md").is_file())


if __name__ == "__main__":
    unittest.main()
