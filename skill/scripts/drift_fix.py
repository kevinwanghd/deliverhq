#!/usr/bin/env python3
"""
drift_fix.py —— PRD↔CR 漂移修复工具

用法:
  # 查看 drift 和建议
  python drift_fix.py <CR目录>

  # 自动修复: PRD → CR（PRD 已改，同步到 acceptance-spec 的 prd_hash）
  python drift_fix.py <CR目录> --direction prd-to-cr

  # 自动修复: CR → PRD（CR 已改，同步 PRD 锚点内容）
  python drift_fix.py <CR目录> --direction cr-to-prd

  # 强制修复（跳过确认）
  python drift_fix.py <CR目录> --direction prd-to-cr --force

修复后需重新过 SpecGate 验证。
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


def _is_assoc_line(line):
    """识别「关联 CR」行(允许 markdown 粗体 ** 与缩进)。"""
    s = line.lstrip()
    while s.startswith('*'):
        s = s[1:]
    return s.startswith('关联 CR')


def _anchor_hash(prd_text, anchor_id):
    """锚点章节哈希，排除「关联 CR」行。"""
    section = _anchor_section(prd_text, anchor_id)
    if section is None:
        return None
    kept = [l for l in section.splitlines() if not _is_assoc_line(l)]
    norm = '\n'.join(kept).strip()
    return hashlib.sha256(norm.encode('utf-8')).hexdigest()[:12]


def diagnose_drift(cr_dir, root):
    """诊断 drift，返回当前状态和建议。"""
    spec = cr_dir / 'acceptance-spec.md'
    prd = root / 'docs' / 'PRD.md'

    if not spec.exists():
        return None, "acceptance-spec.md 不存在"

    text = spec.read_text(encoding='utf-8')
    dm = DERIVED_RE.search(text)
    if not dm:
        return None, "acceptance-spec 无 derived_from.prd_section"

    anchor = dm.group(1)
    if not prd.exists():
        return None, "docs/PRD.md 不存在"

    prd_text = prd.read_text(encoding='utf-8')
    cur_hash = _anchor_hash(prd_text, anchor)
    hm = PRD_HASH_RE.search(text)
    recorded_hash = hm.group(1) if hm else None

    spec_mtime = spec.stat().st_mtime
    prd_mtime = prd.stat().st_mtime

    is_match = (recorded_hash == cur_hash)
    direction = None
    if not is_match:
        if prd_mtime > spec_mtime:
            direction = "prd-to-cr"
        elif spec_mtime > prd_mtime:
            direction = "cr-to-prd"
        else:
            direction = "manual"

    return {
        "anchor": anchor,
        "current_hash": cur_hash,
        "recorded_hash": recorded_hash,
        "is_match": is_match,
        "direction": direction,
        "prd_mtime": prd_mtime,
        "spec_mtime": spec_mtime,
    }, None


def fix_prd_to_cr(cr_dir, root, dry_run=False):
    """修复: PRD → CR（更新 acceptance-spec 的 prd_hash 为当前 PRD 锚点哈希）。"""
    spec = cr_dir / 'acceptance-spec.md'
    prd = root / 'docs' / 'PRD.md'

    text = spec.read_text(encoding='utf-8')
    dm = DERIVED_RE.search(text)
    if not dm:
        return False, "未找到 prd_section"

    anchor = dm.group(1)
    prd_text = prd.read_text(encoding='utf-8')
    new_hash = _anchor_hash(prd_text, anchor)

    if not new_hash:
        return False, f"PRD 中找不到锚点 {anchor}"

    # 替换 prd_hash
    new_text = PRD_HASH_RE.sub(lambda m: f'prd_hash: "{new_hash}"', text, count=1)

    if dry_run:
        print("=== DRY RUN: 以下是替换后的内容片段 ===")
        for i, line in enumerate(new_text.splitlines()[:10], 1):
            print(f"  {i}: {line}")
        print(f"  ... (共 {len(new_text.splitlines())} 行)")
        return True, None

    spec.write_text(new_text, encoding='utf-8')
    return True, f"已更新 prd_hash → {new_hash}（{anchor}）"


def fix_cr_to_prd(cr_dir, root, dry_run=False):
    """修复: CR → PRD（在 PRD 锚点后追加说明本次 CR 已覆盖）。"""
    spec = cr_dir / 'acceptance-spec.md'
    prd = root / 'docs' / 'PRD.md'

    text = spec.read_text(encoding='utf-8')
    dm = DERIVED_RE.search(text)
    if not dm:
        return False, "未找到 prd_section"

    cr_id = cr_dir.name
    anchor = dm.group(1)

    prd_text = prd.read_text(encoding='utf-8')
    section = _anchor_section(prd_text, anchor)
    if not section:
        return False, f"PRD 中找不到锚点 {anchor}"

    # 在锚点章节末尾追加
    note_line = f"\n**关联 CR**: {cr_id}\n"
    new_prd_text = prd_text.replace(section, section.rstrip() + note_line, 1)

    if dry_run:
        print("=== DRY RUN: 以下是替换后的 PRD 锚点片段 ===")
        new_section = _anchor_section(new_prd_text, anchor)
        for i, line in enumerate((new_section or section).splitlines()[-5:], 1):
            print(f"  {i}: {line}")
        return True, None

    prd.write_text(new_prd_text, encoding='utf-8')
    return True, f"已在 PRD 锚点 {anchor} 追加关联 CR: {cr_id}"


def main():
    parser = argparse.ArgumentParser(description='PRD↔CR 漂移修复工具')
    parser.add_argument('cr_path', help='CR 目录路径')
    parser.add_argument('--root', default=None, help='skill 根目录（默认推断为 CR 目录的上两级）')
    parser.add_argument('--direction', choices=['prd-to-cr', 'cr-to-prd'],
                        help='修复方向')
    parser.add_argument('--force', action='store_true', help='跳过确认')
    parser.add_argument('--dry-run', action='store_true', help='仅显示修改内容，不实际写入')
    args = parser.parse_args()

    cr_dir = Path(args.cr_path).resolve()
    if not cr_dir.exists():
        print(f"CR 目录不存在: {cr_dir}")
        sys.exit(1)

    root = Path(args.root).resolve() if args.root else cr_dir.parent.parent

    # 诊断
    diagnosis, err = diagnose_drift(cr_dir, root)
    if err:
        print(f"⚠️  {err}")
        sys.exit(1)

    print("=== Drift 诊断 ===")
    print(f"  锚点: {diagnosis['anchor']}")
    print(f"  PRD 锚点当前哈希: {diagnosis['current_hash']}")
    print(f"  acceptance-spec 记录的哈希: {diagnosis['recorded_hash'] or '∅'}")

    if diagnosis['is_match']:
        print("\n✅ 无 Drift（哈希一致）")
        sys.exit(0)

    print(f"\n⚠️  检测到 Drift")
    print(f"  建议修复方向: {diagnosis['direction']}")

    if not args.direction:
        print("\n用法:")
        print(f"  python drift_fix.py {cr_dir} --direction {diagnosis['direction']} [--force]")
        print(f"  python drift_fix.py {cr_dir} --dry-run --direction {diagnosis['direction']}")
        sys.exit(1)

    if args.dry_run:
        print("\n=== DRY RUN MODE ===")

    if args.direction == 'prd-to-cr':
        success, msg = fix_prd_to_cr(cr_dir, root, dry_run=args.dry_run)
    else:
        success, msg = fix_cr_to_prd(cr_dir, root, dry_run=args.dry_run)

    if success:
        print(f"\n✅ {msg}")
        if not args.dry_run:
            print("\n⚠️  修复后需重新过 SpecGate 验证:")
            print(f"   python scripts/specgate.py {cr_dir}")
    else:
        print(f"\n❌ 修复失败: {msg}")
        sys.exit(1)


if __name__ == '__main__':
    main()
