# Test Plan: CR-005

## Automated Tests

- `python -m unittest discover -s tests -v`
- `python scripts/capability_registry.py check --json`
- `node --check ../bin/cli.js`
- `npm pack --dry-run --json`
- `python scripts/selftest.py`

## Required Results

- Unit tests: 25/25 pass.
- Registry check: 52 capabilities, matrix current.
- npm package: <=260 files and <=1.2 MB unpacked.
- DeliverHQ selftest: 37/37 pass.

## Platforms

GitHub Actions matrix remains Ubuntu/Windows with Python 3.10/3.13.

