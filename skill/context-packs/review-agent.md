# Review Agent Context Pack

## Must Read
- `change-requests/<CR>/acceptance-spec.md`
- `change-requests/<CR>/review-report.md`
- `change-requests/<CR>/traceability.yml`
- `change-requests/<CR>/test-plan.md`
- `change-requests/<CR>/state.yml`

## Must Not Read
- Free-form summaries not tied to changed files
- Irrelevant legacy CRs

## Allowed Writes
- `change-requests/<CR>/review-report.md`
- `change-requests/<CR>/evidence/**`
- `change-requests/<CR>/artifacts/**`

## Current Objective
- Verify the real implementation against the spec, traceability, and tests.

## Required Evidence
- Changed files list
- Traceability coverage
- Review findings

## Next Gate
- `quality`
