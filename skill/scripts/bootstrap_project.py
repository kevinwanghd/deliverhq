#!/usr/bin/env python3
"""Evidence-first brownfield bootstrap facade over DeliverHQ legacy scanners."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import yaml

from scan_legacy import detect_tech_stack, find_source_files, find_test_files
from scan_legacy_structure import collect_findings

DOC_PATTERNS = (
    "AGENTS.md", "CLAUDE.md", "CONTEXT.md", "ARCHITECTURE.md",
    "CONTRIBUTING.md", "README.md", ".clinerules",
)
EXTRA_DOC_GLOBS = (
    ".cursor/rules/*.md", ".windsurf/rules/*.md",
    ".github/copilot-instructions.md",
)


def file_evidence(path: Path, root: Path) -> dict:
    data = path.read_bytes()
    return {
        "path": path.relative_to(root).as_posix(),
        "line": 1,
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def discover_documents(root: Path) -> list[dict]:
    found = []
    for name in DOC_PATTERNS:
        for path in (root / name, root / ".specs" / name):
            if path.is_file():
                found.append({"kind": name, "status": "confirmed", "evidence": file_evidence(path, root)})
    for pattern in EXTRA_DOC_GLOBS:
        for path in root.glob(pattern):
            if path.is_file():
                found.append({"kind": path.name, "status": "confirmed", "evidence": file_evidence(path, root)})
    return sorted(found, key=lambda item: item["evidence"]["path"])


def detect_commands(root: Path) -> dict:
    result = {name: {"enabled": False, "command": None, "evidence": None}
              for name in ("build", "test", "lint", "typecheck")}
    package = root / "package.json"
    if package.is_file():
        try:
            scripts = json.loads(package.read_text(encoding="utf-8")).get("scripts", {})
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            scripts = {}
        mapping = {"build": "build", "test": "test", "lint": "lint", "typecheck": "typecheck"}
        for key, script_name in mapping.items():
            if script_name in scripts:
                result[key] = {
                    "enabled": True,
                    "command": f"npm run {script_name}",
                    "evidence": file_evidence(package, root),
                }
    if (root / "pyproject.toml").is_file() or (root / "pytest.ini").is_file():
        marker = root / "pyproject.toml" if (root / "pyproject.toml").is_file() else root / "pytest.ini"
        if not result["test"]["enabled"]:
            result["test"] = {"enabled": True, "command": "python -m pytest", "evidence": file_evidence(marker, root)}
    return result


def discover_abstractions(root: Path) -> list[dict]:
    names = {"utils", "helpers", "shared", "common", "services", "hooks", "middleware", "repositories"}
    found = []
    for base in (root / "src", root / "lib", root / "app"):
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.is_dir() and path.name.lower() in names:
                found.append({"kind": path.name.lower(), "status": "inferred", "path": path.relative_to(root).as_posix()})
    return sorted(found, key=lambda item: (item["kind"], item["path"]))


def build_bootstrap_report(root: Path) -> dict:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError("invalid_repository_path")
    primary_stack, language_counts = detect_tech_stack(root)
    source_files = find_source_files(root, primary_stack)
    tests = find_test_files(root)
    structure_findings, top_names = collect_findings(root)
    source_evidence = [file_evidence(path, root) for path in source_files[:5] if path.is_file()]
    report = {
        "schema": "deliverhq-bootstrap-report",
        "version": 1,
        "repository": str(root),
        "documents": discover_documents(root),
        "tech_stack": primary_stack,
        "language_counts": language_counts,
        "top_level": top_names,
        "structure_findings": [
            {"code": code, "message": message, "severity": severity, "status": "inferred"}
            for code, message, severity in structure_findings
        ],
        "source_file_count": len(source_files),
        "test_file_count": len(tests),
        "commands": detect_commands(root),
        "abstractions": discover_abstractions(root),
        "findings": [{
            "kind": "tech_stack", "value": primary_stack, "status": "inferred",
            "evidence": source_evidence,
        }],
        "context_policy": "review-existing-documents-before-generating-context",
        "warnings": [],
    }
    for item in report["documents"]:
        if item["status"] == "confirmed" and not item.get("evidence"):
            raise ValueError("confirmed_finding_missing_evidence")
    return report


def render_context_candidate(report: dict) -> str:
    docs = "\n".join(
        f"- `{item['evidence']['path']}` sha256 `{item['evidence']['sha256']}`"
        for item in report["documents"]
    ) or "- 未发现已有上下文文档"
    return (
        "# CONTEXT Candidate\n\n"
        "> 由 DeliverHQ bootstrap 生成，需人工审查后再采用。\n\n"
        "## 来源文档\n\n" + docs + "\n\n"
        f"## 技术栈\n\n- `{report['tech_stack']}`\n\n"
        "## 既有抽象索引\n\n" +
        ("\n".join(f"- {x['kind']}: `{x['path']}`" for x in report["abstractions"]) or "- 未识别") + "\n"
    )


def render_repo_map_candidate(report: dict) -> str:
    rows = "\n".join(f"| `{name}` | 待人工确认 |" for name in report["top_level"])
    return "# REPO MAP Candidate\n\n| Path | Purpose |\n|---|---|\n" + rows + "\n"


def candidate_outputs(report: dict) -> dict[str, str]:
    commands = {
        key: {"enabled": value["enabled"], "command": value["command"]}
        for key, value in report["commands"].items()
    }
    return {
        "bootstrap-report.json": json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        "CONTEXT.candidate.md": render_context_candidate(report),
        "REPO_MAP.candidate.md": render_repo_map_candidate(report),
        "COMMANDS.candidate.yml": yaml.safe_dump(commands, allow_unicode=True, sort_keys=False),
    }


def apply_candidates(report: dict, home: Path) -> list[dict]:
    home.mkdir(parents=True, exist_ok=True)
    results = []
    for name, content in candidate_outputs(report).items():
        path = home / name
        if path.exists():
            results.append({"path": str(path), "status": "conflict", "written": False})
            continue
        path.write_text(content, encoding="utf-8", newline="\n")
        results.append({"path": str(path), "status": "created", "written": True})
    return results


def validate_home(root: Path, home: Path) -> Path:
    resolved_root = root.resolve()
    resolved_home = home.resolve()
    if resolved_home.name.lower() != "deliverhq" or (
        resolved_home != resolved_root / "DeliverHQ" and resolved_root not in resolved_home.parents
    ):
        raise ValueError("invalid_deliverhq_home")
    return resolved_home


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default=".")
    parser.add_argument("--home", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        root = Path(args.path).resolve()
        report = build_bootstrap_report(root)
        home = validate_home(root, Path(args.home) if args.home else root / "DeliverHQ")
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    writes = apply_candidates(report, home) if args.apply else []
    payload = {"report": report, "writes": writes}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Bootstrap: {root}")
        print(f"documents={len(report['documents'])} sources={report['source_file_count']} tests={report['test_file_count']}")
        print("mode=apply" if args.apply else "mode=report-only")
        for item in writes:
            print(f"{item['status']}: {item['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
