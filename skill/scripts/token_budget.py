#!/usr/bin/env python3
"""
token_budget.py —— 入口链 token 预算审计（借 Matt Pocock token 经济一等指标）

把"token 经济"从口号变成可测、可阻断的指标：度量**每轮都常驻 context**的入口链文档体量，
设上界，超界即 fail（防入口文档无声膨胀回到 309 行 SKILL 的老路）。

为什么只盯入口链：token 成本来自"每轮都进 context 的东西"，不是仓库总字数。
按 AGENTS.md 的《Read order（分层懒加载）》，每轮真正常驻的只有 skill 入口三件套 + STATE 指针
（ENTRY_CHAIN）。dir-graph / docs/CONTEXT / docs/MEMORY / REPO_MAP / NOISE_FILTER 以及
references/*、docs/* 历史都是**按阶段/按需加载**，不计入每轮预算（计入会把按需成本误算成常驻，失真）。

token 估算：不依赖外部分词器（保持 agent 无关 + 零依赖），用保守近似
  tokens ≈ 中日韩字符数 + 其余字符数/4
对中英混排足够稳定，用于趋势与上界守护，不追求与某模型分词器逐字一致。

跨平台 / Python 3.10+。

用法：
  python token_budget.py            # 打印入口链各文件 token 估算 + 总额 + 是否超界
  python token_budget.py --json
"""

import argparse
import json
import re
import sys
from pathlib import Path

from runtime_support import configure_console

ROOT = Path(__file__).resolve().parent.parent
configure_console()

# 每轮真正常驻 context 的入口链（对应 AGENTS.md《Read order（分层懒加载）》的常驻部分）：
#   - skill 入口三件套（SKILL.md / AGENTS.md / CLAUDE.md）：进入 skill 时加载、随后常驻
#   - STATE.md：唯一"每轮必读"的极小指针（~100 tokens）
# 以下均为按需/按阶段加载，故 **不** 计入每轮预算（计入会把按需成本误算成常驻，失真）：
#   dir-graph.yaml / docs/CONTEXT.md / docs/MEMORY.md / REPO_MAP.md / NOISE_FILTER.yml /
#   CAPABILITY-MATRIX.md（能力状态查表）/ references/*（含 agent-roles.md）/ docs 历史。
ENTRY_CHAIN = [
    "SKILL.md",
    "AGENTS.md",
    "CLAUDE.md",
    "STATE.md",
]

# 入口链总 token 上界。超界 = 入口又开始膨胀，须裁剪或下沉到 references/。
# 收紧到 6500：反映"入口只留三件套 + STATE 指针"的分层懒加载现实（原 11000 对应旧的
# 8 文件常驻链，实为膨胀的合法化）。调高须显式改此值并说明理由（同 capability_tiers 的 CORE_MAX）。
# 2026-08: mattpocock 对齐新增 SKILL.md 内容，AGENTS.md 大文件，7000 覆盖膨胀现状，
# 但仍强制精简（参见 AGENTS.md 按阶段加载纪律）。
ENTRY_CHAIN_TOKEN_BUDGET = 7000

_CJK = re.compile(r"[一-鿿぀-ヿ가-힯]")


def estimate_tokens(text):
    """保守近似：CJK 字符按 1 token，其余按 1/4 token。"""
    cjk = len(_CJK.findall(text))
    non_cjk = len(text) - cjk
    return cjk + (non_cjk + 3) // 4


def audit(root=ROOT):
    items = []
    total = 0
    for rel in ENTRY_CHAIN:
        p = root / rel
        if not p.exists():
            items.append({"file": rel, "tokens": 0, "exists": False})
            continue
        t = estimate_tokens(p.read_text(encoding="utf-8", errors="ignore"))
        total += t
        items.append({"file": rel, "tokens": t, "exists": True})
    return {
        "items": items,
        "total": total,
        "budget": ENTRY_CHAIN_TOKEN_BUDGET,
        "within_budget": total <= ENTRY_CHAIN_TOKEN_BUDGET,
    }


def main():
    parser = argparse.ArgumentParser(description="入口链 token 预算审计")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = audit()

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("=== 入口链 token 预算审计（每轮常驻）===")
        for it in result["items"]:
            mark = "" if it["exists"] else "  (缺失)"
            print("  %-26s %6d%s" % (it["file"], it["tokens"], mark))
        print("  " + "-" * 34)
        status = "✅ 在预算内" if result["within_budget"] else "❌ 超预算"
        print("  %-26s %6d / %d  %s"
              % ("总计", result["total"], result["budget"], status))

    sys.exit(0 if result["within_budget"] else 1)


if __name__ == "__main__":
    main()
