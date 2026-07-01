#!/usr/bin/env python3
"""
Baseline Comparison - 基线对比机制

目标：
1. pre-dev 生成 baseline-before
2. quality 生成 baseline-after
3. 允许历史失败存在，但不允许新增 build/test/lint/type failure
"""


import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

sys.dont_write_bytecode = True

from runtime_support import configure_console, ensure_cr_runtime_dirs

configure_console()

DELIVERHQ_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = DELIVERHQ_ROOT.parent
SUBPROCESS_ENV = {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}


def _load_host_repo_root() -> Path:
    graph_path = DELIVERHQ_ROOT / "dir-graph.yaml"
    if graph_path.exists():
        try:
            data = {}
            for doc in yaml.safe_load_all(graph_path.read_text(encoding="utf-8")):
                if isinstance(doc, dict):
                    data.update(doc)
            relative_root = data.get("workspace", {}).get("host_repo_root")
            if relative_root:
                return (DELIVERHQ_ROOT / relative_root).resolve()
        except Exception:
            pass
    return PROJECT_ROOT.resolve()


HOST_REPO_ROOT = _load_host_repo_root()


@dataclass
class CommandResult:
    name: str
    category: str
    command: str
    working_dir: str
    timeout: int
    success: bool
    returncode: int
    stdout: str
    stderr: str


@dataclass
class BaselineResult:
    timestamp: str
    commit_hash: str
    commands_run: List[str]
    build_passed: bool
    build_errors: List[str]
    tests_total: int
    tests_passed: int
    tests_failed: int
    failing_tests: List[str]
    lint_errors: int
    lint_warnings: int
    type_errors: int
    coverage_percent: Optional[float]
    command_config: Dict
    command_results: List[CommandResult] = field(default_factory=list)


def _baseline_file(cr_path: Path, phase: str) -> Path:
    ensure_cr_runtime_dirs(cr_path)
    return cr_path / "evidence" / f"baseline-{phase}.json"


def _comparison_file(cr_path: Path) -> Path:
    ensure_cr_runtime_dirs(cr_path)
    return cr_path / "evidence" / "baseline-comparison.json"


def load_verification_manifest(cr_path: Path) -> Tuple[Optional[Dict], Optional[str]]:
    manifest_path = cr_path / "verification-manifest.yml"
    if not manifest_path.exists():
        return None, "verification-manifest.yml 不存在"
    try:
        return yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}, None
    except Exception as exc:
        return None, f"解析 verification-manifest.yml 失败: {exc}"


