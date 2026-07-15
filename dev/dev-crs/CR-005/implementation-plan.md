# Implementation Plan: CR-005 Productize Packaging and Metadata

## Scope

Implement the approved architecture for a slimmer npm package, a machine-readable capability registry, and a formal `deliverhq` Python package while preserving existing script entrypoints.

## Steps

1. Add failing tests for registry validation/rendering, script compatibility, and npm pack budget.
2. Introduce `skill/deliverhq/` package modules for capabilities, runtime, and routing.
3. Keep existing `skill/scripts/*` entrypoints as compatibility wrappers.
4. Generate `capabilities.yml` from the current matrix, then make `CAPABILITY-MATRIX.md` a checked generated view.
5. Add npm ignore policy and packaging assertions for file count, unpacked size, required files, and forbidden paths.
6. Run registry tests, full unit tests, selftest, npm pack dry-run, ReviewGate, QualityGate, and anti-gaming checks.

## Risks

- npm packlist behavior can differ between `files` and `.npmignore`; the packaging test is the source of truth.
- Moving runtime/routing code can break imports if script-path compatibility is incomplete.
- Matrix generation must preserve human guidance outside the generated table.

