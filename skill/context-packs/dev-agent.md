# Dev Agent Context Pack

## Must Read
- `change-requests/<CR>/acceptance-spec.md`
- `change-requests/<CR>/implementation-plan.md`
- `change-requests/<CR>/traceability.yml`
- `change-requests/<CR>/state.yml`

## Must Not Read
- Unrelated CR directories
- Historical reports not referenced by the current CR

## Allowed Writes
- Product code inside approved source paths
- `change-requests/<CR>/traceability.yml`
- `change-requests/<CR>/workspace/**`
- `change-requests/<CR>/artifacts/**`

## Current Objective
- Implement the approved change without crossing protected boundaries.

## Required Evidence
- Code diff
- Updated traceability
- Build/test artifacts if generated

## Next Gate
- `review`
