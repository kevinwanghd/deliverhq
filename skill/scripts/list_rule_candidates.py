#!/usr/bin/env python3
"""
List rule candidates from docs/rules-candidates.md.
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


DELIVERHQ_ROOT = Path(__file__).parent.parent
sys.dont_write_bytecode = True


@dataclass
class CandidateSummary:
    title: str
    source_cr: str
    promotion_recommendation: str
    promotion_status: Optional[str]
    rejection_status: Optional[str]
    promoted_to: Optional[str]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List rule candidates for governance review"
    )
    parser.add_argument(
        "--status",
        choices=["pending", "promoted", "rejected"],
        help="Filter by candidate governance status",
    )
    parser.add_argument("--cr", help="Filter by Source CR")
    return parser


def split_candidate_blocks(content: str) -> List[str]:
    if "## Active Candidates" in content:
        content = content.split("## Active Candidates", 1)[1]
    parts = re.split(r"(?=^## Candidate Rule: )", content, flags=re.MULTILINE)
    return [part.strip() for part in parts if part.strip().startswith("## Candidate Rule: ")]


def extract_field(block: str, label: str) -> Optional[str]:
    match = re.search(rf"^- {re.escape(label)}: (.+)$", block, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def parse_candidate_block(block: str) -> CandidateSummary:
    title_match = re.search(r"^## Candidate Rule: (.+)$", block, flags=re.MULTILINE)
    if not title_match:
        raise ValueError("Candidate block missing title header")

    source_cr = extract_field(block, "Source CR")
    if not source_cr:
        raise ValueError(f"Candidate entry '{title_match.group(1).strip()}' 缺少 Source CR")

    return CandidateSummary(
        title=title_match.group(1).strip(),
        source_cr=source_cr,
        promotion_recommendation=extract_field(block, "Promotion Recommendation") or "",
        promotion_status=extract_field(block, "Promotion Status"),
        rejection_status=extract_field(block, "Rejection Status"),
        promoted_to=extract_field(block, "Promoted To"),
    )


def load_candidates(candidate_path: Path) -> List[CandidateSummary]:
    if not candidate_path.exists():
        raise ValueError("docs/rules-candidates.md 不存在")
    content = candidate_path.read_text(encoding="utf-8")
    return [parse_candidate_block(block) for block in split_candidate_blocks(content)]


def derive_status(candidate: CandidateSummary) -> str:
    if candidate.promotion_status == "promoted":
        return "promoted"
    if candidate.rejection_status == "rejected":
        return "rejected"
    return "pending"


def apply_filters(
    candidates: List[CandidateSummary], status: Optional[str], cr_id: Optional[str]
) -> List[CandidateSummary]:
    filtered = candidates
    if status:
        filtered = [candidate for candidate in filtered if derive_status(candidate) == status]
    if cr_id:
        filtered = [candidate for candidate in filtered if candidate.source_cr == cr_id]
    return filtered


def group_candidates(candidates: List[CandidateSummary]) -> Dict[str, List[CandidateSummary]]:
    grouped = {"pending": [], "promoted": [], "rejected": []}
    for candidate in candidates:
        grouped[derive_status(candidate)].append(candidate)
    return grouped


def render_candidate_row(candidate: CandidateSummary) -> str:
    row = (
        f"- {candidate.title} | {candidate.source_cr} | "
        f"recommended={candidate.promotion_recommendation or 'unknown'}"
    )
    if derive_status(candidate) == "promoted" and candidate.promoted_to:
        row += f" | {candidate.promoted_to}"
    if derive_status(candidate) == "rejected":
        row += " | rejected"
    return row


def print_summary(grouped: Dict[str, List[CandidateSummary]]) -> None:
    print("Rule Candidates Summary")
    print(f"- pending: {len(grouped['pending'])}")
    print(f"- promoted: {len(grouped['promoted'])}")
    print(f"- rejected: {len(grouped['rejected'])}")
    print()
    for status in ("pending", "promoted", "rejected"):
        print(f"[{status}]")
        if grouped[status]:
            for candidate in grouped[status]:
                print(render_candidate_row(candidate))
        else:
            print("- none")
        print()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        candidates = load_candidates(DELIVERHQ_ROOT / "docs" / "rules-candidates.md")
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    filtered = apply_filters(candidates, args.status, args.cr)
    grouped = group_candidates(filtered)
    print_summary(grouped)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
