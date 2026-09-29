#!/usr/bin/env python3
"""
时间戳工具
统一约定：写入用带本地时区偏移的 ISO-8601（秒精度），如 2026-09-29T10:00:00+08:00；
读取一律解析为 aware datetime 再比较，不做字符串比较。旧的 naive 值按本地时间解释。
设置 SOURCE_DATE_EPOCH 时 now_dt() 返回该时刻（UTC），保证产物可复现。
"""

import os
from datetime import datetime, timezone

_SPACE_FORMAT = "%Y-%m-%d %H:%M:%S"


def now_dt():
    """当前时刻（aware，本地时区，去掉微秒）；SOURCE_DATE_EPOCH 存在时返回该时刻（UTC）。"""
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc)
    return datetime.now().astimezone().replace(microsecond=0)


def now_iso():
    """当前时刻的 ISO-8601 字符串（秒精度，带时区偏移）。"""
    return now_dt().isoformat(timespec="seconds")


def parse_ts(value):
    """把 datetime / ISO 字符串（可带 Z 或偏移，可为 naive）解析为 aware datetime；naive 视为本地时间。

    无法解析时抛 ValueError。
    """
    if isinstance(value, datetime):
        dt = value
    else:
        if value is None:
            raise ValueError("timestamp is None")
        text = str(value).strip()
        if text.endswith(("Z", "z")):
            # Python 3.10 的 fromisoformat 不接受 Z 后缀
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            try:
                dt = datetime.strptime(text, _SPACE_FORMAT)
            except ValueError:
                raise ValueError("无法解析时间戳: %r" % (value,)) from None
    if dt.tzinfo is None:
        dt = dt.astimezone()  # 按本地时区解释
    return dt


def hours_since(value):
    """从 value 到现在经过的小时数（float）；无法解析时抛 ValueError。"""
    return (datetime.now(timezone.utc) - parse_ts(value)).total_seconds() / 3600


def sort_key(value):
    """排序键（POSIX 时间戳 float）；无法解析时返回 0.0，保证排序不崩溃。"""
    try:
        return parse_ts(value).timestamp()
    except (TypeError, ValueError, OverflowError, OSError):
        return 0.0
