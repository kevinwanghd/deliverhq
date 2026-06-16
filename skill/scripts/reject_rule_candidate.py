#!/usr/bin/env python3
"""
Reject rule candidates from docs/rules-candidates.md.
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
    promotion_status: Optional[str]
    rejection_status: Optional[str]
    block_text: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reject rule candidates for governance review"
    )
    parser.add_argument("cr_id", help="CR ID whose candidate rules should be rejected")
    parser.add_argument("--reason", required=True, help="Human rejection reason")
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
    source_cr = extract_field(block, "Source CR")
    if not source_cr:
        raise ValueError(f"Candidate entry '{title_match.group(1).strip()}' 缺少 Source CR")
    return CandidateEntry(
        title=title_match.group(1).strip(),
        source_cr=source_cr,
        promotion_status=extract_field(block, "Promotion Status"),
        rejection_status=extract_field(block, "Rejection Status"),
        block_text=block,
    )


def load_candidate_entries(candidate_path: Path) -> Tuple[str, List[CandidateEntry]]:
    if not candidate_path.exists():
        raise ValueError("docs/rules-candidates.md 不存在")
    content = candidate_path.read_text(encoding="utf-8")
    return content, [parse_candidate_block(block) for block in split_candidate_blocks(content)]


def is_actionable(entry: CandidateEntry) -> bool:
    return entry.promotion_status != "promoted" and entry.rejection_status != "rejected"


def select_actionable_entries(entries: List[CandidateEntry], cr_id: str) -> List[CandidateEntry]:
    matching = [entry for entry in entries if entry.source_cr == cr_id]
    if not matching:
        raise ValueError(f"未找到 Source CR 为 {cr_id} 的候选规则")
    actionable = [entry for entry in matching if is_actionable(entry)]
    if not actionable:
        raise ValueError(f"{cr_id} 下的候选规则已全部处理，无可拒绝项")
    return actionable


def mark_rejected_candidates(original_text: str, entries: List[CandidateEntry], reason: str) -> str:
    updated_text = original_text
    today = date.today().isoformat()
    for entry in entries:
        replacement = entry.block_text.rstrip() + (
            f"\n- Rejection Status: rejected"
            f"\n- Rejected Reason: {reason}"
            f"\n- Rejected On: {today}"
        )
        updated_text = updated_text.replace(entry.block_text, replacement, 1)
    return updated_text


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    candidate_path = DELIVERHQ_ROOT / "docs" / "rules-candidates.md"
    try:
        original_text, entries = load_candidate_entries(candidate_path)
        actionable = select_actionable_entries(entries, args.cr_id)
        updated_text = mark_rejected_candidates(original_text, actionable, args.reason)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    candidate_path.write_text(updated_text, encoding="utf-8")
    print(f"已拒绝 {len(actionable)} 条候选规则")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
