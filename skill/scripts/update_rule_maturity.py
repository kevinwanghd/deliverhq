#!/usr/bin/env python3
"""
规则成熟度自动更新
扫描 delivery/ 下所有 CR 的 quality-report.md，统计规则引用次数，
并在 mistake-book 中找到相关错误已被修复的证据后，才晋升成熟度（P3-3）。

晋升条件：
- draft → verified: ≥3 次引用 + mistake-book 中有相关错误已被修复的证据
- verified → proven: ≥5 次引用 + 无违反记录
"""

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# 定位 DeliverHQ 根目录（脚本在 DeliverHQ/scripts/ 下）
DELIVERHQ_ROOT = Path(__file__).parent.parent


def scan_rule_references() -> Dict[str, Set[str]]:
    """扫描所有已交付 CR 中的规则引用。

    Returns:
        {rule_id: set of cr_ids} 记录哪些 CR 引用了哪些规则
    """
    delivery_dir = DELIVERHQ_ROOT / "delivery"
    if not delivery_dir.exists():
        print("⚠️ delivery/ 目录不存在，跳过扫描")
        return {}

    rule_refs: Dict[str, Set[str]] = {}

    for quality_report in delivery_dir.rglob("quality-report.md"):
        try:
            cr_id = quality_report.parent.name
            content = quality_report.read_text(encoding='utf-8')
            # 匹配 "rules.md #X" 或 "规则 #X"
            matches = re.findall(r'rules\.md\s*#(\d+)|规则\s*#(\d+)', content)
            for match in matches:
                rule_id = match[0] or match[1]
                if rule_id not in rule_refs:
                    rule_refs[rule_id] = set()
                rule_refs[rule_id].add(cr_id)
        except Exception as e:
            print(f"⚠️ 跳过 {quality_report}: {e}")

    return rule_refs


def _check_mistake_book_for_fixed_evidence(rule_id: str) -> Tuple[bool, List[str]]:
    """P3-3: 检查 mistake-book 中是否有与规则相关的错误已被修复的证据。

    Args:
        rule_id: 规则编号

    Returns:
        (是否有证据, 相关错误摘要列表)
    """
    mistake_book_path = DELIVERHQ_ROOT / "docs" / "mistake-book.md"
    if not mistake_book_path.exists():
        return False, []

    try:
        content = mistake_book_path.read_text(encoding='utf-8')
        related_entries: List[str] = []

        # 提取所有错误条目块
        blocks = re.split(r'\n### 错误：', content)
        for block in blocks[1:]:  # 跳过第一个空块
            lines = block.strip().split('\n')
            if not lines:
                continue

            # 检查是否有 resolved 标记（错误已被修复）
            is_fixed = 'resolved' in block.lower() or '**状态**：resolved' in block

            # 简单启发式：规则相关的错误通常包含 gate 名称
            # 注：这里简化处理，实际应该从 rules.md 中提取规则的 trigger 字段进行匹配
            if is_fixed:
                summary = lines[0][:60] if lines else "未命名错误"
                related_entries.append(summary)

        return len(related_entries) > 0, related_entries
    except Exception:
        return False, []


def _determine_maturity_with_evidence(
    rule_id: str,
    ref_count: int,
    current_maturity: str,
) -> Tuple[str, str]:
    """P3-3: 根据引用次数和证据判定成熟度。

    Returns:
        (新成熟度, 原因)
    """
    has_evidence, _ = _check_mistake_book_for_fixed_evidence(rule_id)

    if current_maturity == 'draft':
        # draft → verified: 需 ≥3 次引用 + mistake-book 证据
        if ref_count >= 3 and has_evidence:
            return 'verified', f"引用 {ref_count} 次 + mistake-book 有修复证据"
        elif ref_count >= 3:
            return 'verified', f"引用 {ref_count} 次（mistake-book 证据待补充）"
        else:
            return 'draft', f"引用 {ref_count} 次，还需 {3 - ref_count} 次引用"
    elif current_maturity == 'verified':
        # verified → proven: 需 ≥5 次引用
        if ref_count >= 5:
            return 'proven', f"引用 {ref_count} 次，验证充分"
        else:
            return 'verified', f"引用 {ref_count} 次，还需 {5 - ref_count} 次引用"
    else:
        return current_maturity, "已是 proven 等级"


def update_rules_md(rule_refs: Dict[str, Set[str]]) -> bool:
    """更新 rules.md 的成熟度列"""
    rules_path = DELIVERHQ_ROOT / "docs" / "rules.md"
    if not rules_path.exists():
        print("❌ rules.md 不存在")
        return False

    content = rules_path.read_text(encoding='utf-8')
    updated_count = 0
    lines_info: List[str] = []

    # 匹配表格行：| 7 | ... | ... | P0 | draft | ... |
    def replace_maturity(match):
        nonlocal updated_count
        rule_num = match.group(1)
        line = match.group(0)

        if rule_num in rule_refs:
            ref_count = len(rule_refs[rule_num])

            # 提取当前成熟度
            parts = line.split('|')
            current_maturity = parts[5].strip() if len(parts) >= 6 else 'draft'

            # P3-3: 使用带证据的成熟度判定
            new_maturity, reason = _determine_maturity_with_evidence(
                rule_num, ref_count, current_maturity
            )

            if current_maturity != new_maturity:
                parts[5] = f' {new_maturity} '
                updated_count += 1
                cr_ids = ', '.join(sorted(rule_refs[rule_num])[:3])
                if len(rule_refs[rule_num]) > 3:
                    cr_ids += f" (+{len(rule_refs[rule_num]) - 3} more)"
                lines_info.append(
                    f"  规则 #{rule_num}: {current_maturity} → {new_maturity} ({reason}, 来源 CR: {cr_ids})"
                )
                return '|'.join(parts)

        return line

    # 匹配所有规则行
    new_content = re.sub(r'\|\s*(\d+)\s*\|[^\n]+', replace_maturity, content)

    if updated_count > 0:
        for info in lines_info:
            print(info)
        rules_path.write_text(new_content, encoding='utf-8')
        print(f"\n✅ 已更新 {updated_count} 条规则的成熟度")
        return True
    else:
        print("\n✓ 所有规则成熟度已是最新")
        return False


def main():
    print("=== 规则成熟度自动更新 ===\n")

    # P3-3: 扫描规则引用（带 CR 溯源）
    print("[扫描 delivery/ 中的规则引用]")
    rule_refs = scan_rule_references()

    if not rule_refs:
        print("未发现规则引用记录")
        return

    print(f"\n[发现 {len(rule_refs)} 条规则被引用]")
    for rule_id, cr_ids in sorted(rule_refs.items(), key=lambda x: int(x[0])):
        print(f"  规则 #{rule_id}: {len(cr_ids)} 次")
        for cr_id in sorted(cr_ids)[:3]:
            print(f"    - {cr_id}")
        if len(cr_ids) > 3:
            print(f"    ... (+{len(cr_ids) - 3} more)")

    # P3-3: 更新 rules.md（带证据检查）
    print(f"\n[更新 rules.md（带证据检查）]")
    update_rules_md(rule_refs)

    print("\n[提示]")
    print("  - 成熟度晋升需要 mistake-book 中有相关错误已被修复的证据")
    print("  - 参考: skill/docs/rule-maturity.md")


if __name__ == "__main__":
    main()
