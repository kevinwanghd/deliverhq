#!/usr/bin/env python3
"""Check installed DeliverHQ skeleton completeness."""

import sys
from pathlib import Path


REQUIRED_FILES = [
    "CLAUDE.md",
    "AGENTS.md",
    "attention.md",
    "dir-graph.yaml",
    "README.md",
    ".ai-instructions",
    "docs/CONTEXT.md",
    "docs/architecture.md",
    "docs/interfaces.md",
    "docs/data-model.md",
    "docs/rules.md",
    "docs/decisions.md",
    "docs/mistake-book.md",
    "docs/verification.md",
    "notes/_index.md",
    "inbox/README.md",
    "journal/README.md",
    "docs/reports/code-health-report.md",
    "docs/reports/legacy-scan-report.md",
    "change-requests/CR-TEMPLATE/request.md",
    "change-requests/CR-TEMPLATE/acceptance-spec.md",
    "change-requests/CR-TEMPLATE/architecture-design.md",
    "change-requests/CR-TEMPLATE/architecture-alignment-report.md",
    "change-requests/CR-TEMPLATE/context-summary.md",
    "change-requests/CR-TEMPLATE/implementation-plan.md",
    "change-requests/CR-TEMPLATE/test-plan.md",
    "change-requests/CR-TEMPLATE/quality-report.md",
    "change-requests/CR-TEMPLATE/writeback-report.md",
    "change-requests/CR-TEMPLATE/human-decisions.md",
    "change-requests/CR-TEMPLATE/traceability.yml",
    "change-requests/CR-TEMPLATE/exceptions.yml",
    "change-requests/CR-TEMPLATE/design/lo-fi-spec.md",
    "change-requests/CR-TEMPLATE/design/hi-fi-spec.md",
    "change-requests/CR-TEMPLATE/design/prototype.html",
    "change-requests/CR-TEMPLATE/design/design-decisions.md",
    "change-requests/CR-TEMPLATE/design/direct-read-audit.md",
    "change-requests/CR-TEMPLATE/design/visual-audit-report.md",
    "change-requests/CR-TEMPLATE/design/assets/README.md",
    "change-requests/CR-TEMPLATE/specgate-report.md",
    "change-requests/CR-TEMPLATE/designgate-report.md",
    "change-requests/CR-TEMPLATE/context-window-report.md",
    "change-requests/CR-TEMPLATE/qualitygate-report.md",
    "change-requests/CR-TEMPLATE/writeback-gate-report.md",
    "scripts/pre_dev_gate.py",
    "scripts/check_skeleton.py",
    "scripts/init_cr.py",
    "scripts/deliver.py",
    "scripts/specgate.py",
    "scripts/prd_validate.py",
    "scripts/prd_sync.py",
    "scripts/designgate.py",
    "scripts/architecturegate.py",
    "scripts/context_window_check.py",
    "scripts/qualitygate.py",
    "scripts/writeback_gate.py",
    "scripts/update_rule_maturity.py",
    "scripts/update_mistake_book.py",
    "MIGRATION.md",
    "ROLLBACK.md",
]

REQUIRED_DIRS = [
    "docs",
    "docs/reports",
    "notes",
    "inbox",
    "journal",
    "change-requests",
    "change-requests/CR-TEMPLATE",
    "change-requests/CR-TEMPLATE/design",
    "delivery",
    "_archived",
    "scripts",
]

PRODUCT_REQUIRED_FILES = [
    "INSTALL-PROFILE.yml",
    "AGENTS.md",
    "COMMANDS.yml",
    "README.md",
    "SKILL.md",
    "VERSION.yml",
    "dir-graph.yaml",
    "docs/PRD.md",
    "scripts/check_skeleton.py",
    "scripts/dir_graph_lint.py",
    "scripts/health_check.py",
    "scripts/prd_validate.py",
    "scripts/prd_sync.py",
    "scripts/runtime_support.py",
]

PRODUCT_REQUIRED_DIRS = [
    "docs",
    "scripts",
]


def detect_install_profile(base: Path) -> str:
    profile_path = base / "INSTALL-PROFILE.yml"
    if not profile_path.exists():
        return "full"
    for line in profile_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("profile:"):
            return line.split(":", 1)[1].strip() or "full"
    return "full"


def check_completeness(base_dir=".") -> bool:
    base = Path(base_dir)
    profile = detect_install_profile(base)
    required_dirs = PRODUCT_REQUIRED_DIRS if profile == "product" else REQUIRED_DIRS
    required_files = PRODUCT_REQUIRED_FILES if profile == "product" else REQUIRED_FILES

    print("=== DeliverHQ skeleton check ===")
    print(f"install profile: {profile}")

    missing_dirs = []
    missing_files = []

    print("\n[directories]")
    for dir_path in required_dirs:
        full_path = base / dir_path
        if full_path.exists():
            print(f"  OK {dir_path}")
        else:
            print(f"  MISSING {dir_path}")
            missing_dirs.append(dir_path)

    print("\n[files]")
    for file_path in required_files:
        full_path = base / file_path
        if full_path.exists():
            print(f"  OK {file_path}")
        else:
            print(f"  MISSING {file_path}")
            missing_files.append(file_path)

    print("\n[summary]")
    print(f"directories: {len(required_dirs) - len(missing_dirs)}/{len(required_dirs)}")
    print(f"files: {len(required_files) - len(missing_files)}/{len(required_files)}")

    if not missing_dirs and not missing_files:
        print("\nPASS")
        return True

    print("\nBLOCKED")
    if missing_dirs:
        print(f"\nmissing directories ({len(missing_dirs)}):")
        for item in missing_dirs:
            print(f"  - {item}")
    if missing_files:
        print(f"\nmissing files ({len(missing_files)}):")
        for item in missing_files:
            print(f"  - {item}")
    return False


def main() -> None:
    base_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    passed = check_completeness(base_dir)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
