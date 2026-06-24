#!/usr/bin/env python3
"""
capability_tiers.py —— 能力调用分层（借 Matt Pocock 双轴调用模型）

把 CAPABILITY-MATRIX.md 的能力按"调用轴"分两层，遏制能力膨胀（张力1）：

  - core（model-invoked，常驻 context）：默认流程里每轮都应被 Agent 感知的能力。
    判据：default_enabled == true（是否在默认链路，由矩阵单一事实源决定；与成熟度 status 解耦）。
  - on-demand（user-invoked，零 per-turn 成本）：非默认/罕用/路线图能力。
    仅在显式需要时按需加载，不占每轮上下文。

这条派生规则让"哪些能力常驻"变成**从矩阵 default_enabled 列机器推导**的，而非随手往入口文档堆。
新增一个 default_enabled=false 的能力自动落到 on-demand，不会无声进入每轮 context。

跨平台 / Python 3.10+。

用法：
  python capability_tiers.py            # 打印两层清单 + 计数
  python capability_tiers.py --tier core
  python capability_tiers.py --tier on-demand
  python capability_tiers.py --json
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MATRIX = ROOT / "CAPABILITY-MATRIX.md"


def parse_matrix(text=None):
    """解析 CAPABILITY-MATRIX.md 的能力表，返回 [{name,status,default_enabled,...}]。"""
    if text is None:
        text = MATRIX.read_text(encoding="utf-8")
    rows = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 6:
            continue
        name = cells[0]
        # 跳过表头与分隔行
        if name in ("能力", "") or set(name) <= {"-", ":"}:
            continue
        status = cells[2]
        if status not in ("stable", "experimental", "placeholder", "roadmap"):
            continue  # 非能力行
        rows.append({
            "name": name,
            "script": cells[1],
            "status": status,
            "integrated": cells[3],
            "default_enabled": cells[4].lower() == "true",
            "allowed_in_pipeline": cells[5].lower() == "true",
        })
    return rows


def classify(rows):
    core, on_demand = [], []
    for r in rows:
        if r["default_enabled"]:
            core.append(r)
        else:
            on_demand.append(r)
    return core, on_demand


def main():
    parser = argparse.ArgumentParser(description="能力调用分层（Pocock 双轴）")
    parser.add_argument("--tier", choices=["core", "on-demand"], help="只列某一层")
    parser.add_argument("--json", action="store_true", help="机器可读")
    args = parser.parse_args()

    if not MATRIX.exists():
        print("CAPABILITY-MATRIX.md 不存在")
        sys.exit(1)

    rows = parse_matrix()
    core, on_demand = classify(rows)

    if args.json:
        print(json.dumps({
            "core": [r["name"] for r in core],
            "on_demand": [r["name"] for r in on_demand],
            "counts": {"core": len(core), "on_demand": len(on_demand), "total": len(rows)},
        }, ensure_ascii=False, indent=2))
        return

    if args.tier == "core":
        for r in core:
            print(r["name"])
        return
    if args.tier == "on-demand":
        for r in on_demand:
            print(r["name"])
        return

    print("=== core（model-invoked，常驻 context；stable+default_enabled）===")
    for r in core:
        print("  %s" % r["name"])
    print("\n=== on-demand（user-invoked，零 per-turn 成本；按需加载）===")
    for r in on_demand:
        print("  [%s] %s" % (r["status"], r["name"]))
    print("\n计数：core=%d, on-demand=%d, total=%d" % (len(core), len(on_demand), len(rows)))


if __name__ == "__main__":
    main()
