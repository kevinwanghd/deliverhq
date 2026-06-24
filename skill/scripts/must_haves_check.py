#!/usr/bin/env python3
"""
must_haves_check.py —— must_haves 谓词校验器（借 GSD must_haves 判据语法）

**定位（重要）**：这是给 DeliverHQ 已有的**确定性 Python 门禁**补一套"目标倒推"判据语法，
不是向 GSD 的 agent-verifier 看齐。GSD 的 must_haves 由 LLM agent 事后判断；这里全部是
确定性文件/内容断言，与 DeliverHQ "信证据不信声明" 一致。

校验 verification-manifest.yml 的 `must_haves` 段——用字面、可机器判定的谓词断言
"建出来的 = 计划的"：
  - key_links: 文件级关联（from/to 文件存在 + via 文件中包含 pattern）
  - artifacts: 产物断言（path 存在 + min_lines / exports[] / contains[]）
  - 反 stub: forbid[] 中的占位串（TODO/NotImplemented/pass-only）出现即 fail

manifest 中无 `must_haves` 段 → 跳过（向后兼容，不阻断既有 CR）。
所有路径相对 --root（默认 CR 所在仓库根，即 DeliverHQ 上一级）解析。

跨平台 / Python 3.10+。

用法：
  python must_haves_check.py <CR目录> [--root <仓库根>]
  python must_haves_check.py <CR目录> --json
exit: 0=PASS 或无 must_haves；1=BLOCKED；2=输入/解析错误
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


DEFAULT_FORBID = ["TODO", "FIXME", "NotImplementedError", "raise NotImplemented", "// stub", "# stub"]


def _resolve_root(cr_dir, root_override):
    if root_override:
        return Path(root_override).resolve()
    # CR 在 <root>/DeliverHQ/change-requests/CR-x → 仓库根是 DeliverHQ 的上一级
    # 找最近的含 .git/package.json 的祖先，兜底 cr_dir 上三级
    p = cr_dir.resolve()
    for anc in [p] + list(p.parents):
        if (anc / ".git").exists() or (anc / "package.json").exists():
            return anc
    return p.parents[2] if len(p.parents) >= 3 else p


def _read(path):
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None


def check_key_links(links, root):
    blockers = []
    for i, link in enumerate(links or []):
        frm = link.get("from")
        to = link.get("to")
        via = link.get("via")
        pattern = link.get("pattern")
        label = link.get("name") or ("key_link[%d]" % i)

        if frm and not (root / frm).exists():
            blockers.append("%s: from 文件不存在 %s" % (label, frm))
        if to and not (root / to).exists():
            blockers.append("%s: to 文件不存在 %s" % (label, to))
        # via 文件中必须包含 pattern（证明关联真实建立，而非仅文件存在）
        if via and pattern:
            text = _read(root / via)
            if text is None:
                blockers.append("%s: via 文件不可读 %s" % (label, via))
            elif not re.search(pattern, text):
                blockers.append("%s: %s 中未找到关联模式 /%s/" % (label, via, pattern))
    return blockers


def check_artifacts(artifacts, root):
    blockers = []
    for i, art in enumerate(artifacts or []):
        path = art.get("path")
        label = art.get("name") or path or ("artifact[%d]" % i)
        if not path:
            blockers.append("%s: 缺 path" % label)
            continue
        fp = root / path
        if not fp.exists():
            blockers.append("%s: 产物不存在 %s" % (label, path))
            continue
        text = _read(fp) or ""

        min_lines = art.get("min_lines")
        if isinstance(min_lines, int):
            n = len([ln for ln in text.splitlines() if ln.strip()])
            if n < min_lines:
                blockers.append("%s: 非空行 %d < min_lines %d（疑似 stub）" % (label, n, min_lines))

        for exp in art.get("exports", []) or []:
            # 语言无关的弱断言：标识符以词边界出现（def/function/export/class 名等）
            if not re.search(r"\b%s\b" % re.escape(exp), text):
                blockers.append("%s: 未导出/定义 %s" % (label, exp))

        for needle in art.get("contains", []) or []:
            if needle not in text:
                blockers.append("%s: 不包含必需内容 %r" % (label, needle))

        forbid = art.get("forbid", DEFAULT_FORBID) if art.get("anti_stub", True) else art.get("forbid", [])
        for bad in forbid or []:
            if bad in text:
                blockers.append("%s: 含禁止的占位/stub 标记 %r" % (label, bad))
    return blockers


def check_must_haves(cr_dir, root):
    manifest_path = cr_dir / "verification-manifest.yml"
    if not manifest_path.exists():
        return None, ["verification-manifest.yml 不存在"]
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return None, ["解析 verification-manifest.yml 失败: %s" % e]

    mh = manifest.get("must_haves")
    if not mh:
        return "skip", []  # 无 must_haves 段，向后兼容跳过

    blockers = []
    blockers += check_key_links(mh.get("key_links", []), root)
    blockers += check_artifacts(mh.get("artifacts", []), root)
    return ("pass" if not blockers else "blocked"), blockers


def main():
    parser = argparse.ArgumentParser(description="must_haves 谓词校验（确定性，借 GSD 判据语法）")
    parser.add_argument("cr_path", help="CR 目录")
    parser.add_argument("--root", help="仓库根（默认自动定位）")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    cr_dir = Path(args.cr_path)
    if not cr_dir.exists():
        print("CR 目录不存在: %s" % cr_dir)
        sys.exit(2)

    root = _resolve_root(cr_dir, args.root)
    status, blockers = check_must_haves(cr_dir, root)

    if args.json:
        print(json.dumps({"status": status, "blockers": blockers, "root": str(root)},
                         ensure_ascii=False, indent=2))
    else:
        if status == "skip":
            print("⏭  manifest 无 must_haves 段，跳过（向后兼容）")
        elif status == "pass":
            print("✅ must_haves PASS（所有谓词成立）")
        elif status is None:
            print("❌ must_haves 无法校验：")
            for b in blockers:
                print("  - %s" % b)
        else:
            print("❌ must_haves BLOCKED：")
            for b in blockers:
                print("  - %s" % b)

    if status in ("pass", "skip"):
        sys.exit(0)
    sys.exit(1 if status == "blocked" else 2)


if __name__ == "__main__":
    main()
