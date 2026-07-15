#!/usr/bin/env python3
"""
prd_writeback.py —— PRD 锚点的「关联 CR」行回填(原 PRD-LAYER-DESIGN 承诺的 writeback-agent)

设计文档(dev/docs/PRD-LAYER-DESIGN.md)承诺有一个 writeback-agent,在 CR 完成后回填
docs/PRD.md 锚点章节的「关联 CR」行(反向索引),好让人翻 PRD 就能看到每个意图
挂了哪些 CR。原先这个承诺是"言而无功"——没有真正的脚本。本脚本补齐它。

不变式:
  1. 「关联 CR」行排除在锚点哈希之外(drift_check._anchor_hash 已实现)
     ⇒ 回填后再次 drift_check 应仍 PASS,绝不触发对账死循环
  2. 幂等:同一 CR 反复回填 ≡ 单次回填(去重 + 排序)
  3. 占位符 `{{由 writeback-agent...}}` 视为空,首次写入会替换它

用法:
  python prd_writeback.py <CR目录>               # 单 CR 回填
  python prd_writeback.py --all <skill根>        # 扫描所有 CR
  python prd_writeback.py <CR目录> --dry-run     # 只打印,不写

退出码:
  0 = 成功(无论是否真的写了)
  1 = 失败(CR 无 derived_from / PRD 无该锚点 / IO 错误)
"""

import argparse
import re
import sys
from pathlib import Path

from runtime_support import configure_console
from drift_check import _anchor_section, _anchor_hash, DERIVED_RE

configure_console()

# 「关联 CR」行的 3 种形态:
#   - 模板占位:`**关联 CR**: {{...}}`
#   - 已填值:  `**关联 CR**: CR-007, CR-012`
#   - 不带前缀的旧版:`关联 CR: CR-XXX`(向后兼容)
ASSOC_LINE_RE = re.compile(
    r'^(\s*\*?\*?关联 CR\*?\*?\s*[:：])\s*(.*?)\s*$',
    re.MULTILINE,
)
PLACEHOLDER_RE = re.compile(r'\{\{[^}]*\}\}')
CR_ID_RE = re.compile(r'\bCR-[A-Za-z0-9_\-]+\b')


def _extract_cr_id(cr_dir: Path) -> str:
    """从 CR 目录名取 CR ID(就用目录名)。"""
    return cr_dir.name


def _read_derived_from(spec_path: Path):
    """从 acceptance-spec 读 derived_from.prd_section,返回 anchor_id 或 None。"""
    if not spec_path.exists():
        return None
    text = spec_path.read_text(encoding="utf-8")
    m = DERIVED_RE.search(text)
    return m.group(1) if m else None


def _merge_cr_list(existing: str, new_cr: str):
    """合并 CR ID:占位符视为空;去重 + 按 ID 排序。返回 (new_value, changed)。"""
    if PLACEHOLDER_RE.search(existing):
        existing = PLACEHOLDER_RE.sub("", existing).strip().rstrip(",").strip()
    ids = set(CR_ID_RE.findall(existing))
    before = set(ids)
    ids.add(new_cr)
    if ids == before:
        return None, False
    return ", ".join(sorted(ids)), True


def writeback(prd_path: Path, anchor_id: str, cr_id: str, dry_run: bool = False):
    """对 prd_path 的 anchor_id 章节回填 cr_id。返回 (changed, message)。"""
    if not prd_path.exists():
        return False, "PRD 文件不存在: %s" % prd_path

    text = prd_path.read_text(encoding="utf-8")
    section = _anchor_section(text, anchor_id)
    if section is None:
        return False, "PRD 中找不到锚点 %s" % anchor_id

    hash_before = _anchor_hash(text, anchor_id)

    # 在锚点章节内定位「关联 CR」行
    line_match = ASSOC_LINE_RE.search(section)
    if line_match is None:
        return False, "锚点 %s 章节缺『关联 CR』行,跳过" % anchor_id

    prefix = line_match.group(1)
    existing_value = line_match.group(2)
    new_value, changed = _merge_cr_list(existing_value, cr_id)

    if not changed:
        return False, "%s 已记录在 %s 的关联 CR 中(幂等无操作)" % (cr_id, anchor_id)

    new_line = "%s %s" % (prefix, new_value)
    new_section = section[:line_match.start()] + new_line + section[line_match.end():]

    section_start = text.find(section)
    new_text = text[:section_start] + new_section + text[section_start + len(section):]

    if not dry_run:
        prd_path.write_text(new_text, encoding="utf-8")

    hash_after = _anchor_hash(new_text, anchor_id)
    if hash_before != hash_after:
        # 不应该发生:理论上「关联 CR」行不参与哈希
        return False, "⚠ 哈希不应改变但变了(before=%s after=%s),已回滚" % (hash_before, hash_after)

    return True, "回填 %s -> [%s]:%s(hash 不变 %s)" % (
        cr_id, anchor_id, new_value, hash_before)


def find_root(start: Path) -> Path:
    """从 CR 目录向上找 skill 根(含 docs/PRD.md)。"""
    p = start.resolve()
    for candidate in [p.parent.parent, p.parent, p]:
        if (candidate / "docs" / "PRD.md").exists():
            return candidate
    return p.parent.parent


def writeback_one(cr_dir: Path, root: Path, dry_run: bool):
    cr_id = _extract_cr_id(cr_dir)
    spec_path = cr_dir / "acceptance-spec.md"
    anchor = _read_derived_from(spec_path)
    if not anchor:
        return False, "%s 无 derived_from.prd_section,跳过" % cr_id
    return writeback(root / "docs" / "PRD.md", anchor, cr_id, dry_run)


def main():
    parser = argparse.ArgumentParser(description="PRD 锚点关联 CR 回填(writeback-agent)")
    parser.add_argument("cr_path", nargs="?", help="CR 目录路径(单 CR 模式)")
    parser.add_argument("--all", metavar="ROOT", help="扫描 ROOT/change-requests 下所有 CR")
    parser.add_argument("--root", default=None, help="skill 根目录(默认从 CR 路径推断)")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写")
    args = parser.parse_args()

    print("=== PRD Writeback ===")

    if args.all:
        root = Path(args.all).resolve()
        cr_root = root / "change-requests"
        if not cr_root.exists():
            print("change-requests 目录不存在: %s" % cr_root)
            sys.exit(1)
        any_failure = False
        for cr_dir in sorted(cr_root.iterdir()):
            if not cr_dir.is_dir() or cr_dir.name.startswith("CR-TEMPLATE"):
                continue
            ok, msg = writeback_one(cr_dir, root, args.dry_run)
            print(("✅ " if ok else "•  ") + msg)
            if not ok and "无 derived_from" not in msg and "已记录" not in msg:
                any_failure = True
        sys.exit(1 if any_failure else 0)

    if not args.cr_path:
        parser.print_help()
        sys.exit(1)

    cr_dir = Path(args.cr_path).resolve()
    if not cr_dir.exists():
        print("CR 目录不存在: %s" % cr_dir)
        sys.exit(1)
    root = Path(args.root).resolve() if args.root else find_root(cr_dir)

    ok, msg = writeback_one(cr_dir, root, args.dry_run)
    print(("✅ " if ok else "•  ") + msg)
    sys.exit(0 if ok or "已记录" in msg or "无 derived_from" in msg else 1)


if __name__ == "__main__":
    main()
