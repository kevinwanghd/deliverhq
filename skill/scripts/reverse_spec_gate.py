#!/usr/bin/env python3
"""
reverse_spec_gate.py —— 逆向需求门禁（目标2 的硬约束）

把"人工确认"从君子协定变成强制门禁。规则：
  BLOCK 条件（任一）：
    1. 存在 review_required:true 且 human_decision.status == "unconfirmed" 的高风险条目
       （高风险模块未经人工裁决，不许进开发）
    2. 存在 status in (confirmed, modified) 但 is_real_requirement 仍为 null 的条目
       （确认了却没回答"这是真需求还是 bug"，等于没裁决）
    3. 存在 status == confirmed/modified 且 is_real_requirement:true 但 becomes_acceptance_criteria 为空
       （要转成需求却没写验收条件）

  PASS WITH WARNING：
    - 存在 deferred 条目（暂缓，不阻塞，但提示）

跨平台 / Python 3.10+。写回 state.yml（若存在 cr_state）。

用法：
  python reverse_spec_gate.py <CR目录 或 reverse-spec-candidates.yml 路径>
"""

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("需要 PyYAML：pip install PyYAML")
    sys.exit(2)


class Color:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    END = "\033[0m"


def _resolve_candidates_path(arg):
    """参数可为 CR 目录或直接的 yml 文件。"""
    p = Path(arg)
    if p.is_dir():
        return p / "reverse-spec-candidates.yml"
    return p


def load_candidates(path):
    if not path.exists():
        return None, "reverse-spec-candidates.yml 不存在: %s" % path
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return None, "解析失败: %s" % e
    return data, None


def check_reverse_spec_gate(arg):
    print("%s=== ReverseSpecGate 检查 ===%s\n" % (Color.BLUE, Color.END))
    path = _resolve_candidates_path(arg)
    data, error = load_candidates(path)
    if error:
        print("%s✗ %s%s" % (Color.RED, error, Color.END))
        return False, [error]

    candidates = data.get("candidates", []) or []
    if not candidates:
        print("%s⚠ 候选列表为空%s" % (Color.YELLOW, Color.END))
        return True, []

    blockers = []
    warnings = []
    stats = {"total": len(candidates), "unconfirmed_highrisk": 0,
             "confirmed": 0, "rejected": 0, "deferred": 0, "modified": 0}

    for c in candidates:
        cid = c.get("id", "?")
        review_required = c.get("review_required", False)
        hd = c.get("human_decision", {}) or {}
        status = hd.get("status", "unconfirmed")
        is_real = hd.get("is_real_requirement", None)
        becomes = c.get("becomes_acceptance_criteria")

        if status == "deferred":
            stats["deferred"] += 1
            warnings.append("%s 已暂缓（deferred）" % cid)
            continue
        if status == "rejected":
            stats["rejected"] += 1
            continue
        if status == "modified":
            stats["modified"] += 1
        if status == "confirmed":
            stats["confirmed"] += 1

        # 规则1：高风险未裁决
        if review_required and status == "unconfirmed":
            stats["unconfirmed_highrisk"] += 1
            reasons = "；".join(c.get("review_reason", []))
            blockers.append("%s 高风险未确认（%s）" % (cid, reasons or "review_required"))
            continue

        # 规则2：确认了但没回答 is_real_requirement
        if status in ("confirmed", "modified") and is_real is None:
            blockers.append("%s 已确认但未回答 is_real_requirement（真需求 or bug?）" % cid)
            continue

        # 规则3：是真需求却没写验收条件
        if status in ("confirmed", "modified") and is_real is True:
            if not becomes or (isinstance(becomes, str) and "{{" in becomes):
                blockers.append("%s 标为真需求但 becomes_acceptance_criteria 为空" % cid)

    # 输出统计
    print("%s[候选统计]%s" % (Color.BLUE, Color.END))
    print("  总数: %d" % stats["total"])
    print("  确认(真需求): %d  修正: %d  拒绝(bug/债): %d  暂缓: %d"
          % (stats["confirmed"], stats["modified"], stats["rejected"], stats["deferred"]))
    print("  %s高风险未确认: %d%s"
          % (Color.RED if stats["unconfirmed_highrisk"] else Color.GREEN,
             stats["unconfirmed_highrisk"], Color.END))

    print("\n%s=== ReverseSpecGate 结果 ===%s" % (Color.BLUE, Color.END))
    if blockers:
        print("%s❌ BLOCKED%s" % (Color.RED, Color.END))
        for i, b in enumerate(blockers, 1):
            print("  %d. %s" % (i, b))
        print("\n%s⛔ 高风险逆向需求未经人工裁决，不能进入开发。%s" % (Color.RED, Color.END))
        print("   用 confirm_reverse_spec.py 逐条裁决，或人工编辑 reverse-spec-candidates.yml")
        return False, blockers

    if warnings:
        print("%s⚠️  PASS WITH WARNINGS%s" % (Color.YELLOW, Color.END))
        for i, w in enumerate(warnings, 1):
            print("  %d. %s" % (i, w))
    print("%s✅ PASS - 所有高风险逆向需求已裁决%s" % (Color.GREEN, Color.END))
    return True, []


def main():
    if len(sys.argv) < 2:
        print("用法: python reverse_spec_gate.py <CR目录 或 reverse-spec-candidates.yml>")
        sys.exit(1)

    arg = sys.argv[1]
    passed, blockers = check_reverse_spec_gate(arg)

    # 写回状态机（若可用且参数是 CR 目录）
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from cr_state import record_from_arg
        record_from_arg(arg, "reverse_spec", passed)
    except Exception:
        pass

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
