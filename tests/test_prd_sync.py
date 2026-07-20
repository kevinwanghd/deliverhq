import importlib.util
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill" / "scripts" / "prd_sync.py"


def load_sync():
    spec = importlib.util.spec_from_file_location("prd_sync", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALID_PRD = """# PRD: Demo

```yaml
schema: deliverhq-prd
schema_version: 2
prd_id: PRD-DEMO
status: draft
```

## [PRD-LOGIN] Login

- **REQ ID**: REQ-LOGIN
- **状态**: confirmed
- **优先级**: P0
- **负责人**: Product
- **目标平台**: Flutter
- **来源证据**: Prototype page 1
- **依赖**: None
- **范围内**: Login
- **范围外**: Registration

**验收条件索引**
- AC-LOGIN-01: successful login
- AC-LOGIN-02: invalid password

**业务不变式**
- INV-LOGIN-01: password is never returned

**研发交付映射**
| 任务 ID | 角色 | 责任 | 覆盖 REQ/AC | 禁止承接 |
|---|---|---|---|---|
| DEV-LOGIN | backend | login rules | REQ-LOGIN/AC-LOGIN-01 | Flutter business logic |
| QA-LOGIN | qa | acceptance tests | AC-LOGIN-01 | implementation |

**待确认问题**
- Q-LOGIN-01: None
"""


class PrdSyncTests(unittest.TestCase):
    def test_sync_writes_agent_artifacts(self):
        prd_sync = load_sync()
        with tempfile.TemporaryDirectory(prefix="deliverhq-prd-sync-") as tmp:
            root = Path(tmp)
            prd = root / "PRD.md"
            out = root / "agent"
            prd.write_text(VALID_PRD, encoding="utf-8")

            result = prd_sync.sync(prd, out)

            self.assertTrue(result["ok"], result)
            self.assertEqual(1, result["feature_count"])
            manifest = yaml.safe_load((out / "prd-manifest.yml").read_text(encoding="utf-8"))
            task_map = yaml.safe_load((out / "task-map.yml").read_text(encoding="utf-8"))
            acceptance = (out / "acceptance-spec.md").read_text(encoding="utf-8")
            report = (out / "change-report.md").read_text(encoding="utf-8")

            self.assertEqual("deliverhq-prd-manifest", manifest["schema"])
            self.assertEqual("PRD-LOGIN", manifest["features"][0]["anchor"])
            self.assertEqual(["AC-LOGIN-01", "AC-LOGIN-02"], manifest["features"][0]["ac_ids"])
            self.assertEqual({"backend", "qa"}, {item["role"] for item in task_map["tasks"]})
            self.assertIn("business_logic_authority", acceptance)
            self.assertIn("successful login", acceptance)
            self.assertIn("Added anchors: 1", report)

    def test_sync_blocks_invalid_prd(self):
        prd_sync = load_sync()
        with tempfile.TemporaryDirectory(prefix="deliverhq-prd-sync-invalid-") as tmp:
            root = Path(tmp)
            prd = root / "PRD.md"
            out = root / "agent"
            prd.write_text("# PRD\n", encoding="utf-8")

            result = prd_sync.sync(prd, out)

            self.assertFalse(result["ok"])
            self.assertFalse(out.exists())

    def test_generated_at_is_deterministic_when_epoch_pinned(self):
        # Reproducibility: same PRD + pinned SOURCE_DATE_EPOCH => byte-identical
        # derived artifacts across runs.
        import os

        prd_sync = load_sync()
        prev = os.environ.get("SOURCE_DATE_EPOCH")
        os.environ["SOURCE_DATE_EPOCH"] = "1700000000"
        try:
            with tempfile.TemporaryDirectory(prefix="deliverhq-prd-sync-det-") as tmp:
                root = Path(tmp)
                prd = root / "PRD.md"
                prd.write_text(VALID_PRD, encoding="utf-8")
                out1, out2 = root / "a1", root / "a2"
                prd_sync.sync(prd, out1)
                prd_sync.sync(prd, out2)
                for name in ("prd-manifest.yml", "task-map.yml", "acceptance-spec.md", "change-report.md"):
                    self.assertEqual(
                        (out1 / name).read_text(encoding="utf-8"),
                        (out2 / name).read_text(encoding="utf-8"),
                        f"{name} differs across runs with pinned epoch",
                    )
                manifest = yaml.safe_load((out1 / "prd-manifest.yml").read_text(encoding="utf-8"))
                self.assertEqual("2023-11-14T22:13:20+00:00", manifest["generated_at"])
        finally:
            if prev is None:
                os.environ.pop("SOURCE_DATE_EPOCH", None)
            else:
                os.environ["SOURCE_DATE_EPOCH"] = prev

    def test_feature_count_parity_guard(self):
        # If sync's derived feature count ever diverges from the validator's,
        # it must fail closed rather than emit a partial contract.
        prd_sync = load_sync()
        with tempfile.TemporaryDirectory(prefix="deliverhq-prd-sync-parity-") as tmp:
            root = Path(tmp)
            prd = root / "PRD.md"
            out = root / "agent"
            prd.write_text(VALID_PRD, encoding="utf-8")

            # Force a divergence: make validate see one more feature than
            # collect_features returns, simulating a template-detection mismatch.
            original = prd_sync.prd_validate.validate

            def inflated(path, strict=False):
                res = original(path, strict=strict)
                res["feature_count"] += 1
                return res

            prd_sync.prd_validate.validate = inflated
            try:
                result = prd_sync.sync(prd, out)
            finally:
                prd_sync.prd_validate.validate = original

            self.assertFalse(result["ok"])
            self.assertIn("error", result)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
