# List Rule Candidates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only CLI that lists rule candidates from `docs/rules-candidates.md` grouped by promotion status, with optional `--status` and `--cr` filters.

**Architecture:** Build a small reporting script that reuses the same Markdown candidate format already parsed by `promote_rule_candidate.py`. The script should stay read-only, derive `pending` versus `promoted` from existing metadata, apply lightweight filters, and print a governance-friendly summary. Only `README.md` needs documentation updates in this round.

**Tech Stack:** Python 3, Markdown docs, existing DeliverHQ script conventions

---

## File Structure

- Create: `scripts/list_rule_candidates.py`
  - Read-only CLI for parsing candidate entries, applying filters, and rendering grouped summary output.
- Modify: `README.md`
  - Document the listing command and examples for the supported filters.

### Task 1: Scaffold The Read-Only CLI

**Files:**
- Create: `scripts/list_rule_candidates.py`
- Test: `scripts/list_rule_candidates.py`

- [ ] **Step 1: Create the CLI skeleton with filter arguments**

Create `scripts/list_rule_candidates.py` with this initial content:

```python
#!/usr/bin/env python3
"""
List rule candidates from docs/rules-candidates.md.
"""

import argparse
import sys
from pathlib import Path

DELIVERHQ_ROOT = Path(__file__).parent.parent
sys.dont_write_bytecode = True


def build_parser():
    parser = argparse.ArgumentParser(description="List rule candidates for governance review")
    parser.add_argument("--status", choices=["pending", "promoted"], help="Filter by promotion status")
    parser.add_argument("--cr", help="Filter by Source CR")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    print(args.status or "all", args.cr or "all")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the default command and verify placeholder output**

Run: `python scripts/list_rule_candidates.py`
Expected: `all all`

- [ ] **Step 3: Run the filtered command and verify placeholder output**

Run: `python scripts/list_rule_candidates.py --status promoted --cr CR-EXAMPLE`
Expected: `promoted CR-EXAMPLE`

- [ ] **Step 4: Commit the CLI skeleton**

```bash
git add scripts/list_rule_candidates.py
git commit -m "feat: scaffold rule candidate listing cli"
```

### Task 2: Parse Candidate Entries Safely

**Files:**
- Modify: `scripts/list_rule_candidates.py`
- Test: `scripts/list_rule_candidates.py`

- [ ] **Step 1: Add a small dataclass and parsing helpers**

Replace the placeholder script body with this parsing layer:

```python
import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CandidateSummary:
    title: str
    source_cr: str
    promotion_recommendation: str
    promotion_status: Optional[str]
    promoted_to: Optional[str]


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
        promoted_to=extract_field(block, "Promoted To"),
    )


def load_candidates(candidate_path: Path) -> List[CandidateSummary]:
    if not candidate_path.exists():
        raise ValueError("docs/rules-candidates.md 不存在")
    content = candidate_path.read_text(encoding="utf-8")
    return [parse_candidate_block(block) for block in split_candidate_blocks(content)]
```

- [ ] **Step 2: Wire parsing into `main()` and print the number of parsed entries**

Temporarily replace `main()` with:

```python
def main():
    parser = build_parser()
    parser.parse_args()
    candidates = load_candidates(DELIVERHQ_ROOT / "docs" / "rules-candidates.md")
    print(f"loaded {len(candidates)} candidates")
    return 0
```

- [ ] **Step 3: Run the script and verify the candidate file parses**

Run: `python scripts/list_rule_candidates.py`
Expected: `loaded 1 candidates`

- [ ] **Step 4: Commit the parsing layer**

```bash
git add scripts/list_rule_candidates.py
git commit -m "feat: parse rule candidate entries"
```

### Task 3: Add Status Derivation And Filters

**Files:**
- Modify: `scripts/list_rule_candidates.py`
- Test: `scripts/list_rule_candidates.py`

- [ ] **Step 1: Add a derived status helper and filter function**

Append these helpers below `load_candidates()`:

```python
def derive_status(candidate: CandidateSummary) -> str:
    return "promoted" if candidate.promotion_status == "promoted" else "pending"


def apply_filters(candidates: List[CandidateSummary], status: Optional[str], cr_id: Optional[str]) -> List[CandidateSummary]:
    filtered = candidates
    if status:
        filtered = [candidate for candidate in filtered if derive_status(candidate) == status]
    if cr_id:
        filtered = [candidate for candidate in filtered if candidate.source_cr == cr_id]
    return filtered
```

- [ ] **Step 2: Update `main()` to apply filters and print filtered count**

Replace `main()` with:

```python
def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        candidates = load_candidates(DELIVERHQ_ROOT / "docs" / "rules-candidates.md")
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    filtered = apply_filters(candidates, args.status, args.cr)
    print(f"filtered {len(filtered)} candidates")
    return 0
