# Context Summary: CR-004

## Previous Phase Summary

The first reliability batch shipped v5.15.4 with entrypoint tests, Windows/Linux CI, UTF-8 fixes, and explicit disabled command templates.

## Current Phase Focus

Refactor runtime structure while preserving all external behavior. The current baselines are 7/7 entrypoint tests and 37/37 selftest contracts.

## Key Decisions

- Keep all public script filenames and CLI arguments.
- Keep the frozen Gate set unchanged.
- Introduce one standard-library-only execution module.
- Extract in small phases with independent tests and commits.

## Open Questions

None. Architecture confirmed by Kevin on 2026-07-11.
