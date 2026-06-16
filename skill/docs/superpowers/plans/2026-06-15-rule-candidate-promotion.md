# Rule Candidate Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manual CLI that promotes rule candidates from `docs/rules-candidates.md` into the canonical `docs/rules.md` table.

**Architecture:** The promotion flow stays explicit and human-driven. A new `scripts/promote_rule_candidate.py` script parses candidate entries by CR ID, appends canonical rule rows into the existing Markdown table, and writes promotion metadata back into the candidate file so repeated runs are safe. Documentation updates keep the governance flow discoverable without adding any new Gate or automatic promotion logic.

**Tech Stack:** Python 3, Markdown docs, existing DeliverHQ CLI/script conventions

---

## File Structure

- Create: `scripts/promote_rule_candidate.py`
  - Single-purpose CLI for parsing candidate entries, appending canonical rules, and marking promotion metadata.
- Modify: `docs/rules-candidates.md`
  - Keep the current candidate format, but add one promoted example entry during verification.
- Modify: `README.md`
  - Document the promotion command and where it sits in the governance flow.
- Modify: `AGENTS.md`
  - Clarify that human governance promotes candidate rules into `docs/rules.md`.

### Task 1: Build The Promotion CLI Skeleton

**Files:**
- Create: `scripts/promote_rule_candidate.py`
- Test: `scripts/promote_rule_candidate.py`

- [ ] **Step 1: Write the failing script skeleton**

Create `scripts/promote_rule_candidate.py` with only argument parsing and a placeholder `main()`:

```python
#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

DELIVERHQ_ROOT = Path(__file__).parent.parent


def build_parser():
    parser = argparse.ArgumentParser(description="Promote rule candidates into docs/rules.md")
    parser.add_argument("cr_id", help="CR ID whose candidate rules should be promoted")
    parser.add_argument("--gate", required=True, help="Canonical Gate value, e.g. P0/P1")
    parser.add_argument("--detection", required=True, help="Canonical Detection value, e.g. manual/static")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    print(args.cr_id, args.gate, args.detection)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the CLI with the happy-path command and verify the placeholder output**

Run: `python scripts/promote_rule_candidate.py CR-EXAMPLE --gate P1 --detection manual`
Expected: `CR-EXAMPLE P1 manual`

- [ ] **Step 3: Run the CLI without required flags and verify argparse fails**

Run: `python scripts/promote_rule_candidate.py CR-EXAMPLE`
Expected: exit code `2` and usage text mentioning `--gate` and `--detection`

- [ ] **Step 4: Commit the skeleton**

```bash
git add scripts/promote_rule_candidate.py
git commit -m "feat: scaffold rule candidate promotion cli"
```

### Task 2: Parse Candidate Entries By CR

**Files:**
- Modify: `scripts/promote_rule_candidate.py`
- Test: `scripts/promote_rule_candidate.py`

- [ ] **Step 1: Add a dataclass and parsing helpers for candidate entries**

Extend `scripts/promote_rule_candidate.py` with these definitions above `main()`:

```python
from dataclasses import dataclass
from datetime import date
import re


@dataclass
class CandidateEntry:
    title: str
    source_cr: str
    trigger: str
    proposed_rule: str
    scope: str
    promotion_recommendation: str
    promotion_status: str | None
    promoted_to: str | None
    promoted_on: str | None
    block_text: str


def split_candidate_blocks(content: str):
    parts = re.split(r"(?=^## Candidate Rule: )", content, flags=re.MULTILINE)
    return [part.strip() for part in parts if part.strip().startswith("## Candidate Rule: ")]