```

- [ ] **Step 3: Run the promoted filter against the existing promoted example**

Run: `python scripts/list_rule_candidates.py --status promoted`
Expected: `filtered 1 candidates`

- [ ] **Step 4: Run the pending filter against the same file**

Run: `python scripts/list_rule_candidates.py --status pending`
Expected: `filtered 0 candidates`

- [ ] **Step 5: Run the CR filter**

Run: `python scripts/list_rule_candidates.py --cr CR-EXAMPLE`
Expected: `filtered 1 candidates`

- [ ] **Step 6: Commit status and filter support**

```bash
git add scripts/list_rule_candidates.py
git commit -m "feat: filter listed rule candidates"
```

### Task 4: Render The Governance Summary Output

**Files:**
- Modify: `scripts/list_rule_candidates.py`
- Test: `scripts/list_rule_candidates.py`

- [ ] **Step 1: Add grouping and row rendering helpers**

Append these functions below `apply_filters()`:

```python
def render_candidate_row(candidate: CandidateSummary) -> str:
    row = (
        f"- {candidate.title} | {candidate.source_cr} | "
        f"recommended={candidate.promotion_recommendation or 'unknown'}"
    )
    if derive_status(candidate) == "promoted" and candidate.promoted_to:
        row += f" | {candidate.promoted_to}"
    return row


def group_candidates(candidates: List[CandidateSummary]) -> dict[str, List[CandidateSummary]]:
    grouped = {"pending": [], "promoted": []}
    for candidate in candidates:
        grouped[derive_status(candidate)].append(candidate)
    return grouped


def print_summary(grouped: dict[str, List[CandidateSummary]]):
    print("Rule Candidates Summary")
    print(f"- pending: {len(grouped['pending'])}")
    print(f"- promoted: {len(grouped['promoted'])}")
    print()
    for status in ("pending", "promoted"):
        print(f"[{status}]")
        if grouped[status]:
            for candidate in grouped[status]:
                print(render_candidate_row(candidate))
        else:
            print("- none")
        print()
```

- [ ] **Step 2: Update `main()` to print the grouped summary**

Replace the last lines of `main()` with:

```python
    filtered = apply_filters(candidates, args.status, args.cr)
    grouped = group_candidates(filtered)
    print_summary(grouped)
    return 0
```

- [ ] **Step 3: Run the default command and verify grouped output**

Run: `python scripts/list_rule_candidates.py`
Expected output contains:

```text
Rule Candidates Summary
- pending: 0
- promoted: 1

[pending]
- none

[promoted]
- 规则沉淀必须先写候选区 | CR-EXAMPLE | recommended=yes | rules.md #7
```

- [ ] **Step 4: Run the empty-result filter and verify it stays stable**

Run: `python scripts/list_rule_candidates.py --status pending --cr CR-EXAMPLE`
Expected output contains:

```text
Rule Candidates Summary
- pending: 0
- promoted: 0
```

and exits with code `0`

- [ ] **Step 5: Commit the summary renderer**

```bash
git add scripts/list_rule_candidates.py
git commit -m "feat: render grouped rule candidate summary"
```

### Task 5: Document And Verify The Listing Flow

**Files:**
- Modify: `README.md`
- Test: `python scripts/selftest.py`

- [ ] **Step 1: Update `README.md` with listing examples**

Add this section near the existing promotion examples:

```md
### List Candidate Rules

查看候选规则治理状态：

```bash
python scripts/list_rule_candidates.py
python scripts/list_rule_candidates.py --status pending
python scripts/list_rule_candidates.py --cr CR-EXAMPLE
python scripts/list_rule_candidates.py --status promoted --cr CR-EXAMPLE
```

默认输出按 `pending / promoted` 分组，并显示每条候选的标题、来源 CR、推荐值和已晋升目标。
```

- [ ] **Step 2: Run the full verification set**

Run:

```bash
python scripts/list_rule_candidates.py
python scripts/list_rule_candidates.py --status promoted
python scripts/list_rule_candidates.py --status pending --cr CR-EXAMPLE
python scripts/selftest.py
```

Expected:
- all three listing commands exit `0`
- the summary output is stable
- `selftest.py` remains fully passing

- [ ] **Step 3: Check for unintended file churn**

Run: `git status --short`
Expected: only `scripts/list_rule_candidates.py` and `README.md` are intentionally modified, plus any expected `__pycache__` cleanup if needed

- [ ] **Step 4: Commit the documented listing workflow**

```bash
git add scripts/list_rule_candidates.py README.md
git commit -m "feat: add rule candidate listing cli"
```

## Self-Review

- Spec coverage: the plan covers the read-only CLI, status grouping, summary output, `--status` and `--cr` filters, documentation, and regression verification from the approved spec.
- Placeholder scan: every task includes exact file paths, commands, and code snippets; no TBD/TODO placeholders remain.
- Type consistency: `CandidateSummary`, `load_candidates()`, `derive_status()`, `apply_filters()`, `group_candidates()`, and `print_summary()` are used consistently across all tasks.
