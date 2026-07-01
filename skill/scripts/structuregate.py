#!/usr/bin/env python3
"""
StructureGate - project directory structure governance.

New projects use strict mode. Legacy projects can use progressive mode: existing
legacy paths are warnings, but new misplaced files are blocked.
"""

import argparse
import fnmatch
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

from runtime_support import configure_console

configure_console()

DELIVERHQ_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE = DELIVERHQ_ROOT / "STRUCTURE-PROFILE.yml"

SOURCE_EXTS = {".js", ".jsx", ".ts", ".tsx", ".py", ".go", ".java", ".cs", ".rb", ".php", ".swift", ".kt"}
TEST_MARKERS = ("test", "spec")
CONFIG_MARKERS = ("config", "settings")


class Color:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    END = "\033[0m"


def load_profile(path: Path) -> Dict:
    if not path.exists():
        raise FileNotFoundError("STRUCTURE-PROFILE.yml 不存在: %s" % path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if data.get("schema") != "deliverhq-structure-profile":
        raise ValueError("STRUCTURE-PROFILE.yml schema 必须为 deliverhq-structure-profile")
    return data


def _match(path: str, patterns: List[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns)


def _collect_files(project_root: Path) -> List[Path]:
    ignored_parts = {".git", "node_modules", ".venv", "venv", "__pycache__", ".claude", "DeliverHQ"}
    files: List[Path] = []
    for path in project_root.rglob("*"):
        if path.is_dir():
            continue
        if any(part in ignored_parts for part in path.relative_to(project_root).parts):
            continue
        files.append(path)
    return files


def _is_test_file(rel: str) -> bool:
    lower = rel.lower()
    name = Path(rel).name.lower()
    return any(marker in name for marker in TEST_MARKERS) or "/tests/" in lower or lower.startswith("tests/")


def _is_config_file(rel: str) -> bool:
    lower = rel.lower()
    name = Path(rel).name.lower()
    return any(marker in name for marker in CONFIG_MARKERS) or (name.startswith(".") and "env" in name)


def _under_legacy_path(rel: str, legacy_paths) -> bool:
    return any(rel == legacy or rel.startswith(legacy.rstrip("/") + "/") for legacy in legacy_paths)


def _add_placement_issue(rel: str, message: str, mode: str, legacy_paths, blockers: List[str], warnings: List[str]):
    if mode == "progressive" and _under_legacy_path(rel, legacy_paths):
        warnings.append(message + "（legacy fenced）")
    else:
        blockers.append(message)


def lint_structure(project_root: Path, profile_path: Path, mode_override: str = None) -> Tuple[List[str], List[str]]:
    blockers: List[str] = []
    warnings: List[str] = []

    profile = load_profile(profile_path)
    mode = mode_override or (profile.get("legacy", {}) or {}).get("mode") or "strict"
    required_dirs = profile.get("required_dirs") or []
    allowed_top = set(profile.get("allowed_top_level_dirs") or [])
    forbidden_top = set(profile.get("forbidden_top_level_dirs") or [])
    forbidden_files = set(profile.get("forbidden_files") or [])
    placement_rules = profile.get("placement_rules") or {}
    legacy_paths = set((profile.get("legacy", {}) or {}).get("legacy_paths") or [])

    for rel_dir in required_dirs:
        if not (project_root / rel_dir).exists():
            message = "缺少必需目录: %s" % rel_dir
            if mode == "progressive":
                warnings.append(message + "（progressive mode）")
            else:
                blockers.append(message)

    for child in project_root.iterdir():
        name = child.name
        if name.startswith(".") and name != ".github":
            continue
        if child.is_dir() and name in forbidden_top:
            message = "发现禁止顶层目录: %s" % name
            if mode == "progressive" and _under_legacy_path(name, legacy_paths):
                warnings.append(message + "（legacy fenced）")
            else:
                blockers.append(message)
        elif child.is_dir() and allowed_top and name not in allowed_top:
            message = "发现未授权顶层目录: %s" % name
            if mode == "progressive" and _under_legacy_path(name, legacy_paths):
                warnings.append(message + "（legacy fenced）")
            else:
                blockers.append(message)

    files = _collect_files(project_root)
    for path in files:
        rel = path.relative_to(project_root).as_posix()
        name = path.name
        if name in forbidden_files or _match(rel, list(forbidden_files)):
            _add_placement_issue(rel, "发现禁止提交文件: %s" % rel, mode, legacy_paths, blockers, warnings)

        if path.suffix.lower() in SOURCE_EXTS:
            if _is_test_file(rel):
                allowed = placement_rules.get("tests", {}).get("allowed", [])
                forbidden = placement_rules.get("tests", {}).get("forbidden", [])
                if _match(rel, forbidden) or (allowed and not _match(rel, allowed)):
                    _add_placement_issue(rel, "测试文件位置不符合 profile: %s" % rel, mode, legacy_paths, blockers, warnings)
            elif rel.startswith("apps/api/") or rel.startswith("src/") or rel.startswith("backend/") or rel.startswith("server/"):
                allowed = placement_rules.get("backend_source", {}).get("allowed", [])
                forbidden = placement_rules.get("backend_source", {}).get("forbidden", [])
                if _match(rel, forbidden) or (rel.startswith("apps/api/") and allowed and not _match(rel, allowed)):
                    _add_placement_issue(rel, "后端源码位置不符合 profile: %s" % rel, mode, legacy_paths, blockers, warnings)
            elif rel.startswith("apps/web/") or rel.startswith("frontend/") or rel.startswith("client/"):
                allowed = placement_rules.get("frontend_source", {}).get("allowed", [])
                forbidden = placement_rules.get("frontend_source", {}).get("forbidden", [])
                if _match(rel, forbidden) or (rel.startswith("apps/web/") and allowed and not _match(rel, allowed)):
                    _add_placement_issue(rel, "前端源码位置不符合 profile: %s" % rel, mode, legacy_paths, blockers, warnings)

        if _is_config_file(rel):
            allowed = placement_rules.get("config", {}).get("allowed", [])
            forbidden = placement_rules.get("config", {}).get("forbidden", [])
            if _match(rel, forbidden) or (allowed and not _match(rel, allowed)):
                _add_placement_issue(rel, "配置文件位置不符合 profile: %s" % rel, mode, legacy_paths, blockers, warnings)

    return blockers, warnings


def main():
    parser = argparse.ArgumentParser(description="Run DeliverHQ StructureGate")
    parser.add_argument("project_root", nargs="?", default=".", help="project root to lint")
    parser.add_argument("--profile", default=None, help="STRUCTURE-PROFILE.yml path")
    parser.add_argument("--mode", choices=["strict", "progressive", "migration"], help="override profile mode")
    parser.add_argument("--json", action="store_true", help="output JSON")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    profile_path = Path(args.profile).resolve() if args.profile else project_root / "DeliverHQ" / "STRUCTURE-PROFILE.yml"
    if not profile_path.exists() and (project_root / "STRUCTURE-PROFILE.yml").exists():
        profile_path = project_root / "STRUCTURE-PROFILE.yml"

    try:
        blockers, warnings = lint_structure(project_root, profile_path, args.mode)
    except Exception as exc:
        blockers, warnings = [str(exc)], []

    if args.json:
        print(json.dumps({"blockers": blockers, "warnings": warnings, "passed": not blockers}, ensure_ascii=False, indent=2))
    else:
        print("%s=== StructureGate ===%s" % (Color.BLUE, Color.END))
        print("project_root: %s" % project_root)
        print("profile: %s" % profile_path)
        if warnings:
            print("%sWarnings:%s" % (Color.YELLOW, Color.END))
            for warning in warnings:
                print("  - %s" % warning)
        if blockers:
            print("%s❌ BLOCKED%s" % (Color.RED, Color.END))
            for blocker in blockers:
                print("  - %s" % blocker)
        else:
            print("%s✅ PASS%s" % (Color.GREEN, Color.END))

    sys.exit(1 if blockers else 0)


if __name__ == "__main__":
    main()
