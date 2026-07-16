# Reject Rule Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manual CLI that rejects rule candidates by CR ID, preserves them in `docs/rules-candidates.md`, and records explicit rejection metadata.

**Architecture:** Implement a small read/write CLI that reuses the existing candidate-entry Markdown structure already used by `promote_rule_candidate.py` and `list_rule_candidates.py`. The script should only mutate actionable candidates, append rejection metadata, and fail closed when the CR is missing or already fully resolved. Documentation updates keep the rejection step visible without introducing any new automation or Gate behavior.

**Tech Stack:** Python 3, Markdown docs, existing DeliverHQ script conventions

---

## File Structure

- Create: `scripts/reject_rule_candidate.py`
  - Manual governance CLI for rejecting candidate rules by CR and appending rejection metadata.
- Modify: `docs/rules-candidates.md`
  - Keep the candidate ledger intact and append rejection metadata during verification.
- Modify: `README.md`
  - Document the rejection command and its position in the governance loop.
- Modify: `AGENTS.md`
  - Clarify that rejected candidates remain auditable in the candidate ledger.

### Task 1: Scaffold The Rejection CLI

**Files:**
- Create: `scripts/reject_rule_candidate.py`
- Test: `scripts/reject_rule_candidate.py`

- [ ] **Step 1: Create the CLI skeleton with required reason input**

Create `scripts/reject_rule_candidate.py` with this initial content:

```python
#!/usr/bin/env python3
"""
Reject rule candidates from docs/rules-candidates.md.
"""

import argparse
import sys
from pathlib import Path

DELIVERHQ_ROOT = Path(__file__).parent.parent
sys.dont_write_bytecode = True


def build_parser():
    parser = argparse.ArgumentParser(description="Reject rule candidates for governance review")
    parser.add_argument("cr_id", help="CR ID whose candidate rules should be rejected")
    parser.add_argument("--reason", required=True, help="Human rejection reason")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    print(args.cr_id, args.reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the happy-path command and verify placeholder output**

Run: `python scripts/reject_rule_candidate.py CR-EXAMPLE --reason "与现有规则重复"`
Expected: `CR-EXAMPLE 与现有规则重复`

- [ ] **Step 3: Run the command without `--reason` and verify argparse blocks it**

Run: `python scripts/reject_rule_candidate.py CR-EXAMPLE`
Expected: exit code `2` and usage text mentioning `--reason`

- [ ] **Step 4: Commit the CLI skeleton**

```bash
git add scripts/reject_rule_candidate.py
git commit -m "feat: scaffold rule candidate rejection cli"
```

### Task 2: Parse Candidate Entries And Select Actionable Targets

**Files:**
- Modify: `scripts/reject_rule_candidate.py`
- Test: `scripts/reject_rule_candidate.py`

- [ ] **Step 1: Add a candidate dataclass and parsing helpers aligned with the existing candidate format**

Replace the placeholder script body with this parsing layer:

```python
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class CandidateEntry:
    title: str
    source_cr: str
    promotion_status: Optional[str]
    rejection_status: Optional[str]
    block_text: str


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
```

- [ ] **Step 2: Add actionable-entry selection by CR**

Add these helpers below `load_candidate_entries()`:

```python
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
```

- [ ] **Step 3: Wire parsing and selection into `main()`**

Replace `main()` with:

```python
def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        _, entries = load_candidate_entries(DELIVERHQ_ROOT / "docs" / "rules-candidates.md")
        actionable = select_actionable_entries(entries, args.cr_id)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"找到 {len(actionable)} 条可拒绝候选规则")
    return 0