def _resolve_working_dir(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    base_dir = HOST_REPO_ROOT if HOST_REPO_ROOT.exists() else DELIVERHQ_ROOT
    return (base_dir / path).resolve()


def _run_command(name: str, category: str, command: str, working_dir: str, timeout: int) -> CommandResult:
    resolved_cwd = _resolve_working_dir(working_dir)
    proc = subprocess.run(
        command,
        shell=True,
        cwd=resolved_cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=timeout,
        env={**dict(os.environ), **SUBPROCESS_ENV},
    )
    return CommandResult(
        name=name,
        category=category,
        command=command,
        working_dir=str(resolved_cwd),
        timeout=timeout,
        success=proc.returncode == 0,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def _parse_test_metrics(output: str) -> Tuple[int, int, List[str], Optional[float]]:
    passed = 0
    failed = 0
    failing_tests = re.findall(r'FAILED\s+([^\s]+)', output)[:20]

    passed_match = re.search(r'(\d+)\s+passed', output, re.IGNORECASE)
    failed_match = re.search(r'(\d+)\s+failed', output, re.IGNORECASE)
    if passed_match:
        passed = int(passed_match.group(1))
    if failed_match:
        failed = int(failed_match.group(1))

    coverage = None
    # 优先匹配带 coverage 上下文的百分比，避免误抓其他百分比（如 "15% improvement"）
    coverage_match = re.search(r'(?i)coverage[^0-9]*?(\d+(?:\.\d+)?)\s*%', output)
    if not coverage_match:
        # 兜底：TOTAL 行末尾的百分比（coverage.py 的典型格式）
        coverage_match = re.search(r'(?im)^TOTAL\b.*?(\d+(?:\.\d+)?)\s*%', output)
    if coverage_match:
        coverage = float(coverage_match.group(1))

    return passed, failed, failing_tests, coverage


def _parse_count(output: str, keyword: str) -> int:
    match = re.search(rf'(\d+)\s+{keyword}', output, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _manifest_to_commands(manifest: Dict) -> List[Dict]:
    commands: List[Dict] = []

    build = manifest.get("build", {})
    if build.get("enabled", False):
        commands.append({
            "name": "build",
            "category": "build",
            "command": build["command"],
            "working_dir": build.get("working_dir", "."),
            "timeout": build.get("timeout", 300),
        })

    unit = manifest.get("test", {}).get("unit", {})
    if unit.get("enabled", False):
        commands.append({
            "name": "test-unit",
            "category": "test",
            "command": unit["command"],
            "working_dir": unit.get("working_dir", "."),
            "timeout": unit.get("timeout", 600),
        })

    lint = manifest.get("lint", {})
    if lint.get("enabled", False):
        for tool in lint.get("tools", []) or []:
            if tool.get("enabled", True):
                commands.append({
                    "name": tool["name"],
                    "category": "lint",
                    "command": tool["command"],
                    "working_dir": tool.get("working_dir", "."),
                    "timeout": tool.get("timeout", 300),
                })

    typecheck = manifest.get("typecheck", {})
    if typecheck.get("enabled", False):
        commands.append({
            "name": typecheck.get("name", "typecheck"),
            "category": "typecheck",
            "command": typecheck["command"],
            "working_dir": typecheck.get("working_dir", "."),
            "timeout": typecheck.get("timeout", 300),
        })

    return commands


def run_baseline(cr_path: Path, manifest: Dict) -> BaselineResult:
    try:
        commit_hash = subprocess.check_output(
            ["git", "-C", str(HOST_REPO_ROOT), "rev-parse", "HEAD"],
            universal_newlines=True,
            stderr=subprocess.DEVNULL,
            env={**dict(os.environ), **SUBPROCESS_ENV},
        ).strip()
    except Exception:
        commit_hash = "unknown"

    commands = _manifest_to_commands(manifest)
    result = BaselineResult(
        timestamp=datetime.now().isoformat(),
        commit_hash=commit_hash,
        commands_run=[item["command"] for item in commands],
        build_passed=True,
        build_errors=[],
        tests_total=0,
        tests_passed=0,
        tests_failed=0,
        failing_tests=[],
        lint_errors=0,
        lint_warnings=0,
        type_errors=0,
        coverage_percent=None,
        command_config=manifest,
        command_results=[],
    )

    for item in commands:
        command_result = _run_command(
            name=item["name"],
            category=item["category"],
            command=item["command"],
            working_dir=item["working_dir"],
            timeout=item["timeout"],
        )
        result.command_results.append(command_result)
        output = f"{command_result.stdout}\n{command_result.stderr}"

        if item["category"] == "build":
            result.build_passed = command_result.success
            if not command_result.success:
                result.build_errors.append(output.strip()[:500] or f"exit {command_result.returncode}")

        elif item["category"] == "test":
            passed, failed, failing_tests, coverage = _parse_test_metrics(output)
            if command_result.success and passed == 0 and failed == 0:
                passed = 1
            result.tests_passed = passed
            result.tests_failed = failed if failed or passed else (0 if command_result.success else 1)
            result.tests_total = result.tests_passed + result.tests_failed
            result.failing_tests = failing_tests
            if coverage is not None:
                result.coverage_percent = coverage

        elif item["category"] == "lint":
            result.lint_errors += _parse_count(output, "error")
            result.lint_warnings += _parse_count(output, "warning")
            if not command_result.success and result.lint_errors == 0:
                result.lint_errors += 1

        elif item["category"] == "typecheck":
            parsed_type_errors = _parse_count(output, "error")
            result.type_errors += parsed_type_errors if parsed_type_errors else (0 if command_result.success else 1)

    return result


def save_baseline(cr_path: Path, phase: str, result: BaselineResult) -> Path:
    output_file = _baseline_file(cr_path, phase)
    output_file.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 基线已保存: {output_file}")
    return output_file


def load_baseline(cr_path: Path, phase: str) -> Optional[BaselineResult]:
    baseline_file = _baseline_file(cr_path, phase)
    if not baseline_file.exists():
        return None

    data = json.loads(baseline_file.read_text(encoding="utf-8"))
    command_results = [CommandResult(**item) for item in data.get("command_results", [])]
    data["command_results"] = command_results
    return BaselineResult(**data)


def compare_baselines(before: BaselineResult, after: BaselineResult) -> Dict:
    comparison = {
        "passed": True,
        "regressions": [],
        "improvements": [],
    }

    if before.build_passed and not after.build_passed:
        comparison["regressions"].append("构建从通过变为失败")
    elif not before.build_passed and after.build_passed:
        comparison["improvements"].append("构建从失败变为通过")

    if after.tests_failed > before.tests_failed:
        comparison["regressions"].append(f"新增 {after.tests_failed - before.tests_failed} 个失败测试")
    elif after.tests_failed < before.tests_failed:
        comparison["improvements"].append(f"修复了 {before.tests_failed - after.tests_failed} 个失败测试")

    new_failing = sorted(set(after.failing_tests) - set(before.failing_tests))
    if new_failing:
        comparison["regressions"].append(f"新增失败测试: {', '.join(new_failing[:5])}")

    if after.lint_errors > before.lint_errors:
        comparison["regressions"].append(f"新增 {after.lint_errors - before.lint_errors} 个 Lint 错误")
    elif after.lint_errors < before.lint_errors:
        comparison["improvements"].append(f"修复了 {before.lint_errors - after.lint_errors} 个 Lint 错误")

    if after.type_errors > before.type_errors:
        comparison["regressions"].append(f"新增 {after.type_errors - before.type_errors} 个 Type 错误")
    elif after.type_errors < before.type_errors:
        comparison["improvements"].append(f"修复了 {before.type_errors - after.type_errors} 个 Type 错误")

    if before.coverage_percent is not None and after.coverage_percent is not None:
        if after.coverage_percent < before.coverage_percent:
            comparison["regressions"].append(
                f"覆盖率从 {before.coverage_percent:.1f}% 下降到 {after.coverage_percent:.1f}%"
            )
        elif after.coverage_percent > before.coverage_percent:
            comparison["improvements"].append(
                f"覆盖率从 {before.coverage_percent:.1f}% 提升到 {after.coverage_percent:.1f}%"
            )

    comparison["passed"] = not comparison["regressions"]
    return comparison


def save_comparison(cr_path: Path, comparison: Dict) -> Path:
    output_file = _comparison_file(cr_path)
    output_file.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 基线对比已保存: {output_file}")
    return output_file


def format_comparison_report(comparison: Dict) -> str:
    report = ["✅ 基线对比通过：无新增问题" if comparison["passed"] else "❌ 基线对比失败：发现质量退化", ""]
    if comparison["regressions"]:
        report.append("🚫 质量退化:")
        report.extend(f"  - {item}" for item in comparison["regressions"])
        report.append("")
    if comparison["improvements"]:
        report.append("✨ 质量改进:")
        report.extend(f"  - {item}" for item in comparison["improvements"])
        report.append("")
    return "\n".join(report)


def capture_baseline(cr_path: Path, phase: str) -> Tuple[Optional[BaselineResult], List[str], List[str]]:
    manifest, error = load_verification_manifest(cr_path)
    if error:
        return None, [error], []

    commands = _manifest_to_commands(manifest or {})
    if not commands:
        return None, ["verification-manifest.yml 未启用任何可执行验证命令"], []

    result = run_baseline(cr_path, manifest or {})
    save_baseline(cr_path, phase, result)
    return result, [], result.commands_run


def compare_after_baseline(cr_path: Path) -> Tuple[bool, List[str], List[str]]:
    before = load_baseline(cr_path, "before")
    if not before:
        return False, ["缺少 baseline-before，无法执行质量回归对比"], []

    after, errors, commands = capture_baseline(cr_path, "after")
    if errors or after is None:
        return False, errors, commands

    comparison = compare_baselines(before, after)
    save_comparison(cr_path, comparison)
    return comparison["passed"], comparison["regressions"], commands


def main():
    if len(sys.argv) < 3:
        print("用法:")
        print("  python baseline_comparison.py <CR目录> before")
        print("  python baseline_comparison.py <CR目录> after")
        sys.exit(1)

    cr_path = Path(sys.argv[1])
    phase = sys.argv[2]

    if phase == "before":
        result, errors, _ = capture_baseline(cr_path, "before")
        if errors:
            for item in errors:
                print(f"❌ {item}")
            sys.exit(1)
        assert result is not None
        print(f"\n构建: {'✅' if result.build_passed else '❌'}")
        print(f"测试: {result.tests_passed} passed, {result.tests_failed} failed")
        sys.exit(0)

    if phase == "after":
        passed, regressions, _ = compare_after_baseline(cr_path)
        comparison = json.loads(_comparison_file(cr_path).read_text(encoding="utf-8")) if _comparison_file(cr_path).exists() else {
            "passed": passed,
            "regressions": regressions,
            "improvements": [],
        }
        print("\n" + "=" * 60)
        print("基线对比")
        print("=" * 60)
        print(format_comparison_report(comparison))
        sys.exit(0 if passed else 1)

    print(f"❌ 未知 phase: {phase}")
    sys.exit(1)


if __name__ == "__main__":
    main()
