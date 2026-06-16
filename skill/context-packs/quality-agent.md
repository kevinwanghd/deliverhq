# Quality Agent Context Pack

## Must Read
- `change-requests/<CR>/quality-report.md`
- `change-requests/<CR>/verification-manifest.yml`
- `change-requests/<CR>/review-report.md`
- `change-requests/<CR>/state.yml`

## Must Not Read
- Narrative-only reports without executable evidence
- Unscoped repository history

## Allowed Writes
- `change-requests/<CR>/quality-report.md`
- `change-requests/<CR>/evidence/**`
- `change-requests/<CR>/artifacts/**`

## Current Objective
- Bind quality judgment to real verification commands and evidence.

## Required Evidence
- Commands executed
- Verification outputs
- Blocking findings

## Next Gate
- `writeback`
