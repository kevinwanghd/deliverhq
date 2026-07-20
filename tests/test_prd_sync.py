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


if __name__ == "__main__":
    unittest.main()
