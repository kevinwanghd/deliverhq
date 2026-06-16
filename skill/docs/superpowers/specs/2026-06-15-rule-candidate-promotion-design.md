# DeliverHQ Rule Candidate Promotion Design

## Goal

Introduce a minimal manual promotion CLI that moves rule proposals from `docs/rules-candidates.md` into the canonical `docs/rules.md` table.

This design preserves the governance boundary established in the previous round:

- AI writes rule proposals into `docs/rules-candidates.md`
- Humans explicitly promote approved proposals into `docs/rules.md`
- Matured canonical rules continue to use the existing `update_rule_maturity.py` flow

## Scope

In scope:

- Add a manual CLI for promoting candidate rules by CR
- Append promoted rules into the existing `docs/rules.md` table
- Mark promoted entries in `docs/rules-candidates.md` without deleting them
- Require explicit `--gate` and `--detection` inputs during promotion
- Update documentation so the promotion step is visible and repeatable

Out of scope:

- Automatic approval or automatic promotion
- Promotion by candidate title or by file index
- Automatic duplicate detection or rule merging
- Automatic writeback into `docs/rules-deprecated.md`
- Promotion flows for `decisions.md` or `mistake-book.md`
- Automatic invocation from any Gate

## Recommended Approach

Use a minimal, explicit CLI:

```bash
python scripts/promote_rule_candidate.py CR-EXAMPLE --gate P1 --detection manual
```

This approach is preferred because it matches the current governance model:

- the promotion action is intentional
- governance metadata is supplied by a human rather than guessed
- the implementation stays small and compatible with the existing rules table and maturity updater

## Behavior

### Promotion Unit

Promotion happens **by CR ID**.

The script scans `docs/rules-candidates.md` for entries whose `Source CR` matches the requested CR and whose promotion status is not already marked as promoted.

If multiple unpromoted entries exist for the same CR, the script promotes all of them in one run.

### CLI Contract

Required arguments:

- positional `cr_id`
- `--gate`
- `--detection`

Example:

```bash
python scripts/promote_rule_candidate.py CR-EXAMPLE --gate P1 --detection manual
```

Failure cases should exit non-zero:

- missing required arguments
- no matching candidate entries for the CR
- all matching entries already promoted
- `docs/rules.md` table cannot be parsed safely

### Canonical Rule Insertion

Each promoted candidate becomes a new row appended to the existing rules table in `docs/rules.md`.

Field mapping:

- `Rule`: value from `Proposed Rule`
- `Gate`: value from `--gate`
- `Maturity`: always `draft`
- `Detection`: value from `--detection`
- `Source`: `Promoted from <CR ID>`

Rule numbering uses the current maximum rule number in `docs/rules.md` plus one.

### Candidate Retention

Promoted candidates remain in `docs/rules-candidates.md`.

Each promoted entry gets writeback metadata appended beneath the existing fields:

```md
- Promotion Status: promoted
- Promoted To: rules.md #N
- Promoted On: YYYY-MM-DD
```

This keeps the candidate file auditable and makes the CLI idempotent.

## File-Level Changes

### New File

- `scripts/promote_rule_candidate.py`
  - parses CLI arguments
  - reads candidate entries from `docs/rules-candidates.md`
  - appends new rows to `docs/rules.md`
  - writes promotion metadata back into candidate entries
  - returns non-zero for unsafe or no-op promotion attempts

### Updated Files

- `docs/rules-candidates.md`
  - keeps existing candidate structure
  - gains promotion metadata after successful promotion

- `README.md`
  - documents the promotion step and CLI example

- `AGENTS.md`
  - clarifies that human governance promotes candidates into canonical rules

## Data Shape

Candidate entries remain Markdown. No YAML or JSON migration is required.

Expected shape before promotion:

```md
## Candidate Rule: <short title>
- Source CR: CR-XXX
- Trigger: <what failure, review finding, or repeated issue caused this>
- Proposed Rule: <rule text>
- Scope: <where this applies>
- Promotion Recommendation: yes/no
```

Expected shape after promotion:

```md
## Candidate Rule: <short title>
- Source CR: CR-XXX
- Trigger: <what failure, review finding, or repeated issue caused this>
- Proposed Rule: <rule text>
- Scope: <where this applies>
- Promotion Recommendation: yes/no
- Promotion Status: promoted
- Promoted To: rules.md #N
- Promoted On: YYYY-MM-DD
```

The `Promotion Recommendation` field remains advisory in this round. The CLI does not block promotion when that field says `no`, because human governance is the authoritative decision maker.

## Compatibility

The canonical rules file already uses a table shape compatible with the existing maturity updater:

```md
| # | Rule | Gate | Maturity | Detection | Source |
```

By appending promoted rules directly into this table and setting `Maturity = draft`, the new script stays compatible with `scripts/update_rule_maturity.py` without changing that script.

## Testing Strategy

Minimum verification:

- Success path:
  - run `python scripts/promote_rule_candidate.py CR-EXAMPLE --gate P1 --detection manual`
  - confirm one new row is appended to `docs/rules.md`
  - confirm candidate entry is marked as promoted

- Repeat-run protection:
  - run the same command again
  - confirm no duplicate rule is appended
  - confirm the script exits non-zero with a clear message

- Argument validation:
  - omit `--gate` or `--detection`
  - confirm non-zero exit and usage output

- Missing CR:
  - use a non-existent CR ID
  - confirm non-zero exit and clear error message

- Structural safety:
  - if the rules table cannot be parsed, the script must fail without writing partial changes

- Regression safety:
  - run `python scripts/update_rule_maturity.py`
  - run `python scripts/selftest.py`
  - confirm the promotion flow does not break existing checks

## Risks

- Candidate parsing may become fragile if Markdown entries drift from the expected shape
- Table insertion may break if `docs/rules.md` format changes later
- Human operators may forget required governance metadata and expect the script to guess it

## Risk Mitigation

- Keep the candidate entry format narrow and documented
- Make the CLI fail closed when parsing is ambiguous
- Require `--gate` and `--detection` instead of guessing
- Keep promoted entries in the candidate file for auditability and idempotency

## Implementation Sequence

1. Add `scripts/promote_rule_candidate.py`
2. Parse candidate entries by CR and skip already-promoted entries
3. Append canonical rule rows into `docs/rules.md`
4. Write promotion metadata back to candidate entries
5. Update `README.md` and `AGENTS.md`
6. Run targeted promotion tests and `selftest.py`
