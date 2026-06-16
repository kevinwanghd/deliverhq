#!/usr/bin/env python3
"""
自动更新错误案例库。

同一 CR + Gate + failure hash 不重复追加；重复出现时更新 count / last_seen。
当同类失败出现 3 次以上，生成 rules.md candidate 标记，供人工转规则。
"""


import hashlib
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


def _fingerprint(cr_id: str, gate_type: str, failure_reason: str) -> str:
    normalized = re.sub(r"\s+", " ", failure_reason.strip().lower())
    return hashlib.sha256(f"{cr_id}|{gate_type}|{normalized}".encode("utf-8")).hexdigest()[:12]


def _entry_block(
    cr_id: str,
    gate_type: str,
    failure_reason: str,
    root_cause: Optional[str],
    improvement: Optional[str],
    fp: str,
    today: str,
) -> str:
    entry = f"""
### 错误：{cr_id} - {gate_type} 失败
- **日期**：{today}
- **last_seen**：{today}
- **CR-ID**：{cr_id}
- **失败门禁**：{gate_type}
- **failure_hash**：{fp}
- **count**：1
- **converted_to_rule**：false
- **rules_candidate**：false
- **问题描述**：{failure_reason}
"""
    if root_cause:
        entry += f"- **根本原因**：{root_cause}\n"
    if improvement:
        entry += f"- **改进措施**：{improvement}\n"
    return entry


def _update_existing(content: str, fp: str, today: str) -> Tuple[str, bool, int]:
    marker = f"**failure_hash**：{fp}"
    index = content.find(marker)
    if index == -1:
        return content, False, 0

    start = content.rfind("\n### ", 0, index)
    if start == -1:
        start = 0
    else:
        start += 1
    end = content.find("\n### ", index)
    if end == -1:
        end = len(content)

    block = content[start:end]
    count_match = re.search(r"\*\*count\*\*：\s*(\d+)", block)
    count = int(count_match.group(1)) if count_match else 1
    new_count = count + 1

    if count_match:
        block = re.sub(r"\*\*count\*\*：\s*\d+", f"**count**：{new_count}", block, count=1)
    else:
        block = block.replace(marker, f"{marker}\n- **count**：{new_count}", 1)

    if "**last_seen**：" in block:
        block = re.sub(r"\*\*last_seen\*\*：.*", f"**last_seen**：{today}", block, count=1)
    else:
        block = block.replace("- **日期**：", f"- **last_seen**：{today}\n- **日期**：", 1)

    if new_count >= 3 and "**rules_candidate**：true" not in block:
        if "**rules_candidate**：false" in block:
            block = block.replace("**rules_candidate**：false", "**rules_candidate**：true", 1)
        else:
            block = block.replace(marker, f"{marker}\n- **rules_candidate**：true", 1)

    return content[:start] + block + content[end:], True, new_count


def update_mistake_book(cr_id: str, gate_type: str, failure_reason: str, root_cause: str = None, improvement: str = None):
    script_dir = Path(__file__).parent
    mistake_book_path = script_dir.parent / "docs" / "mistake-book.md"

    if not mistake_book_path.exists():
        print(f"❌ 错误：找不到 {mistake_book_path}")
        return False

    today = datetime.now().strftime("%Y-%m-%d")
    fp = _fingerprint(cr_id, gate_type, failure_reason)
    content = mistake_book_path.read_text(encoding="utf-8")
    updated, existed, count = _update_existing(content, fp, today)

    if existed:
        mistake_book_path.write_text(updated, encoding="utf-8")
        print(f"✅ 已更新重复错误 {fp}：count={count}, last_seen={today}")
        if count >= 3:
            print("ℹ️  该失败已重复 3 次以上，已标记 rules_candidate=true")
        return True

    entry = _entry_block(cr_id, gate_type, failure_reason, root_cause, improvement, fp, today)
    with open(mistake_book_path, 'a', encoding='utf-8') as f:
        f.write(entry)

    print(f"✅ 已将 {cr_id} 的 {gate_type} 失败记录追加到 mistake-book.md（failure_hash={fp}）")
    return True


def parse_gate_report(report_path: str):
    report_file = Path(report_path)

    if not report_file.exists():
        print(f"❌ 错误：找不到报告文件 {report_path}")
        return None

    cr_id = report_file.parent.name
    gate_type = report_file.stem.replace('-report', '').replace('gate', 'Gate').title()
    if not gate_type.endswith('Gate'):
        gate_type += 'Gate'

    content = report_file.read_text(encoding='utf-8')

    if 'BLOCKED' not in content and 'FAILED' not in content:
        print(f"ℹ️  {report_file.name} 状态不是 BLOCKED/FAILED，无需记录错误")
        return None

    failure_reason = "详见报告文件"
    if "## 检查结果" in content:
        start = content.find("## 检查结果")
        end = content.find("##", start + 10)
        if end == -1:
            end = len(content)
        failure_reason = content[start:end].strip()

    return {
        'cr_id': cr_id,
        'gate_type': gate_type,
        'failure_reason': failure_reason[:200] + "..."
    }


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python update_mistake_book.py <CR-ID> <gate_type> <failure_reason> [root_cause] [improvement]")
        print("  python update_mistake_book.py --from-report <report_file_path>")
        sys.exit(1)

    if sys.argv[1] == '--from-report':
        if len(sys.argv) < 3:
            print("❌ 错误：缺少报告文件路径")
            sys.exit(1)
        info = parse_gate_report(sys.argv[2])
        if not info:
            sys.exit(0)
        success = update_mistake_book(
            cr_id=info['cr_id'],
            gate_type=info['gate_type'],
            failure_reason=info['failure_reason']
        )
        sys.exit(0 if success else 1)

    if len(sys.argv) < 4:
        print("❌ 错误：缺少 gate_type 或 failure_reason")
        sys.exit(1)

    cr_id = sys.argv[1]
    gate_type = sys.argv[2]
    failure_reason = sys.argv[3]
    root_cause = sys.argv[4] if len(sys.argv) > 4 else None
    improvement = sys.argv[5] if len(sys.argv) > 5 else None

    success = update_mistake_book(cr_id, gate_type, failure_reason, root_cause, improvement)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
