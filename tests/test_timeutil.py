"""common.timeutil 时间戳统一约定的回归测试。

约定：写入带本地偏移的 ISO-8601（秒精度）；读取一律解析为 aware datetime，
旧的 naive 值按本地时间解释，不做字符串比较。
"""
import importlib
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

timeutil = importlib.import_module("common.timeutil")
cr_state = importlib.import_module("cr_state")
memory_store = importlib.import_module("memory_store")

ISO_WITH_OFFSET = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")


def _without_epoch():
    env = {k: v for k, v in os.environ.items() if k != "SOURCE_DATE_EPOCH"}
    return mock.patch.dict(os.environ, env, clear=True)


class ParseTsTests(unittest.TestCase):
    def test_naive_is_local_time(self):
        naive = datetime(2026, 9, 29, 10, 0, 0)
        parsed = timeutil.parse_ts("2026-09-29T10:00:00")
        self.assertIsNotNone(parsed.tzinfo)
        self.assertEqual(naive.astimezone(), parsed)

    def test_naive_with_microseconds(self):
        parsed = timeutil.parse_ts("2026-09-29T10:00:00.123456")
        self.assertEqual(datetime(2026, 9, 29, 10, 0, 0, 123456).astimezone(), parsed)

    def test_z_suffix_on_all_python_versions(self):
        # Python 3.10 的 fromisoformat 不接受 Z，必须自行处理
        expected = datetime(2026, 9, 29, 2, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(expected, timeutil.parse_ts("2026-09-29T02:00:00Z"))
        self.assertEqual(expected, timeutil.parse_ts("2026-09-29T02:00:00z"))

    def test_explicit_offset(self):
        parsed = timeutil.parse_ts("2026-09-29T10:00:00+08:00")
        self.assertEqual(datetime(2026, 9, 29, 2, 0, 0, tzinfo=timezone.utc), parsed)

    def test_space_format_is_local(self):
        parsed = timeutil.parse_ts("2026-09-29 10:00:00")
        self.assertEqual(datetime(2026, 9, 29, 10, 0, 0).astimezone(), parsed)

    def test_datetime_input(self):
        aware = datetime(2026, 9, 29, 2, 0, tzinfo=timezone.utc)
        self.assertEqual(aware, timeutil.parse_ts(aware))
        naive = datetime(2026, 9, 29, 10, 0)
        self.assertEqual(naive.astimezone(), timeutil.parse_ts(naive))

    def test_invalid_raises_value_error(self):
        for bad in ("not-a-date", "", None, "2026/09/29"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                timeutil.parse_ts(bad)

    def test_sort_key_never_raises(self):
        self.assertEqual(0.0, timeutil.sort_key("garbage"))
        self.assertEqual(0.0, timeutil.sort_key(None))

    def test_hours_since(self):
        old = datetime.now(timezone.utc) - timedelta(hours=5)
        self.assertAlmostEqual(5.0, timeutil.hours_since(old.isoformat()), delta=0.1)


class NowIsoTests(unittest.TestCase):
    def test_format_has_seconds_and_offset(self):
        with _without_epoch():
            value = timeutil.now_iso()
        self.assertRegex(value, ISO_WITH_OFFSET)
        self.assertLess(abs(timeutil.hours_since(value)), 0.01)

    def test_source_date_epoch_is_deterministic(self):
        with mock.patch.dict(os.environ, {"SOURCE_DATE_EPOCH": "1700000000"}):
            first = timeutil.now_iso()
            second = timeutil.now_iso()
        self.assertEqual(first, second)
        self.assertEqual("2023-11-14T22:13:20+00:00", first)


class BlockedDurationTests(unittest.TestCase):
    """旧 state.yml 中的 naive updated_at 曾因 naive/aware 相减 TypeError 被吞掉而返回 None。"""

    def snapshot(self, updated_at):
        return cr_state.CRStateSnapshot(
            cr_id="CR-1", title="t", lane="standard", current_state=cr_state.CRState.BLOCKED,
            current_phase="dev", current_owner="dev-agent", updated_at=updated_at)

    def test_old_naive_updated_at_is_measured(self):
        naive = (datetime.now() - timedelta(hours=50)).isoformat()
        hours = cr_state._blocked_duration_hours(self.snapshot(naive))
        self.assertIsNotNone(hours)
        self.assertAlmostEqual(50, hours, delta=1)

    def test_new_aware_updated_at_is_measured(self):
        aware = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat().replace("+00:00", "Z")
        self.assertAlmostEqual(3, cr_state._blocked_duration_hours(self.snapshot(aware)), delta=1)

    def test_unparseable_updated_at_returns_none(self):
        self.assertIsNone(cr_state._blocked_duration_hours(self.snapshot("garbage")))


class MemoryStoreOrderingTests(unittest.TestCase):
    """混合格式的 updated_at 必须按真实时间排序，而不是按字符串排序。"""

    def test_search_orders_mixed_formats_chronologically(self):
        temp = tempfile.TemporaryDirectory(prefix="deliverhq-timeutil-")
        self.addCleanup(temp.cleanup)
        store = memory_store.MemoryStore(str(Path(temp.name) / "memory"))
        base = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
        # 字符串序与时间序刻意不一致
        values = {
            "oldest": (base - timedelta(hours=3)).astimezone(timezone(timedelta(hours=8))).isoformat(),
            "middle": (base - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "newest": (base - timedelta(hours=1)).astimezone().replace(tzinfo=None).isoformat(),
        }
        for name, stamp in values.items():
            entry = store.add(content=name, type="lesson", fingerprint=name)
            entry.updated_at = stamp

        ordered = [e.content for e in store.search()]
        self.assertEqual(["newest", "middle", "oldest"], ordered)


if __name__ == "__main__":
    unittest.main()
