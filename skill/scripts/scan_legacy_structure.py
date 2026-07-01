#!/usr/bin/env python3
"""
scan_legacy_structure.py - read-only structure assessment for legacy projects.

It reports directory risks and writes a candidate structure profile. It never
moves code.
"""

import argparse
import sys
from pathlib import Path
from typing import List

try:
    import yaml
except ImportError:
    print('需要 PyYAML：pip install PyYAML')
    sys.exit(2)

from runtime_support import configure_console

configure_console()

DELIVERHQ_ROOT = Path(__file__).resolve().parent.parent

SOURCE_EXTS = {".js", ".jsx", ".ts", ".tsx", ".py", ".go", ".java", ".cs"}
CONFIG_NAMES = {".env", ".env.production", "config.js", "config.py", "settings.py", "settings_prod.py"}
LEGACY_DIR_NAMES = {"src", "backend", "frontend", "server", "client", "utils", "common", "helpers"}


def list_top_level(project_root: Path):
    return [p for p in sorted(project_root.iterdir(), key=lambda item: item.name) if p.is_dir() and not p.name.startswith(".git")]


def collect_findings(project_root: Path):
    findings = []
    top_dirs = list_top_level(project_root)
    top_names = {p.name for p in top_dirs}

    if {"frontend", "backend"} & top_names:
        findings.append(("frontend-backend-split-legacy", "legacy frontend/backend top-level dirs detected", "medium"))
    if "src" in top_names and ({"pages", "controllers", "services"} & {p.name for p in (project_root / "src").iterdir() if p.is_dir()} if (project_root / "src").exists() else set()):
        findings.append(("mixed-src", "src appears to mix frontend/backend/layered code", "high"))
    if {"utils", "common", "helpers"} & top_names:
        findings.append(("shared-dump", "utils/common/helpers top-level dump detected", "high"))

    test_like = []
    config_like = []
    misplaced_source = []
    for path in project_root.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(project_root).as_posix()
        if any(part in {".git", "node_modules", ".venv", "venv", "__pycache__", "DeliverHQ"} for part in path.relative_to(project_root).parts):
            continue
        lower = rel.lower()
        name = path.name
        if name in CONFIG_NAMES or name.startswith(".env"):
            config_like.append(rel)
        if ("test" in name.lower() or "spec" in name.lower()) and not ("/tests/" in lower or lower.startswith("tests/")):
            test_like.append(rel)
        if path.suffix.lower() in SOURCE_EXTS and rel.split("/", 1)[0] in LEGACY_DIR_NAMES:
            misplaced_source.append(rel)

    for rel in config_like[:20]:
        findings.append(("config-scatter", "config or env file outside profile: %s" % rel, "high" if rel.startswith(".env") else "medium"))
    for rel in test_like[:20]:
        findings.append(("test-placement", "test-like file outside test dirs: %s" % rel, "medium"))
    if misplaced_source:
        findings.append(("legacy-source", "%d source files under legacy top-level dirs" % len(misplaced_source), "medium"))

    return findings, sorted(top_names)


def write_report(project_root: Path, out_dir: Path, findings, top_dirs):
    out_dir.mkdir(parents=True, exist_ok=True)
    report = out_dir / "structure-assessment-report.md"
    lines = [
        "# Structure Assessment Report",
        "",
        "> Read-only scan. No files were moved.",
        "",
        "## Top-Level Directories",
        "",
    ]
    for name in top_dirs:
        lines.append("- `%s`" % name)
    lines.extend(["", "## Findings", ""])
    if not findings:
        lines.append("No obvious structural issues detected.")
    else:
        for code, message, severity in findings:
            lines.append("- **%s** [%s]: %s" % (code, severity, message))
    lines.extend([
        "",
        "## Recommended Next Steps",
        "",
        "1. Review `STRUCTURE-PROFILE.candidate.yml`.",
        "2. If accepted, copy it to `DeliverHQ/STRUCTURE-PROFILE.yml`.",
        "3. Run StructureGate in progressive mode so legacy issues warn but new misplaced files block.",
        "4. Create migration CRs one module at a time.",
    ])
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def write_candidate_profile(project_root: Path, deliverhq_dir: Path, top_dirs: List[str]):
    profile_template = DELIVERHQ_ROOT / "structure-profiles" / "fullstack-web.yml"
    data = yaml.safe_load(profile_template.read_text(encoding="utf-8")) or {}
    data.setdefault("legacy", {})
    data["legacy"]["mode"] = "progressive"
    data["legacy"]["legacy_paths"] = [name for name in top_dirs if name in LEGACY_DIR_NAMES]
    out = deliverhq_dir / "STRUCTURE-PROFILE.candidate.yml"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    out.write_text(text, encoding="utf-8")
    return out


def main():
    parser = argparse.ArgumentParser(description="Scan legacy project structure without modifying source")
    parser.add_argument("project_root", nargs="?", default=".")
    parser.add_argument("--out", default=None, help="reports output dir; default DeliverHQ/docs/reports")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    if not project_root.exists():
        print('扫描目录不存在: %s' % project_root)
        sys.exit(1)
    if not project_root.is_dir():
        print('不是目录: %s' % project_root)
        sys.exit(1)
    deliverhq_dir = project_root / "DeliverHQ"
    out_dir = Path(args.out).resolve() if args.out else deliverhq_dir / "docs" / "reports"

    findings, top_dirs = collect_findings(project_root)
    report = write_report(project_root, out_dir, findings, top_dirs)
    candidate = write_candidate_profile(project_root, deliverhq_dir, top_dirs)

    print("✅ Legacy structure scan complete")
    print("report: %s" % report)
    print("candidate_profile: %s" % candidate)
    print("findings: %d" % len(findings))


if __name__ == "__main__":
    main()