def extract_field(block: str, label: str):
    match = re.search(rf"^- {re.escape(label)}: (.+)$", block, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def parse_candidate_block(block: str):
    title_match = re.match(r"^## Candidate Rule: (.+)$", block)
    if not title_match:
        raise ValueError("Candidate block missing title header")
    return CandidateEntry(
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
```

- [ ] **Step 2: Add a loader that filters by CR and skips already-promoted entries**

Add these helpers below the parser functions:

```python
def load_candidate_entries(candidate_path: Path):
    content = candidate_path.read_text(encoding="utf-8")
    return content, [parse_candidate_block(block) for block in split_candidate_blocks(content)]


def select_unpromoted_entries(entries: list[CandidateEntry], cr_id: str):
    matching = [entry for entry in entries if entry.source_cr == cr_id]
    if not matching:
        raise ValueError(f"未找到 Source CR 为 {cr_id} 的候选规则")
    unpromoted = [entry for entry in matching if entry.promotion_status != "promoted"]
    if not unpromoted:
        raise ValueError(f"{cr_id} 下的候选规则已全部晋升，无可晋升项")
    return unpromoted
```

- [ ] **Step 3: Wire the loader into `main()` and fail closed before any file writes**

Replace the current `main()` body with:

```python
def main():
    parser = build_parser()
    args = parser.parse_args()

    candidate_path = DELIVERHQ_ROOT / "docs" / "rules-candidates.md"
    _, entries = load_candidate_entries(candidate_path)
    selected = select_unpromoted_entries(entries, args.cr_id)
    print(f"找到 {len(selected)} 条可晋升候选规则")
    return 0
```

- [ ] **Step 4: Run the happy-path command and verify it finds the CR-EXAMPLE candidate**

Run: `python scripts/promote_rule_candidate.py CR-EXAMPLE --gate P1 --detection manual`
Expected: `找到 1 条可晋升候选规则`

- [ ] **Step 5: Run the missing-CR command and verify the script fails before writing**

Run: `python scripts/promote_rule_candidate.py CR-MISSING --gate P1 --detection manual`
Expected: exit code `1` with `未找到 Source CR 为 CR-MISSING 的候选规则`

- [ ] **Step 6: Commit the parsing layer**

```bash
git add scripts/promote_rule_candidate.py
git commit -m "feat: parse rule candidates by cr"
```

### Task 3: Append Canonical Rules Into `docs/rules.md`

**Files:**
- Modify: `scripts/promote_rule_candidate.py`
- Test: `scripts/promote_rule_candidate.py`
- Test: `docs/rules.md`

- [ ] **Step 1: Add helpers that find the rules table and next rule number**

Append these helpers to `scripts/promote_rule_candidate.py`:

```python
def parse_rule_numbers(rules_text: str):
    return [int(match) for match in re.findall(r"^\|\s*(\d+)\s*\|", rules_text, flags=re.MULTILINE)]


def build_rule_row(rule_number: int, entry: CandidateEntry, gate: str, detection: str, cr_id: str):
    return f"| {rule_number} | {entry.proposed_rule} | {gate} | draft | {detection} | Promoted from {cr_id} |"


def append_rule_rows(rules_path: Path, entries: list[CandidateEntry], gate: str, detection: str, cr_id: str):
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
    rules_path.write_text(updated_text, encoding="utf-8")
    return promoted_refs
```

- [ ] **Step 2: Call the row appender from `main()`**

Update `main()` so it performs a real write after selection:

```python
def main():
    parser = build_parser()
    args = parser.parse_args()

    candidate_path = DELIVERHQ_ROOT / "docs" / "rules-candidates.md"
    rules_path = DELIVERHQ_ROOT / "docs" / "rules.md"

    _, entries = load_candidate_entries(candidate_path)
    selected = select_unpromoted_entries(entries, args.cr_id)
    promoted_refs = append_rule_rows(rules_path, selected, args.gate, args.detection, args.cr_id)
    print(f"已晋升 {len(promoted_refs)} 条规则到 docs/rules.md")
    return 0
```

- [ ] **Step 3: Run the happy-path command and verify a new canonical rule row appears**

Run: `python scripts/promote_rule_candidate.py CR-EXAMPLE --gate P1 --detection manual`
Expected:
- CLI prints `已晋升 1 条规则到 docs/rules.md`
- `docs/rules.md` gains a new line like:

```md
| 7 | 所有 AI 生成的新规则或规则修改建议必须先写入 `docs/rules-candidates.md`，不得直接写入 `docs/rules.md` | P1 | draft | manual | Promoted from CR-EXAMPLE |
```

- [ ] **Step 4: Run `update_rule_maturity.py` to confirm the new row does not break its parser**

Run: `python scripts/update_rule_maturity.py`
Expected: script completes successfully, even if it reports `未发现规则引用记录`

- [ ] **Step 5: Commit the canonical insertion logic**

```bash
git add scripts/promote_rule_candidate.py docs/rules.md
git commit -m "feat: append promoted rules to canonical table"
```

### Task 4: Mark Candidate Entries As Promoted

**Files:**
- Modify: `scripts/promote_rule_candidate.py`
- Modify: `docs/rules-candidates.md`
- Test: `scripts/promote_rule_candidate.py`

- [ ] **Step 1: Add a helper that appends promotion metadata to candidate blocks**

Add this function below `append_rule_rows()`:

```python
def mark_promoted_candidates(candidate_path: Path, original_text: str, promoted_refs: list[tuple[CandidateEntry, int]]):
    updated_text = original_text
    today = date.today().isoformat()
    for entry, rule_number in promoted_refs:
        replacement = entry.block_text.rstrip() + (
            f"\n- Promotion Status: promoted"
            f"\n- Promoted To: rules.md #{rule_number}"
            f"\n- Promoted On: {today}"
        )
        updated_text = updated_text.replace(entry.block_text, replacement, 1)
    candidate_path.write_text(updated_text, encoding="utf-8")
```

- [ ] **Step 2: Capture the original candidate file text and call the marker after canonical append**

Update `main()` to:

```python
def main():
    parser = build_parser()
    args = parser.parse_args()

    candidate_path = DELIVERHQ_ROOT / "docs" / "rules-candidates.md"
    rules_path = DELIVERHQ_ROOT / "docs" / "rules.md"

    original_text, entries = load_candidate_entries(candidate_path)
    selected = select_unpromoted_entries(entries, args.cr_id)
    promoted_refs = append_rule_rows(rules_path, selected, args.gate, args.detection, args.cr_id)
    mark_promoted_candidates(candidate_path, original_text, promoted_refs)
    print(f"已晋升 {len(promoted_refs)} 条规则到 docs/rules.md")
    return 0
```

- [ ] **Step 3: Run the same command again and verify repeat-run protection now triggers**

Run: `python scripts/promote_rule_candidate.py CR-EXAMPLE --gate P1 --detection manual`
Expected: exit code `1` with `CR-EXAMPLE 下的候选规则已全部晋升，无可晋升项`

- [ ] **Step 4: Inspect `docs/rules-candidates.md` and confirm the entry now has promotion metadata**

Expected candidate block suffix:

```md
- Promotion Status: promoted
- Promoted To: rules.md #7
- Promoted On: 2026-06-15
```

- [ ] **Step 5: Commit the promotion metadata behavior**

```bash
git add scripts/promote_rule_candidate.py docs/rules-candidates.md
git commit -m "feat: mark promoted rule candidates"
```

### Task 5: Document And Verify The Promotion Flow

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Test: `python scripts/selftest.py`

- [ ] **Step 1: Update `README.md` with the promotion command**

Add this example near the existing rules-candidate explanation:

```md
### Promote A Candidate Rule

After a human approves a candidate rule, promote it into the canonical rules table with:

```bash
python scripts/promote_rule_candidate.py CR-EXAMPLE --gate P1 --detection manual
```

The command appends a new `docs/rules.md` row and marks the source entry in `docs/rules-candidates.md` as promoted.
```

- [ ] **Step 2: Update `AGENTS.md` to describe the human-governed promotion step**

Add one bullet in the writeback/governance guidance:

```md
- 人工审核通过后，使用 `python scripts/promote_rule_candidate.py <CR-ID> --gate <P0|P1> --detection <mode>` 将候选规则晋升到 `docs/rules.md`
```

- [ ] **Step 3: Run the full verification set**

Run:

```bash
python scripts/promote_rule_candidate.py CR-MISSING --gate P1 --detection manual
python scripts/update_rule_maturity.py
python scripts/selftest.py
```

Expected:
- first command fails with a clear missing-CR message
- second command completes without parsing errors
- third command reports all checks passing

- [ ] **Step 4: Check for unintended file churn**

Run: `git status --short`
Expected: only `scripts/promote_rule_candidate.py`, `docs/rules.md`, `docs/rules-candidates.md`, `README.md`, and `AGENTS.md` are intentionally modified

- [ ] **Step 5: Commit the final documented workflow**

```bash
git add scripts/promote_rule_candidate.py docs/rules.md docs/rules-candidates.md README.md AGENTS.md
git commit -m "feat: add manual rule candidate promotion flow"
```

## Self-Review

- Spec coverage: the plan covers the CLI contract, CR-based selection, canonical insertion, candidate retention, doc updates, and regression verification from the approved spec.
- Placeholder scan: all steps include concrete file paths, commands, and code snippets; no TBD/TODO placeholders remain.
- Type consistency: `CandidateEntry`, `load_candidate_entries()`, `select_unpromoted_entries()`, `append_rule_rows()`, and `mark_promoted_candidates()` keep consistent names and data flow across all tasks.
