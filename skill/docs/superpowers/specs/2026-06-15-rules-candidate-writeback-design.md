# DeliverHQ Rules Candidate Writeback Design

## Goal

Introduce a minimal candidate-zone mechanism for rules writeback so AI agents no longer write directly to the canonical `docs/rules.md`.

This design changes only the `rules` path. It does not introduce candidate zones for `decisions.md` or `mistake-book.md` in this round.

## Scope

In scope:

- Add `docs/rules-candidates.md`
- Add `docs/rules-deprecated.md`
- Keep `docs/rules.md` as the single canonical rules source
- Update writeback semantics so AI writes candidate rules instead of canonical rules
- Update `WritebackGate` to validate candidate writeback behavior
- Update key docs and permissions to reflect the new boundary

Out of scope:

- Automatic promotion from candidate rules into `docs/rules.md`
- Automatic deprecation workflow
- Candidate zones for `docs/decisions.md`
- Candidate zones for `docs/mistake-book.md`

## Recommended Approach

Use a minimal dual-track model:

- `docs/rules.md`: canonical, human-governed rules
- `docs/rules-candidates.md`: AI-written candidate rules proposed by the current CR
- `docs/rules-deprecated.md`: holding area for rules removed from canonical use

This keeps the write boundary clear without introducing a larger governance system too early.

## Behavior Changes

### Canonical vs Candidate

- `docs/rules.md` remains readable by Dev/Review agents but is not directly writable by Writeback Agent
- `docs/rules-candidates.md` becomes the only AI write target for new or updated rule proposals
- `docs/rules-deprecated.md` exists as a future-safe destination for retired rules, but this round does not require automated use

### Writeback Report Contract

`writeback-report.md` remains the human-readable summary, but its rules section gains stronger semantics:

- If the report claims rule knowledge was produced, candidate content must exist in `docs/rules-candidates.md`
- If no new rules were produced, the report must say so explicitly

### WritebackGate Contract

`WritebackGate` should no longer assume that successful writeback means direct edits to `docs/rules.md`.

Pass conditions:

- `writeback-report.md` is complete
- If the report says "no new rules", missing candidate content is acceptable
- If the report says there are new or updated rules, `docs/rules-candidates.md` exists and contains non-template content

Warning conditions:

- The report does not clearly state whether this CR produced new rule proposals

Blocked conditions:

- The report claims rule writeback occurred, but `docs/rules-candidates.md` is missing
- The candidate file exists but still contains template placeholders or empty boilerplate

## File-Level Changes

### New Files

- `docs/rules-candidates.md`
  - Stores candidate rules proposed by CRs
  - Each entry should include at least:
    - source CR
    - trigger/background
    - proposed rule text
    - scope
    - promotion recommendation

- `docs/rules-deprecated.md`
  - Stores deprecated rules and the reason they were retired
  - This file is introduced now so the directory model is complete, even though no automation depends on it yet

### Updated Files

- `scripts/writeback_gate.py`
  - Stop treating direct `rules.md` updates as the expected path
  - Validate `rules-candidates.md` instead

- `AGENTS.md`
  - Remove direct Writeback Agent write permission to `docs/rules.md`
  - Add write permission for `docs/rules-candidates.md`

- `SKILL.md`
  - Update memory/writeback guidance to distinguish canonical and candidate rule stores

- `README.md`
  - Update repository structure and knowledge writeback description

- Example `writeback-report.md` content
  - Replace statements like "updated `docs/rules.md`" with "proposed updates in `docs/rules-candidates.md`"

## Data Shape

The candidate file does not need strict YAML or JSON in this round. Markdown is sufficient as long as entries are structured and auditable.

Recommended entry shape:

```md
## Candidate Rule: <short title>
- Source CR: CR-XXX
- Trigger: <what failure, review finding, or repeated issue caused this>
- Proposed Rule: <rule text>
- Scope: <where this applies>
- Promotion Recommendation: yes/no
```

## Permissions

New permission boundary:

- Read-only canonical rules: `docs/rules.md`
- Writable candidate rules: `docs/rules-candidates.md`

This reduces the chance that AI mutates organization-wide truth before human review.

## Testing Strategy

Minimum verification for this change:

- `WritebackGate` passes when the report explicitly says no new rules
- `WritebackGate` passes when the report claims new rules and the candidate file is present and populated
- `WritebackGate` blocks when the report claims new rules but the candidate file is absent
- `WritebackGate` blocks when the candidate file contains placeholders
- `selftest.py` still passes after the documentation and gate changes

## Risks

- Existing examples may still imply direct edits to `docs/rules.md`
- Candidate file semantics can become fuzzy if the report format is too loose
- If the report wording is not explicit enough, gate behavior may be ambiguous

## Risk Mitigation

- Update examples and agent docs together with gate logic
- Make `WritebackGate` rely on explicit text markers in `writeback-report.md`
- Keep the first version intentionally narrow: `rules` only, no broader memory refactor

## Implementation Sequence

1. Add candidate/deprecated rules docs
2. Update `writeback_gate.py` validation logic
3. Update `AGENTS.md`, `SKILL.md`, and `README.md`
4. Update example `writeback-report.md` references
5. Run selftest and targeted writeback checks
