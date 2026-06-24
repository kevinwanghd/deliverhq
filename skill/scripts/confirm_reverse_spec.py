#!/usr/bin/env python3
"""
confirm_reverse_spec.py —— 逆向需求人工裁决辅助

供人工对 reverse-spec-candidates.yml 中的候选条目做裁决，写回裁决层。
非交互式（CI/脚本友好）：通过命令行参数指定裁决，避免依赖 stdin。

裁决动作：
  confirm  —— 确认为真需求；需 --criteria "<验收条件>"
  modify   —— 修正后确认为真需求；需 --criteria "<修正后验收条件>"，可 --note
  reject   —— 判定为 bug/技术债，不固化为需求；建议 --note 说明
  defer    —— 暂缓

用法：
  python confirm_reverse_spec.py <candidates.yml> --id RC-002 --action confirm \
      --criteria "连续5次密码错误后账户锁定30分钟" --by "张三"
  python confirm_reverse_spec.py <candidates.yml> --id RC-001 --action reject --note "历史 bug，应修复而非固化" --by "李四"
  python confirm_reverse_spec.py <candidates.yml> --list   # 仅列出待裁决条目

跨平台 / Python 3.10+。
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("需要 PyYAML：pip install PyYAML")
    sys.exit(2)


def load(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def list_pending(data):
    print("=== 待裁决候选（review_required 且 unconfirmed）===")
    found = False
    for c in data.get("candidates", []) or []:
        hd = c.get("human_decision", {}) or {}
        if c.get("review_required") and hd.get("status") == "unconfirmed":
            found = True
            print("  %s  %s" % (c.get("id"), c.get("source", {}).get("module", "")))
            print("      原因: %s" % "；".join(c.get("review_reason", [])))
            print("      AI 推断: %s" % c.get("inferred_behavior", ""))
            assumptions = c.get("assumptions", []) or []
            if assumptions:
                print("      ⚠ AI 假设(需核实): %s" % "; ".join(assumptions))
    if not found:
        print("  （无待裁决条目）")


def apply_decision(data, cid, action, criteria, note, by):
    for c in data.get("candidates", []) or []:
        if c.get("id") != cid:
            continue
        hd = c.setdefault("human_decision", {})
        hd["decided_by"] = by
        hd["date"] = datetime.now().strftime("%Y-%m-%d")
        hd["note"] = note or hd.get("note", "")

        if action == "confirm":
            hd["status"] = "confirmed"
            hd["is_real_requirement"] = True
            c["becomes_acceptance_criteria"] = criteria
        elif action == "modify":
            hd["status"] = "modified"
            hd["is_real_requirement"] = True
            c["becomes_acceptance_criteria"] = criteria
        elif action == "reject":
            hd["status"] = "rejected"
            hd["is_real_requirement"] = False
        elif action == "defer":
            hd["status"] = "deferred"
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description="逆向需求人工裁决")
    parser.add_argument("candidates", help="reverse-spec-candidates.yml 路径")
    parser.add_argument("--list", action="store_true", help="列出待裁决条目")
    parser.add_argument("--id", help="候选 ID，如 RC-002")
    parser.add_argument("--action", choices=["confirm", "modify", "reject", "defer"],
                        help="裁决动作")
    parser.add_argument("--criteria", help="验收条件（confirm/modify 必填）")
    parser.add_argument("--note", help="备注（reject 建议填，说明为何是 bug/债）")
    parser.add_argument("--by", default="human", help="裁决人")
    args = parser.parse_args()

    path = Path(args.candidates)
    if not path.exists():
        print("文件不存在: %s" % path)
        sys.exit(1)

    data = load(path)

    if args.list or not args.action:
        list_pending(data)
        return

    if args.action in ("confirm", "modify") and not args.criteria:
        print("%s 需要 --criteria 指定验收条件" % args.action)
        sys.exit(1)
    if not args.id:
        print("需要 --id 指定候选条目")
        sys.exit(1)

    ok = apply_decision(data, args.id, args.action, args.criteria, args.note, args.by)
    if not ok:
        print("未找到候选: %s" % args.id)
        sys.exit(1)

    save(path, data)
    print("✅ %s 已裁决为 %s（by %s）" % (args.id, args.action, args.by))


if __name__ == "__main__":
    main()
