#!/usr/bin/env python3
"""
drift_check.py —— PRD ↔ CR 漂移对账（产品意图唯一来源轴）

PRD（docs/PRD.md）是产品意图的唯一来源；每个 CR 的 acceptance-spec 通过
derived_from{prd_section, prd_hash} 派生自某个 PRD 功能锚点。

本检查重算该锚点当前内容哈希，与 CR 记录的 prd_hash 比对：
  - 一致           → PASS（静默）
  - 不一致(confirmed 锚点) → 需对账（NEED_HUMAN_DECISION，交给 SpecGate 裁决）
  - 不一致(reverse-engineered 锚点) → 仅警告（老项目放宽）
  - CR 无 derived_from   → 警告：CR 未链接 PRD

哈希范围 = 单个锚点章节（## [PRD-XXX] ... 到下一个 ##），
排除「关联 CR」行（由 writeback-agent 回填，计入会自触发对账死循环）。
修改 PRD 第一部分叙事不改变任何锚点哈希，不触发对账。

跨平台 / Python 3.10+。

用法:
  python drift_check.py <CR目录>
  python drift_check.py <CR目录> --root <skill根目录>
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path

from runtime_support import configure_console

configure_console()

DERIVED_RE = re.compile(r'prd_section:\s*([A-Za-z0-9_\-]+)')
PRD_HASH_RE = re.compile(r'prd_hash:\s*["\']?([0-9a-f]+)["\']?')


def _anchor_section(prd_text, anchor_id):
    """返回单个 PRD 锚点章节文本（## [ID] ... 到下一个 ##）。"""
    m = re.search(r'^##\s*\[' + re.escape(anchor_id) + r'\].*$', prd_text, re.M)
    if not m:
        return None
    rest = prd_text[m.end():]
    nxt = re.search(r'^##\s', rest, re.M)
    return prd_text[m.start(): m.end() + (nxt.start() if nxt else len(rest))]


def _anchor_hash(prd_text, anchor_id):
    """锚点章节哈希，排除「关联 CR」行。"""
    section = _anchor_section(prd_text, anchor_id)
    if section is None:
        return None
    kept = [l for l in section.splitlines() if not l.lstrip().startswith('关联 CR')]
    norm = '\n'.join(kept).strip()
    return hashlib.sha256(norm.encode('utf-8')).hexdigest()[:12]


def check_drift(cr_dir, root):
    blockers = []
    warnings = []

    spec = cr_dir / 'acceptance-spec.md'
    if not spec.exists():
        warnings.append('acceptance-spec.md 不存在，跳过 PRD↔CR 对账')
        return blockers, warnings

    text = spec.read_text(encoding='utf-8')
    dm = DERIVED_RE.search(text)
    if not dm:
        warnings.append('acceptance-spec 无 derived_from.prd_section（CR 未链接 PRD）')
        return blockers, warnings

    anchor = dm.group(1)
    prd = root / 'docs' / 'PRD.md'
    if not prd.exists():
        warnings.append('docs/PRD.md 不存在，无法对账')
        return blockers, warnings

    prd_text = prd.read_text(encoding='utf-8')
    cur = _anchor_hash(prd_text, anchor)
    if cur is None:
        warnings.append('PRD 中找不到锚点 %s' % anchor)
        return blockers, warnings

    hm = PRD_HASH_RE.search(text)
    recorded = hm.group(1) if hm else ''
    section = _anchor_section(prd_text, anchor) or ''
    is_reverse = bool(re.search(r'(状态|status)[^\n]*reverse-engineered', section))

    if recorded != cur:
        msg = 'reconcile: %s (cr_hash %s vs current %s)' % (anchor, recorded or '∅', cur)
        if is_reverse:
            warnings.append('%s [reverse-engineered 锚点，仅警告]' % msg)
        else:
            warnings.append('%s [confirmed 锚点 → SpecGate NEED_HUMAN_DECISION]' % msg)

    return blockers, warnings


def main():
    parser = argparse.ArgumentParser(description='PRD↔CR 漂移对账')
    parser.add_argument('cr_path', help='CR 目录路径')
    parser.add_argument('--root', default=None, help='skill 根目录（默认推断为 CR 目录的上两级）')
    args = parser.parse_args()

    cr_dir = Path(args.cr_path).resolve()
    if not cr_dir.exists():
        print('CR 目录不存在: %s' % cr_dir)
        sys.exit(1)

    root = Path(args.root).resolve() if args.root else cr_dir.parent.parent

    blockers, warnings = check_drift(cr_dir, root)

    print('=== DriftCheck (PRD↔CR) ===')
    if not blockers and not warnings:
        print('✅ PASS：PRD↔CR 一致')
        sys.exit(0)
    if warnings:
        print('⚠️  警告:')
        for w in warnings:
            print('  - %s' % w)
    if blockers:
        print('❌ BLOCKED:')
        for b in blockers:
            print('  - %s' % b)
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
