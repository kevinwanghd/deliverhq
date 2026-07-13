# Implementation Plan: CR-004

## Phase 1: Execution Runtime

1. Add failing tests for successful execution, non-zero exit, timeout, and UTF-8 output.
2. Implement `ExecutionResult` and `run_script` in `execution_runtime.py`.
3. Migrate `gate_wrapper.py` to the new interface without changing CLI behavior.
4. Run entrypoint tests and selftest.

## Phase 2: Orchestrator Responsibilities

1. Add dependency-direction and public routing regression tests.
2. Extract cost estimation, cache detection, CR sizing, and situation routing into `orchestrator_routing.py`.
3. Keep compatibility imports/wrappers in `skill_orchestrator.py` where callers depend on them.
4. Run orchestrator contracts and full selftest.

## Phase 3: Selftest Contract Modules

1. Add a structural test requiring domain contract modules and a smaller entrypoint.
2. Extract related contract checks into `selftest_contracts/core.py`, `workflow.py`, and `governance.py`.
3. Preserve the existing 37 result keys, order, output summary, and CLI flags.
4. Run all local tests, 37/37 selftest, packaging, token budget, and GitHub CI.

## Rollback

Each phase is committed independently. Revert the phase commit if compatibility tests fail; no data migration or persistent format change is involved.
