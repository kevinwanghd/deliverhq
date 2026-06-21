# Review Context Pack

> Minimal pack for Review Agent. Do not rely on Dev Agent self-report alone.

## Must read

1. `acceptance-spec.md`
2. `traceability.yml`
3. `test-plan.md`
4. `verification-manifest.yml`
5. `evidence/changed-files.json`
6. Relevant source diff / changed files

## Review questions

- Do changed files match `traceability.yml`?
- Do tests cover each P0 acceptance criterion?
- Does `verification-manifest.yml` contain real build/test/lint commands?
- Are protected paths involved? If yes, require PermissionGate / human approval.
- Adversarial checks: did the change delete/disable tests, lower quality thresholds, bypass gates, cover only happy paths, or miss boundary conditions?

## Output

Write `review-report.md`, then run:

```bash
python scripts/reviewgate.py change-requests/CR-XXX
```
