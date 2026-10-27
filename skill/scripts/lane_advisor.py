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
  - protected_paths：声明要改的文件命中 skill/dir-graph.yaml 的受保护路径（与 permissiongate.py 同口径）

分档规则（阈值集中在 THRESHOLDS，便于审计）：
  - 命中受保护路径        → high-risk（PermissionGate 只在 high-risk + exceptions.yml 豁免时放行）
  - 命中敏感域            → high-risk（敏感域永不降级，借 scan_legacy 同口径）
  - files ≤ 2 且 ac ≤ 2  → fast（轻量道）
  - files > SPLIT 或 ac > SPLIT_AC → 建议拆分（exit 2，输出 SPLIT 建议）
  - 其余                  → standard

与 PermissionGate 的口径一致性（重要）：
  PermissionGate 只在 lane=high-risk 且该 CR 的 exceptions.yml 里有
  gate_override{gate: PermissionGate, approved_by: 非空} 时才放行受保护路径改动。
  若建议器不知道 protected_paths，就会给出一个 standard lane 的建议，开发者照做
  必然在 PermissionGate 被 BLOCK —— 这就是"按建议走却撞墙"的根因。
  因此受保护路径命中必须直接判 high-risk（与 CR-FLOW-LANES.md
  「修改 protected_paths → 自动判定为 High-Risk」一致）。

跨平台 / Python 3.10+。

用法：
  python lane_advisor.py <CR目录>                 # 打印建议 lane
  python lane_advisor.py <CR目录> --json          # 机器可读
  python lane_advisor.py <CR目录> --explain       # 附信号明细
exit: 0=有明确 lane 建议；2=建议拆分（超硬阈值）；1=输入错误
"""

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path
from common import load_yaml, load_yaml_all
from runtime_support import configure_console

DELIVERHQ_ROOT = Path(__file__).resolve().parent.parent

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


def _changed_file_list(cr_dir):
    """优先 traceability.yml 的 implementation[].file；回退 plan.yml 的 files 并集。"""
    files = set()
    trace = cr_dir / "traceability.yml"
    if trace.exists():
        try:
            data = load_yaml(trace)
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
                data = load_yaml(plan)
                for t in data.get("tasks", []) or []:
                    for f in (t.get("files", []) or []):
                        files.add(f)
            except Exception:
                pass
    return files


def _count_changed_files(cr_dir):
    return len(_changed_file_list(cr_dir))


def _load_protected_paths():
    """读 skill/dir-graph.yaml 的 protected_paths（与 permissiongate.py 同口径）。

    口径必须一致：permissiongate 去掉 "../" 前缀后用 fnmatch 匹配仓库根相对路径，
    这里照抄，否则建议器与门禁对"哪些算受保护路径"的判断会分叉。
    """
    graph = DELIVERHQ_ROOT / "dir-graph.yaml"
    if not graph.exists():
        return []
    try:
        # dir-graph.yaml 是多文档 YAML（permissiongate.py 同口径用 load_yaml_all 合并）
        merged = {}
        for doc in load_yaml_all(graph.read_text(encoding="utf-8")):
            if isinstance(doc, dict):
                merged.update(doc)
    except Exception:
        return []
    patterns = []
    for pattern in merged.get("protected_paths", []) or []:
        if not isinstance(pattern, str):
            continue
        p = pattern.strip()
        if not p:
            continue
        if p.startswith("../"):
            p = p[3:]
        patterns.append(p)
    return patterns


def _protected_hits(files):
    """返回 [(pattern, file)]：声明要改的文件里命中受保护路径的。"""
    patterns = _load_protected_paths()
    hits = []
    for f in sorted(files):
        norm = str(f).replace("\\", "/").strip()
        while norm.startswith("./"):
            norm = norm[2:]
        while norm.startswith("../"):
            norm = norm[3:]
        for pat in patterns:
            if fnmatch.fnmatch(norm, pat) and (pat, f) not in hits:
                hits.append((pat, f))
    return hits


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
    file_list = _changed_file_list(cr_dir)
    files = len(file_list)
    ac = _count_ac(cr_dir)
    sensitive = _has_sensitive(cr_dir)
    protected = _protected_hits(file_list)

    signals = {
        "changed_files": files,
        "ac_count": ac,
        "sensitive_domains": sensitive,
        "protected_paths": [f for _, f in protected],
    }

    # 超硬阈值 → 建议拆分（不自动拆）
    if files > THRESHOLDS["split_files"] or ac > THRESHOLDS["split_ac"]:
        reason = ("规模超阈值（files=%d>%d 或 ac=%d>%d），建议拆分为多个 CR 再开发"
                  % (files, THRESHOLDS["split_files"], ac, THRESHOLDS["split_ac"]))
        if protected:
            reason += "；其中命中受保护路径 %s，拆分后仍需 high-risk + exceptions.yml 豁免" \
                      % "/".join(sorted({p for p, _ in protected}))
        return {
            "decision": "split",
            "lane": None,
            "reason": reason,
            "signals": signals,
        }

    if protected:
        lane, reason = "high-risk", (
            "命中受保护路径 %s（不降级）：PermissionGate 只在 high-risk 且该 CR 的 "
            "exceptions.yml 有 gate_override{gate: PermissionGate, approved_by: 非空} 时放行"
            % "/".join(sorted({p for p, _ in protected}))
        )
    elif sensitive:
        lane, reason = "high-risk", "命中敏感域 %s（不降级）" % "/".join(sensitive)
    elif files <= THRESHOLDS["fast_files"] and ac <= THRESHOLDS["fast_ac"]:
        lane, reason = "fast", "小改动（files=%d, ac=%d）走轻量道" % (files, ac)
    else:
        lane, reason = "standard", "中等规模（files=%d, ac=%d）走标准道" % (files, ac)

    return {"decision": "lane", "lane": lane, "reason": reason, "signals": signals}


def main():
    configure_console()
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
            prot = s.get("protected_paths") or []
            print("  受保护路径: %s" % (", ".join(prot) if prot else "无"))
            if prot:
                print("  放行条件: state.yml 的 lane=high-risk，且本 CR 的 exceptions.yml 需含")
                print("            gate_override{gate: PermissionGate, reason: ..., approved_by: 非空}")

    sys.exit(2 if result["decision"] == "split" else 0)


if __name__ == "__main__":
    main()
