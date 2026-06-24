#!/usr/bin/env python3
"""
lane_advisor.py —— 客观规模分档建议器（借 GSD 客观阈值 + BMAD Quick Flow）

目的：用**可计算的规模信号**把小 CR 路由到轻量道（fast），免去对小改动套全套
~10 件证据；超过硬阈值则建议**拆分 CR**（借 GSD：是"挡回让人重规划"，不是自动拆）。

它**不是新命令、不是新 Gate**：只是一个建议器，由 `pre_dev_gate.py --suggest-lane`
调用，或人工单独运行参考。最终 lane 仍写在 state.yml，由 PreDevGate 执行。

客观信号（全部可计算，不靠主观判断）：
  - changed_files：traceability.yml 的 implementation[].file 去重数；缺则取 plan.yml 的 files 并集
  - ac_count：acceptance-spec.md 的 AC-N 数（无则数 "### 场景"）
  - sensitive：acceptance-spec.md / traceability 命中敏感域关键词（auth/payment/...）

分档规则（阈值集中在 THRESHOLDS，便于审计）：
  - 命中敏感域            → high-risk（敏感域永不降级，借 scan_legacy 同口径）
  - files ≤ 2 且 ac ≤ 2  → fast（轻量道）
  - files > SPLIT 或 ac > SPLIT_AC → 建议拆分（exit 2，输出 SPLIT 建议）
  - 其余                  → standard

跨平台 / Python 3.10+。

用法：
  python lane_advisor.py <CR目录>                 # 打印建议 lane
  python lane_advisor.py <CR目录> --json          # 机器可读
  python lane_advisor.py <CR目录> --explain       # 附信号明细
exit: 0=有明确 lane 建议；2=建议拆分（超硬阈值）；1=输入错误
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("需要 PyYAML：pip install PyYAML")
    sys.exit(2)


THRESHOLDS = {
    "fast_files": 2,     # ≤ 此值且 AC 少 → fast
    "fast_ac": 2,
    "split_files": 8,    # > 此值 → 建议拆分（GSD 8-10 files 量级）
    "split_ac": 10,
}

# 与 scan_legacy 同口径的敏感域关键词（命中即 high-risk，不降级）
SENSITIVE_KEYWORDS = [
    "auth", "login", "session", "token", "oauth", "credential",
    "payment", "billing", "charge", "refund", "checkout",
    "permission", "acl", "rbac", "authorize", "access_control",
    "crypto", "encrypt", "decrypt", "secret", "密码", "支付", "鉴权", "权限",
]


def _count_changed_files(cr_dir):
    """优先 traceability.yml 的 implementation[].file；回退 plan.yml 的 files 并集。"""
    files = set()
    trace = cr_dir / "traceability.yml"
    if trace.exists():
        try:
            data = yaml.safe_load(trace.read_text(encoding="utf-8")) or {}
            for key, val in data.items():
                if not isinstance(val, dict):
                    continue
                for impl in val.get("implementation", []) or []:
                    if isinstance(impl, dict) and impl.get("file"):
                        files.add(impl["file"])
        except Exception:
            pass
    if not files:
        plan = cr_dir / "plan.yml"
        if plan.exists():
            try:
                data = yaml.safe_load(plan.read_text(encoding="utf-8")) or {}
                for t in data.get("tasks", []) or []:
                    for f in (t.get("files", []) or []):
                        files.add(f)
            except Exception:
                pass
    return len(files)


def _count_ac(cr_dir):
    spec = cr_dir / "acceptance-spec.md"
    if not spec.exists():
        return 0
    content = spec.read_text(encoding="utf-8", errors="ignore")
    ac = len(set(re.findall(r"\bAC-\d+\b", content)))
    if ac:
        return ac
    return content.count("### 场景") + content.count("## 场景")


def _has_sensitive(cr_dir):
    hits = []
    for fname in ("acceptance-spec.md", "traceability.yml"):
        p = cr_dir / fname
        if not p.exists():
            continue
        low = p.read_text(encoding="utf-8", errors="ignore").lower()
        for kw in SENSITIVE_KEYWORDS:
            if kw in low and kw not in hits:
                hits.append(kw)
    return hits


def advise(cr_dir):
    cr_dir = Path(cr_dir)
    files = _count_changed_files(cr_dir)
    ac = _count_ac(cr_dir)
    sensitive = _has_sensitive(cr_dir)

    signals = {
        "changed_files": files,
        "ac_count": ac,
        "sensitive_domains": sensitive,
    }

    # 超硬阈值 → 建议拆分（不自动拆）
    if files > THRESHOLDS["split_files"] or ac > THRESHOLDS["split_ac"]:
        return {
            "decision": "split",
            "lane": None,
            "reason": "规模超阈值（files=%d>%d 或 ac=%d>%d），建议拆分为多个 CR 再开发"
                      % (files, THRESHOLDS["split_files"], ac, THRESHOLDS["split_ac"]),
            "signals": signals,
        }

    if sensitive:
        lane, reason = "high-risk", "命中敏感域 %s（不降级）" % "/".join(sensitive)
    elif files <= THRESHOLDS["fast_files"] and ac <= THRESHOLDS["fast_ac"]:
        lane, reason = "fast", "小改动（files=%d, ac=%d）走轻量道" % (files, ac)
    else:
        lane, reason = "standard", "中等规模（files=%d, ac=%d）走标准道" % (files, ac)

    return {"decision": "lane", "lane": lane, "reason": reason, "signals": signals}


def main():
    parser = argparse.ArgumentParser(description="客观规模分档建议器")
    parser.add_argument("cr_path", help="CR 目录")
    parser.add_argument("--json", action="store_true", help="机器可读输出")
    parser.add_argument("--explain", action="store_true", help="附信号明细")
    args = parser.parse_args()

    cr_dir = Path(args.cr_path)
    if not cr_dir.exists():
        print("CR 目录不存在: %s" % cr_dir)
        sys.exit(1)

    result = advise(cr_dir)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result["decision"] == "split":
            print("⚠ 建议拆分：%s" % result["reason"])
        else:
            print("建议 lane: %s（%s）" % (result["lane"], result["reason"]))
        if args.explain:
            s = result["signals"]
            print("  信号: changed_files=%d, ac_count=%d, sensitive=%s"
                  % (s["changed_files"], s["ac_count"], s["sensitive_domains"] or "无"))

    sys.exit(2 if result["decision"] == "split" else 0)


if __name__ == "__main__":
    main()
