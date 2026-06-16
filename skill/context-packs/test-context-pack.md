# Test Context Pack

> Minimal pack for Test Agent. Tests should be based on acceptance criteria, not implementation claims.

## Must read

1. `acceptance-spec.md`
2. `traceability.yml`
3. `verification-manifest.yml`
4. Relevant source files listed in `evidence/changed-files.json`

## Test requirements

- Cover P0 happy path, error path, and boundary cases.
- Update `test-plan.md` with actual evidence.
- Keep `verification-manifest.yml` executable and current.

## Output

- Test code in the host project test directory
- Updated `test-plan.md`
- Updated `verification-manifest.yml` if commands changed
