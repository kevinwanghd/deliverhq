import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill" / "scripts" / "prd_validate.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("prd_validate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALID_PRD = """# PRD: Demo

```yaml
schema: deliverhq-prd
schema_version: 2
status: draft
```

## [PRD-LOGIN] 登录

- **REQ ID**: REQ-LOGIN
- **状态**: confirmed
- **优先级**: P0
- **负责人**: 产品
- **目标平台**: Flutter
- **来源证据**: 原型页面 1
- **依赖**: 无
- **范围内**: 登录
- **范围外**: 注册

**验收条件索引**
- AC-LOGIN-01: 成功登录

**业务不变式**
- INV-LOGIN-01: 密码不明文返回

**研发交付映射**
| 任务 ID | 角色 | 责任 | 覆盖 REQ/AC | 禁止承接 |
|---|---|---|---|---|
| DEV-LOGIN | backend | 登录规则 | REQ-LOGIN/AC-LOGIN-01 | UI 逻辑 |
| QA-LOGIN | qa | 验收脚本 | AC-LOGIN-01 | 业务实现 |

**待确认问题**
- Q-LOGIN-01: 无
"""


class PrdValidateTests(unittest.TestCase):
    def test_valid_prd_passes(self):
        validator = load_validator()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "PRD.md"
            path.write_text(VALID_PRD, encoding="utf-8")
            result = validator.validate(path)
        self.assertTrue(result["ok"], result)
        self.assertEqual(["REQ-LOGIN"], result["req_ids"])

    def test_missing_scope_blocks(self):
        validator = load_validator()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "PRD.md"
            path.write_text(VALID_PRD.replace("- **范围外**: 注册\n", ""), encoding="utf-8")
            result = validator.validate(path)
        self.assertFalse(result["ok"])
        self.assertTrue(any("范围外" in item for item in result["blockers"]))

    def _validate_text(self, text, **kwargs):
        validator = load_validator()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "PRD.md"
            path.write_text(text, encoding="utf-8")
            return validator.validate(path, **kwargs)

    def test_real_feature_with_brace_is_not_dropped(self):
        # A fully-filled feature whose prose legitimately contains {{ user }}
        # must still be counted — the leftover brace should not misclassify the
        # whole section as a template stub (regression: silent feature drop).
        prd = VALID_PRD.replace("- **范围内**: 登录", "- **范围内**: 返回 {{ user }} 给前端")
        result = self._validate_text(prd)
        self.assertTrue(result["ok"], result)
        self.assertEqual(1, result["feature_count"])
        self.assertTrue(any("占位符" in w for w in result["warnings"]), result)

    def test_brace_placeholder_blocks_under_strict(self):
        prd = VALID_PRD.replace("- **范围内**: 登录", "- **范围内**: 返回 {{ user }} 给前端")
        result = self._validate_text(prd, strict=True)
        self.assertFalse(result["ok"])
        self.assertTrue(any("占位符" in b for b in result["blockers"]), result)

    def test_template_markers_still_detected(self):
        # The shipped template markers must keep classifying as template stubs.
        prd = VALID_PRD.replace("- AC-LOGIN-01: 成功登录", "- AC-LOGIN-01: 成功登录 示例锚点")
        result = self._validate_text(prd)
        self.assertFalse(result["ok"])
        self.assertEqual(0, result["feature_count"])


if __name__ == "__main__":
    unittest.main()
