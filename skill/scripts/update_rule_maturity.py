#!/usr/bin/env python3
"""
规则成熟度自动更新
扫描 delivery/ 下所有 CR 的 quality-report.md，统计规则引用次数，自动更新 rules.md 成熟度
"""

import sys
from pathlib import Path
import re

# 定位 DeliverHQ 根目录（脚本在 DeliverHQ/scripts/ 下）
DELIVERHQ_ROOT = Path(__file__).parent.parent

def scan_rule_references():
    """扫描所有已交付 CR 中的规则引用"""
    delivery_dir = DELIVERHQ_ROOT / "delivery"
    if not delivery_dir.exists():
        print("⚠️ delivery/ 目录不存在，跳过扫描")
        return {}

    rule_refs = {}  # {rule_id: count}

    for quality_report in delivery_dir.rglob("quality-report.md"):
        try:
            content = quality_report.read_text(encoding='utf-8')
            # 匹配 "rules.md #X" 或 "规则 #X"
            matches = re.findall(r'rules\.md\s*#(\d+)|规则\s*#(\d+)', content)
            for match in matches:
                rule_id = match[0] or match[1]
                rule_refs[rule_id] = rule_refs.get(rule_id, 0) + 1
        except Exception as e:
            print(f"⚠️ 跳过 {quality_report}: {e}")

    return rule_refs

def determine_maturity(count):
    """根据引用次数判定成熟度"""
    if count >= 5:
        return 'proven'
    elif count >= 3:
        return 'verified'
    else:
        return 'draft'

def update_rules_md(rule_refs):
    """更新 rules.md 的成熟度列"""
    rules_path = DELIVERHQ_ROOT / "docs" / "rules.md"
    if not rules_path.exists():
        print("❌ rules.md 不存在")
        return False

    content = rules_path.read_text(encoding='utf-8')
    updated_count = 0

    # 匹配表格行：| 7 | ... | ... | P0 | draft | ... |
    def replace_maturity(match):
        nonlocal updated_count
        rule_num = match.group(1)
        line = match.group(0)

        if rule_num in rule_refs:
            ref_count = rule_refs[rule_num]
            new_maturity = determine_maturity(ref_count)

            # 替换成熟度列（第 5 列）
            parts = line.split('|')
            if len(parts) >= 6:
                old_maturity = parts[5].strip()
                if old_maturity != new_maturity:
                    parts[5] = f' {new_maturity} '
                    updated_count += 1
                    print(f"  规则 #{rule_num}: {old_maturity} → {new_maturity} (引用 {ref_count} 次)")
                return '|'.join(parts)

        return line

    # 匹配所有规则行
    new_content = re.sub(r'\|\s*(\d+)\s*\|[^\n]+', replace_maturity, content)

    if updated_count > 0:
        rules_path.write_text(new_content, encoding='utf-8')
        print(f"\n✅ 已更新 {updated_count} 条规则的成熟度")
        return True
    else:
        print("\n✓ 所有规则成熟度已是最新")
        return False

def main():
    print("=== 规则成熟度自动更新 ===\n")

    # 扫描规则引用
    print("[扫描 delivery/ 中的规则引用]")
    rule_refs = scan_rule_references()

    if not rule_refs:
        print("未发现规则引用记录")
        return

    print(f"\n[发现 {len(rule_refs)} 条规则被引用]")
    for rule_id, count in sorted(rule_refs.items(), key=lambda x: int(x[0])):
        maturity = determine_maturity(count)
        print(f"  规则 #{rule_id}: {count} 次 → {maturity}")

    # 更新 rules.md
    print(f"\n[更新 rules.md]")
    update_rules_md(rule_refs)

if __name__ == "__main__":
    main()
