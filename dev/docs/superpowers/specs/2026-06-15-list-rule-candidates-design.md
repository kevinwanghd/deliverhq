# DeliverHQ List Rule Candidates Design

## Goal

Introduce a small read-only CLI that lists entries in `docs/rules-candidates.md` for human governance.

The purpose is operational visibility, not governance automation. The script should help humans quickly answer:

- which candidate rules are still pending
- which candidate rules have already been promoted
- which candidates belong to a specific CR

## Scope

In scope:

- add a read-only CLI `scripts/list_rule_candidates.py`
- parse candidate rule entries from `docs/rules-candidates.md`
- group output by promotion status
- provide summary-style output rather than full document dumps
- support minimal filters: `--status` and `--cr`

Out of scope:

- editing candidate entries
- promoting rules
- deleting or archiving candidates
- adding verbose/full-field output
- adding dashboard/UI output
- integrating with any Gate

## Recommended Approach

Use a minimal governance-oriented CLI:

```bash
python scripts/list_rule_candidates.py
python scripts/list_rule_candidates.py --status pending
python scripts/list_rule_candidates.py --cr CR-EXAMPLE
python scripts/list_rule_candidates.py --status promoted --cr CR-EXAMPLE
```

This approach is recommended because it complements the existing promotion flow without adding new governance complexity:

- `writeback` writes into `docs/rules-candidates.md`
- `promote_rule_candidate.py` promotes approved entries into `docs/rules.md`
- `list_rule_candidates.py` provides the human-readable overview in between

## Behavior

### Status Model

Candidate entries are grouped into two statuses:

- `pending`: candidate has no `Promotion Status: promoted`
- `promoted`: candidate contains `Promotion Status: promoted`

No other statuses are introduced in this round.

### Default Output

The default output is a summary view grouped by status.

Expected shape:

```text
Rule Candidates Summary
- pending: 3
- promoted: 1

[pending]
- 规则标题A | CR-123 | recommended=yes
- 规则标题B | CR-456 | recommended=no

[promoted]
- 规则沉淀必须先写候选区 | CR-EXAMPLE | recommended=yes | rules.md #7
```

Each summary row includes:

- candidate title
- `Source CR`
- `Promotion Recommendation`
- `Promoted To` when the candidate is already promoted

### Filters

Supported filters:

- `--status pending|promoted`
- `--cr <CR-ID>`

Filters can be combined. Filtering narrows the displayed candidates before grouping and counts are printed.

If no results match, the script should still exit successfully and print an empty summary instead of failing.

## File-Level Changes

### New File

- `scripts/list_rule_candidates.py`
  - reads `docs/rules-candidates.md`
  - parses candidate entries
  - assigns each entry a derived status
  - applies optional filters
  - prints summary counts and grouped candidate summaries

### Updated Files

- `README.md`
  - document the listing command and filter examples

`AGENTS.md` does not need to change in this round unless implementation reveals a clear gap.

## Data Shape

The script reuses the existing Markdown candidate format. No format changes are required.

Expected parsed fields:

- candidate title
- `Source CR`
- `Promotion Recommendation`
- `Promotion Status` (optional)
- `Promoted To` (optional)

The script should not require `Trigger`, `Scope`, or `Proposed Rule` for rendering the summary view.

## Error Handling

The CLI should fail non-zero only for real structural problems:

- `docs/rules-candidates.md` is missing
- candidate blocks cannot be parsed safely

It should not fail just because filters return no matches.

## Testing Strategy

Minimum verification:

- default command prints grouped summary
- `--status pending` only shows pending candidates
- `--status promoted` only shows promoted candidates
- `--cr CR-EXAMPLE` only shows entries for that CR
- combined filters work together
- empty-result filters print a stable summary instead of throwing errors
- `python scripts/selftest.py` still passes after adding the new script

## Risks

- candidate parsing can drift if Markdown structure changes later
- summary output can become inconsistent if promoted metadata is partially written

## Risk Mitigation

- keep parsing logic narrow and aligned with the candidate format already used by `promote_rule_candidate.py`
- treat missing optional promotion fields as display omissions, not hard failures
- fail closed only when the file is missing or title/CR parsing is impossible

## Implementation Sequence

1. Add `scripts/list_rule_candidates.py`
2. Parse candidate entries from `docs/rules-candidates.md`
3. Derive `pending` vs `promoted` status
4. Add `--status` and `--cr` filters
5. Print summary counts and grouped entries
6. Update `README.md`
7. Run targeted commands and `selftest.py`
