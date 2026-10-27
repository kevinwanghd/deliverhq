import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


sys.dont_write_bytecode = True


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skill"
SCRIPTS = SKILL / "scripts"


def load_script(name):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPTS))
    return module


class LaneAdvisorProtectedPathsTests(unittest.TestCase):
    """lane_advisor 必须与 PermissionGate 同口径识别受保护路径。

    PermissionGate 只在 lane=high-risk 且该 CR 的 exceptions.yml 含
    gate_override{gate: PermissionGate, approved_by 非空} 时才放行受保护路径改动。
    若建议器不知道 protected_paths，给出的 standard lane 建议必然在门禁被 BLOCK，
    开发者"按建议走却撞墙"。CR-FLOW-LANES.md 早已声明「修改 protected_paths
    → 自动判定为 High-Risk」，这里固定该行为。
    """

    @classmethod
    def setUpClass(cls):
        cls.la = load_script("lane_advisor.py")

    def _cr(self, files, spec="## 验收条件\n### 场景 1: a\n"):
        tmp = Path(tempfile.mkdtemp(prefix="deliverhq-lane-"))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        (tmp / "acceptance-spec.md").write_text(spec, encoding="utf-8")
        (tmp / "traceability.yml").write_text(
            "schema: x\nX:\n  implementation:\n"
            + "".join("    - file: %s\n" % f for f in files),
            encoding="utf-8",
        )
        return tmp

    def test_protected_manifest_suggests_high_risk(self):
        for target in ("package.json", "requirements.txt"):
            with self.subTest(target=target):
                out = self.la.advise(self._cr([target]))
                self.assertEqual("high-risk", out["lane"])
                self.assertIn(target, out["signals"]["protected_paths"])

    def test_non_protected_files_not_flagged(self):
        out = self.la.advise(self._cr(["src/app.py", "README.md"]))
        self.assertEqual([], out["signals"]["protected_paths"])
        self.assertNotEqual("high-risk", out["lane"])

    def test_pattern_normalization_matches_permissiongate(self):
        # permissiongate 去掉 "../" 前缀后用 fnmatch 匹配仓库根相对路径，
        # 建议器必须同口径，否则两边对"哪些算受保护路径"的判断会分叉。
        patterns = self.la._load_protected_paths()
        self.assertIn("package.json", patterns)
        self.assertIn("requirements.txt", patterns)
        self.assertNotIn("../package.json", patterns)

    def test_existing_lane_rules_unchanged(self):
        small = self.la.advise(self._cr(["f0.py"]))
        self.assertEqual("fast", small["lane"])
        medium = self.la.advise(self._cr(["f0.py", "f1.py", "f2.py", "f3.py"]))
        self.assertEqual("standard", medium["lane"])
        sensitive = self.la.advise(
            self._cr(["login.py"], "## 验收条件\n### 场景 1: 用户登录 auth token\n")
        )
        self.assertEqual("high-risk", sensitive["lane"])
        big = self.la.advise(self._cr(["f%d.py" % i for i in range(9)]))
        self.assertEqual("split", big["decision"])
