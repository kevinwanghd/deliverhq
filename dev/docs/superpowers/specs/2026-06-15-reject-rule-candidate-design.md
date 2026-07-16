# DeliverHQ Reject Rule Candidate Design

## Goal

Introduce a minimal manual CLI that rejects candidate rules in `docs/rules-candidates.md` without deleting them.

This fills the last missing step in the current lightweight governance loop:

- write candidate rules
- list candidate rules
- promote approved rules
- reject rejected rules

## Scope

In scope:

- add a manual CLI `scripts/reject_rule_candidate.py`
- reject candidate rules by CR ID
- require an explicit rejection reason
- preserve rejected candidates in `docs/rules-candidates.md`
- append rejection metadata for auditability
- keep the implementation compatible with existing promotion and listing flows

Out of scope:

- moving rejected rules into `docs/rules-deprecated.md`
- restoring rejected rules
- rejecting by candidate title or file index
- automatic rejection by any Gate
- more advanced governance workflows

## Recommended Approach

Use a minimal explicit CLI:

```bash
python scripts/reject_rule_candidate.py CR-EXAMPLE --reason "与现有规则重复"
```

This is the recommended approach because it mirrors `promote_rule_candidate.py` and preserves the same governance model:

- humans make the decision
- the decision is explicit and auditable
- the candidate file remains the single working ledger for proposals

## Behavior

### Rejection Unit

Rejection happens **by CR ID**.

The script scans `docs/rules-candidates.md` for entries whose `Source CR` matches the requested CR and whose state is still actionable.

Actionable means:

- not already `promoted`
- not already `rejected`

If multiple actionable entries exist for the same CR, the script rejects all of them in one run.

### CLI Contract

Required arguments:

- positional `cr_id`
- required `--reason`

Example:

```bash
python scripts/reject_rule_candidate.py CR-EXAMPLE --reason "与现有规则重复"
```

Failure cases should exit non-zero:

- missing `--reason`
- no matching candidate entries for the CR
- all matching entries are already promoted or already rejected
- candidate file cannot be parsed safely

### Candidate Retention

Rejected candidates remain in `docs/rules-candidates.md`.

Each rejected entry gets rejection metadata appended beneath the existing fields:

```md
- Rejection Status: rejected
- Rejected Reason: 与现有规则重复
- Rejected On: YYYY-MM-DD
```

This keeps the candidate file auditable and prevents silent deletion of governance history.

## Status Model

After this feature, candidate rules can be in three states:

- `pending`
- `promoted`
- `rejected`

This design does not implement the `list_rule_candidates.py` update yet, but the new script should write metadata in a way that makes that extension straightforward.

## File-Level Changes

### New File

- `scripts/reject_rule_candidate.py`
  - parses CLI arguments
  - reads candidate entries from `docs/rules-candidates.md`
  - filters actionable entries by CR
  - appends rejection metadata back into candidate entries
  - returns non-zero for invalid or no-op rejection attempts

### Updated Files

- `docs/rules-candidates.md`
  - keeps existing structure
  - gains rejection metadata after a successful rejection

- `README.md`
  - documents the rejection command

- `AGENTS.md`
  - clarifies that rejected candidates remain auditable in the candidate file

## Data Shape

The existing candidate Markdown format remains unchanged.

Rejection appends these fields:

```md
- Rejection Status: rejected
- Rejected Reason: <reason text>
- Rejected On: YYYY-MM-DD
```

This design intentionally uses a separate rejection field instead of overloading `Promotion Status`, so promotion and rejection remain easy to distinguish during later parsing and display.

## Error Handling

The CLI should fail non-zero only for real governance or structural problems:

- `docs/rules-candidates.md` is missing
- candidate blocks cannot be parsed safely
- no matching candidate entries for the requested CR
- no actionable candidates remain for the requested CR

It should not silently skip work when the CR exists but all entries are already resolved.

## Testing Strategy

Minimum verification:

- success path:
  - run `python scripts/reject_rule_candidate.py <CR> --reason "<text>"`
  - confirm rejection metadata is appended

- repeat-run protection:
  - run the same command again
  - confirm it exits non-zero with a clear message

- missing reason:
  - omit `--reason`
  - confirm argparse exits non-zero

- missing CR:
  - use a non-existent CR
  - confirm non-zero exit and clear message

- regression safety:
  - run `python scripts/selftest.py`
  - confirm the framework remains healthy

## Risks

- candidate parsing can drift if the Markdown format changes later
- rejected metadata may complicate later status listing if the parser is not updated carefully

## Risk Mitigation

- keep the parser aligned with the existing candidate-entry structure
- make the rejection metadata explicit and separate from promotion metadata
- fail closed when parsing is ambiguous

## Implementation Sequence

1. Add `scripts/reject_rule_candidate.py`
2. Parse candidate entries by CR
3. Skip already promoted and already rejected entries
4. Append rejection metadata to actionable entries
5. Update `README.md` and `AGENTS.md`
6. Run targeted rejection commands and `selftest.py`
