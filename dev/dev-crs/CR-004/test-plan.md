# Test Plan: CR-004

## Automated Tests

- `python -m unittest discover -s tests -v`
- `python scripts/selftest.py`
- `python scripts/gate_composition_check.py`
- `node --check ../bin/cli.js`
- `npm pack --dry-run` from repository root

## Required Results

- Runtime/module tests: 17/17 pass.
- DeliverHQ selftest: 37/37 pass.
- Gate composition: PASS with no new Gate.
- Package and Node syntax checks: PASS.

## Platforms

GitHub Actions matrix: Ubuntu/Windows with Python 3.10/3.13.