```

- [ ] **Step 4: Run the existing promoted example and verify it is not actionable**

Run: `python scripts/reject_rule_candidate.py CR-EXAMPLE --reason "测试"`
Expected: exit code `1` with `CR-EXAMPLE 下的候选规则已全部处理，无可拒绝项`

- [ ] **Step 5: Run a missing-CR command and verify it fails cleanly**

Run: `python scripts/reject_rule_candidate.py CR-MISSING --reason "测试"`
Expected: exit code `1` with `未找到 Source CR 为 CR-MISSING 的候选规则`

- [ ] **Step 6: Commit the parsing and selection layer**

```bash
git add scripts/reject_rule_candidate.py
git commit -m "feat: select actionable rule candidates for rejection"
```

### Task 3: Append Rejection Metadata To Candidate Entries

**Files:**
- Modify: `scripts/reject_rule_candidate.py`
- Modify: `docs/rules-candidates.md`
- Test: `scripts/reject_rule_candidate.py`

- [ ] **Step 1: Add a writeback helper that appends rejection metadata**

Append this helper below `select_actionable_entries()`:

```python
from datetime import date


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
```

- [ ] **Step 2: Update `main()` to write the rejected metadata back to the candidate file**

Replace `main()` with:

```python
def main():
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
```

- [ ] **Step 3: Add one temporary test candidate for a new CR so the success path can be exercised**

Append this block to `docs/rules-candidates.md` for verification:

```md
## Candidate Rule: 重复规则应被拒绝
- Source CR: CR-REJECT-EXAMPLE
- Trigger: 人工治理阶段发现该规则与现有规则重复
- Proposed Rule: 所有重复规则候选必须在治理阶段明确拒绝
- Scope: Rule governance
- Promotion Recommendation: no
```

- [ ] **Step 4: Run the rejection success path**

Run: `python scripts/reject_rule_candidate.py CR-REJECT-EXAMPLE --reason "与现有规则重复"`
Expected:
- CLI prints `已拒绝 1 条候选规则`
- the candidate block gains:

```md
- Rejection Status: rejected
- Rejected Reason: 与现有规则重复
- Rejected On: 2026-06-15
```

- [ ] **Step 5: Run the same command again to verify repeat-run protection**

Run: `python scripts/reject_rule_candidate.py CR-REJECT-EXAMPLE --reason "与现有规则重复"`
Expected: exit code `1` with `CR-REJECT-EXAMPLE 下的候选规则已全部处理，无可拒绝项`

- [ ] **Step 6: Commit the rejection writeback behavior**

```bash
git add scripts/reject_rule_candidate.py docs/rules-candidates.md
git commit -m "feat: mark rejected rule candidates"
```

### Task 4: Document The Rejection Flow

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Update `README.md` with the rejection command**

Add this section near the existing candidate rule governance commands:

```md
### Reject A Candidate Rule

人工审核认为候选规则不应进入 canonical 规则表时，可用下面的命令记录拒绝决定：

```bash
python scripts/reject_rule_candidate.py CR-REJECT-EXAMPLE --reason "与现有规则重复"
```

该命令会保留候选条目，并在 `docs/rules-candidates.md` 上追加拒绝原因和时间。
```

- [ ] **Step 2: Update `AGENTS.md` with the rejection governance rule**

Add this bullet in the rules governance guidance:

```md
- 人工审核否决候选规则时，使用 `python scripts/reject_rule_candidate.py <CR-ID> --reason "<原因>"` 在 `docs/rules-candidates.md` 记录 rejected 状态
```

- [ ] **Step 3: Commit the documentation updates**

```bash
git add README.md AGENTS.md
git commit -m "docs: document rule candidate rejection flow"
```

### Task 5: Final Regression Verification

**Files:**
- Modify: any touched file if verification uncovers a regression
- Test: `python scripts/reject_rule_candidate.py ...`
- Test: `python scripts/selftest.py`

- [ ] **Step 1: Run the full verification set**

Run:

```bash
python scripts/reject_rule_candidate.py CR-MISSING --reason "测试"
python scripts/reject_rule_candidate.py CR-EXAMPLE --reason "测试"
python scripts/reject_rule_candidate.py CR-REJECT-EXAMPLE --reason "与现有规则重复"
python scripts/selftest.py
```

Expected:
- first command fails with the missing-CR message
- second command fails because the existing example is already resolved
- third command fails on repeat-run protection once the rejection metadata already exists
- `selftest.py` remains fully passing

- [ ] **Step 2: Check for unintended file churn**

Run: `git status --short`
Expected: only `scripts/reject_rule_candidate.py`, `docs/rules-candidates.md`, `README.md`, and `AGENTS.md` are intentionally modified, plus any expected `__pycache__` cleanup if needed

- [ ] **Step 3: Prepare handoff notes**

Record this summary in the final handoff:

```text
- reject_rule_candidate.py adds explicit rejection to the governance loop
- rejected candidates remain in docs/rules-candidates.md
- rejection requires a human-provided reason
- no restore or archive flow was added in this round
```

## Self-Review

- Spec coverage: the plan covers the CLI, CR-based rejection, required reason, candidate retention, documentation updates, and regression verification from the approved spec.
- Placeholder scan: every task includes concrete file paths, commands, and code snippets; no TBD/TODO placeholders remain.
- Type consistency: `CandidateEntry`, `load_candidate_entries()`, `select_actionable_entries()`, and `mark_rejected_candidates()` are named consistently across all tasks.
