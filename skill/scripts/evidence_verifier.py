"""Fail-closed verification of an agent run.

The verifier deliberately treats the agent's report as a claim.  The claim is
accepted only when the plan, anti-gaming evidence, manifest command and the
actual git worktree all agree.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from common import load_yaml


def _now() -> str:
    value = os.environ.get("SOURCE_DATE_EPOCH")
    dt = datetime.fromtimestamp(int(value), tz=timezone.utc) if value else datetime.now(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _result(ok: bool, blockers: list[str], warnings: list[str], paths: list[str], **extra: Any):
    data = {"blockers": blockers, "warnings": warnings, "evidence_paths": paths}
    data.update(extra)
    return ok, data


def verify(cr_path: Path, task_id: str, run_id: str) -> tuple[bool, dict]:
    cr_path = Path(cr_path)
    blockers: list[str] = []
    warnings: list[str] = []
    paths: list[str] = []
    worktree = _get_worktree_path(cr_path)
    if not worktree:
        blockers.append("无法获取 worktree 路径（state.yml 中未设置 worktree_path）")
        _, details = _result(False, blockers, warnings, paths)
        _record_run(cr_path, run_id, details)
        return False, details

    result_path = worktree / "agent-result.yml"
    if not result_path.exists():
        blockers.append("agent-result.yml 不存在，agent 未产出声明")
        _, details = _result(False, blockers, warnings, paths)
        _record_run(cr_path, run_id, details)
        return False, details
    paths.append(str(result_path))
    try:
        agent_result = load_yaml(result_path)
    except Exception as exc:
        blockers.append(f"agent-result.yml 解析失败: {exc}")
        _, details = _result(False, blockers, warnings, paths)
        _record_run(cr_path, run_id, details)
        return False, details
    schema_errors = _validate_agent_result(agent_result, task_id)
    blockers.extend(schema_errors)

    # These are required evidence, not optional hints.
    plan_path = cr_path / "plan.yml"
    manifest_path = cr_path / "verification-manifest.yml"
    anti_path = cr_path / "evidence" / "anti-gaming-result.json"
    if not plan_path.exists(): blockers.append("缺少 plan.yml")
    else: paths.append(str(plan_path))
    if not manifest_path.exists(): blockers.append("缺少 verification-manifest.yml")
    else: paths.append(str(manifest_path))
    if not anti_path.exists(): blockers.append("缺少 anti-gaming 证据 evidence/anti-gaming-result.json")
    else: paths.append(str(anti_path))

    if plan_path.exists():
        ok, msg = _check_file_scope(cr_path, task_id, agent_result if isinstance(agent_result, dict) else {})
        if not ok: blockers.append(f"文件范围检查失败: {msg}")
    anti_ok, anti_msg = _check_anti_gaming(cr_path)
    if not anti_ok: blockers.append(f"anti_gaming_check 失败: {anti_msg}")

    command_ok = False
    command_record: dict[str, Any] = {}
    if manifest_path.exists() and isinstance(agent_result, dict):
        command_ok, command_msg, command_record = _check_verification_manifest(cr_path, agent_result, worktree)
        if not command_ok: blockers.append(f"verification-manifest 检查失败: {command_msg}")

    diff_ok, diff_msg, actual_files = _check_git_diff(worktree, agent_result if isinstance(agent_result, dict) else {})
    if not diff_ok: blockers.append(f"真实 git diff 检查失败: {diff_msg}")

    passed = not blockers
    _, details = _result(passed, blockers, warnings, paths, actual_changed_files=sorted(actual_files), command=command_record)
    _record_run(cr_path, run_id, details, agent_result=agent_result)
    if passed:
        _archive_agent_result(cr_path, run_id, result_path)
        _write_receipt(cr_path, task_id, run_id, agent_result, paths, details)
    return passed, details


def _validate_agent_result(value: Any, task_id: str) -> list[str]:
    if not isinstance(value, dict): return ["agent-result.yml 必须是 YAML 对象"]
    errors = []
    if value.get("task_id") != task_id: errors.append(f"agent-result task_id 不匹配: {value.get('task_id')!r}")
    if value.get("status") not in {"done", "success", "passed", "pass"}: errors.append("agent-result status 必须为 done/success/passed")
    if not isinstance(value.get("changed_files"), list) or not all(isinstance(x, str) and x for x in value.get("changed_files", [])): errors.append("agent-result changed_files 必须是字符串数组")
    if not isinstance(value.get("test_command"), str) or not value.get("test_command").strip(): errors.append("agent-result test_command 必须为非空字符串")
    return errors


def _get_worktree_path(cr_path: Path) -> Path | None:
    state_path = cr_path / "state.yml"
    if not state_path.exists(): return None
    try: state = load_yaml(state_path)
    except Exception: return None
    value = state.get("worktree_path")
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else cr_path / path


def _check_anti_gaming(cr_path: Path) -> tuple[bool, str]:
    script = Path(__file__).parent / "anti_gaming_check.py"
    if not script.exists(): return False, "anti_gaming_check.py 不存在"
    try:
        result = subprocess.run([sys.executable, str(script), str(cr_path)], capture_output=True, text=True, timeout=60)
    except Exception as exc: return False, str(exc)
    return (True, "pass") if result.returncode == 0 else (False, result.stdout.strip() or result.stderr.strip() or "检查失败")


def _manifest_commands(manifest: Any) -> list[dict[str, Any]]:
    found = []
    def walk(node: Any):
        if isinstance(node, dict):
            if isinstance(node.get("command"), str): found.append(node)
            for value in node.values(): walk(value)
        elif isinstance(node, list):
            for value in node: walk(value)
    walk(manifest)
    return found


def _check_verification_manifest(cr_path: Path, agent_result: dict, worktree: Path | None = None) -> tuple[bool, str, dict]:
    try: manifest = load_yaml(cr_path / "verification-manifest.yml")
    except Exception as exc: return False, f"解析失败: {exc}", {}
    worktree = worktree or _get_worktree_path(cr_path)
    if not worktree: return False, "缺少 worktree_path", {}
    command = agent_result.get("test_command", "").strip()
    entries = [e for e in _manifest_commands(manifest) if e.get("enabled", True) and e.get("command") == command]
    if not entries: return False, f"test_command '{command}' 未在 manifest 中声明", {}
    entry = entries[0]
    cwd = worktree / str(entry.get("working_dir", "."))
    try:
        argv = shlex.split(command, posix=True)
        if not argv: return False, "manifest command 为空", {}
        proc = subprocess.run(argv, cwd=str(cwd), shell=False, capture_output=True, text=True, timeout=int(entry.get("timeout", 600)))
    except Exception as exc: return False, f"命令执行失败: {exc}", {}
    record = {"command": command, "returncode": proc.returncode, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-4000:]}
    return (True, "pass", record) if proc.returncode == 0 else (False, f"命令返回 {proc.returncode}", record)


def _git_files(worktree: Path) -> set[str] | None:
    try:
        diff = subprocess.run(["git", "diff", "--name-only", "HEAD"], cwd=str(worktree), capture_output=True, text=True, timeout=30)
        if diff.returncode != 0: return None
        files = {line.strip().replace("\\", "/") for line in diff.stdout.splitlines() if line.strip()}
        # git diff does not include untracked files; include them from porcelain.
        status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=str(worktree), capture_output=True, text=True, timeout=30)
        if status.returncode != 0:
            return None
        for line in status.stdout.splitlines():
            raw = line[3:] if len(line) > 3 else ""
            if " -> " in raw: raw = raw.split(" -> ", 1)[1]
            if raw.strip(): files.add(raw.strip().replace("\\", "/"))
        files.discard("agent-result.yml")
        return files
    except Exception: return None


def _check_git_diff(worktree: Path, agent_result: dict) -> tuple[bool, str, set[str]]:
    actual = _git_files(worktree)
    if actual is None: return False, "worktree 不是可检查的 git 仓库", set()
    declared = {str(x).replace("\\", "/") for x in agent_result.get("changed_files", [])}
    missing = declared - actual
    extra = actual - declared
    if missing or extra: return False, f"声明与实际不一致 (missing={sorted(missing)}, extra={sorted(extra)})", actual
    return True, "pass", actual


def _record_run(cr_path: Path, run_id: str, details: dict, agent_result: Any = None):
    input_blob = json.dumps(agent_result if agent_result is not None else {}, ensure_ascii=False, sort_keys=True)
    baseline = ""
    try:
        wt = _get_worktree_path(cr_path)
        if wt:
            baseline = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(wt), capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        pass
    output_blob = json.dumps(details, ensure_ascii=False, sort_keys=True)
    payload = {"schema_version": "arc-run/v1", "run_id": run_id, "recorded_at": _now(), "details": details,
               "input_hash": hashlib.sha256(input_blob.encode()).hexdigest(),
               "baseline_hash": hashlib.sha256(baseline.encode()).hexdigest() if baseline else None,
               "output_hash": hashlib.sha256(output_blob.encode()).hexdigest()}
    if agent_result is not None: payload["agent_result"] = agent_result
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    path = cr_path / "runtime" / "runs" / f"{run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _archive_agent_result(cr_path: Path, run_id: str, path: Path):
    target = cr_path / "runtime" / "runs" / f"{run_id}-result.yml"
    target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, target)


def _write_receipt(cr_path: Path, task_id: str, run_id: str, agent_result: dict, paths: list[str], details: dict):
    receipt = {"schema_version": "arc-receipt/v1", "task_id": task_id, "run_id": run_id, "verified_at": _now(), "verifier_version": "2.0.0", "sources": {"anti_gaming_check": "pass", "verification_manifest": "pass", "changed_files_in_scope": "pass", "agent_result_exists": "pass", "git_diff": "pass"}, "changed_files": agent_result.get("changed_files", []), "test_command": agent_result.get("test_command", ""), "evidence_paths": paths, "command": details.get("command", {})}
    target = cr_path / "runtime" / "receipts" / f"{task_id}.yml"; target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(receipt, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _check_file_scope(cr_path: Path, task_id: str, agent_result: dict) -> tuple[bool, str]:
    try: plan = load_yaml(cr_path / "plan.yml")
    except Exception as exc: return False, f"plan 解析失败: {exc}"
    task = next((t for t in plan.get("tasks", []) if isinstance(t, dict) and t.get("task_id") == task_id), None)
    if not task: return False, f"task {task_id} 在 plan.yml 中未找到"
    allowed = set(task.get("files", []) or [])
    return (True, "pass") if not allowed or set(agent_result.get("changed_files", [])) <= allowed else (False, f"改动了范围外文件: {', '.join(sorted(set(agent_result.get('changed_files', [])) - allowed))}")
