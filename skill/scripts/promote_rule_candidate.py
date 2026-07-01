#!/usr/bin/env python3
"""
Promote rule candidates from docs/rules-candidates.md into docs/rules.md.
"""

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple


DELIVERHQ_ROOT = Path(__file__).parent.parent
sys.dont_write_bytecode = True


@dataclass
class CandidateEntry:
    title: str
    source_cr: str
    trigger: str
    proposed_rule: str
    scope: str
    promotion_recommendation: str
    promotion_status: Optional[str]
    promoted_to: Optional[str]
    promoted_on: Optional[str]
    block_text: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Promote rule candidates into docs/rules.md"
    )
    parser.add_argument("cr_id", help="CR ID whose candidate rules should be promoted")
    parser.add_argument("--gate", required=True, help="Canonical Gate value, e.g. P0/P1")
    parser.add_argument(
        "--detection",
        required=True,
        help="Canonical Detection value, e.g. manual/static",
    )
    return parser


def split_candidate_blocks(content: str) -> List[str]:
    if "## Active Candidates" in content:
        content = content.split("## Active Candidates", 1)[1]
    parts = re.split(r"(?=^## Candidate Rule: )", content, flags=re.MULTILINE)
    return [part.strip() for part in parts if part.strip().startswith("## Candidate Rule: ")]


def extract_field(block: str, label: str) -> Optional[str]:
    match = re.search(rf"^- {re.escape(label)}: (.+)$", block, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def parse_candidate_block(block: str) -> CandidateEntry:
    title_match = re.search(r"^## Candidate Rule: (.+)$", block, flags=re.MULTILINE)
    if not title_match:
        raise ValueError("Candidate block missing title header")

    entry = CandidateEntry(
        title=title_match.group(1).strip(),
        source_cr=extract_field(block, "Source CR") or "",
        trigger=extract_field(block, "Trigger") or "",
        proposed_rule=extract_field(block, "Proposed Rule") or "",
        scope=extract_field(block, "Scope") or "",
        promotion_recommendation=extract_field(block, "Promotion Recommendation") or "",
        promotion_status=extract_field(block, "Promotion Status"),
        promoted_to=extract_field(block, "Promoted To"),
        promoted_on=extract_field(block, "Promoted On"),
        block_text=block,
    )
    if not entry.source_cr or not entry.proposed_rule:
        raise ValueError(f"Candidate entry '{entry.title}' 缺少 Source CR 或 Proposed Rule")
    return entry


def load_candidate_entries(candidate_path: Path) -> Tuple[str, List[CandidateEntry]]:
    content = candidate_path.read_text(encoding="utf-8")
    entries = [parse_candidate_block(block) for block in split_candidate_blocks(content)]
    return content, entries


def select_unpromoted_entries(entries: List[CandidateEntry], cr_id: str) -> List[CandidateEntry]:
    matching = [entry for entry in entries if entry.source_cr == cr_id]
    if not matching:
        raise ValueError(f"未找到 Source CR 为 {cr_id} 的候选规则")

    unpromoted = [entry for entry in matching if entry.promotion_status != "promoted"]
    if not unpromoted:
        raise ValueError(f"{cr_id} 下的候选规则已全部晋升，无可晋升项")
    return unpromoted


def parse_rule_numbers(rules_text: str) -> List[int]:
    return [int(match) for match in re.findall(r"^\|\s*(\d+)\s*\|", rules_text, flags=re.MULTILINE)]


def build_rule_row(
    rule_number: int, entry: CandidateEntry, gate: str, detection: str, cr_id: str
) -> str:
    return (
        f"| {rule_number} | {entry.proposed_rule} | {gate} | draft | "
        f"{detection} | Promoted from {cr_id} |"
    )


def append_rule_rows(
    rules_path: Path,
    entries: List[CandidateEntry],
    gate: str,
    detection: str,
    cr_id: str,
) -> Tuple[str, List[Tuple[CandidateEntry, int]]]:
    rules_text = rules_path.read_text(encoding="utf-8")
    if "| # | Rule | Gate | Maturity | Detection | Source |" not in rules_text:
        raise ValueError("docs/rules.md 缺少规则表头，无法安全晋升")

    rule_numbers = parse_rule_numbers(rules_text)
    if not rule_numbers:
        raise ValueError("docs/rules.md 未发现可解析的规则编号")

    next_rule_number = max(rule_numbers) + 1
    new_rows = []
    promoted_refs = []
    for entry in entries:
        new_rows.append(build_rule_row(next_rule_number, entry, gate, detection, cr_id))
        promoted_refs.append((entry, next_rule_number))
        next_rule_number += 1

    updated_text = rules_text.rstrip() + "\n" + "\n".join(new_rows) + "\n"
    return updated_text, promoted_refs


def mark_promoted_candidates(
    original_text: str, promoted_refs: List[Tuple[CandidateEntry, int]]
) -> str:
    updated_text = original_text
    today = date.today().isoformat()
    for entry, rule_number in promoted_refs:
        # 防御：block_text 找不到（被前面的 replace 改动、或块本身缺失）时报错，
        # 避免静默跳过导致"标记晋升"没写进去却以为成功
        if entry.block_text not in updated_text:
            raise ValueError(
                f"无法标记晋升：在 rules-candidates.md 中找不到候选块 '{getattr(entry, 'title', entry.block_text[:40])}'"
            )
        replacement = entry.block_text.rstrip() + (
            f"\n- Promotion Status: promoted"
            f"\n- Promoted To: rules.md #{rule_number}"
            f"\n- Promoted On: {today}"
        )
        updated_text = updated_text.replace(entry.block_text, replacement, 1)
    return updated_text


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    candidate_path = DELIVERHQ_ROOT / "docs" / "rules-candidates.md"
    rules_path = DELIVERHQ_ROOT / "docs" / "rules.md"

    try:
        original_candidate_text, entries = load_candidate_entries(candidate_path)
        selected = select_unpromoted_entries(entries, args.cr_id)
        updated_rules_text, promoted_refs = append_rule_rows(
            rules_path, selected, args.gate, args.detection, args.cr_id
        )
        updated_candidate_text = mark_promoted_candidates(
            original_candidate_text, promoted_refs
        )
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    rules_path.write_text(updated_rules_text, encoding="utf-8")
    candidate_path.write_text(updated_candidate_text, encoding="utf-8")

    print(f"找到 {len(selected)} 条可晋升候选规则")
    print(f"已晋升 {len(promoted_refs)} 条规则到 docs/rules.md")
    for _, rule_number in promoted_refs:
        print(f"- rules.md #{rule_number}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
