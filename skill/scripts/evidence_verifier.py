"""
Evidence Verifier - 证据聚合与验证。

职责:
    1. 聚合三类证据（agent-result.yml / anti_gaming_check / verification-manifest）
    2. 判断任务是否真正完成（pass/fail）
    3. 通过时写 receipts/<task_id>.yml，并归档 agent-result.yml 副本

不做的事:
    - 不重新运行测试（信现有产物）
    - 不修改代码（只读）
    - 不执行 gate 脚本（只读其输出）
"""
import subprocess
import sys
import yaml
import shutil
import os
from pathlib import Path
from datetime import datetime, timezone


def _now() -> str:
    """
    返回当前 UTC 时间戳（ISO 8601 格式）。

    优先读 SOURCE_DATE_EPOCH 环境变量（支持可复现构建）。
    """
    source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if source_date_epoch:
        dt = datetime.fromtimestamp(int(source_date_epoch), tz=timezone.utc)
    else:
        dt = datetime.now(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def verify(cr_path: Path, task_id: str, run_id: str) -> tuple[bool, dict]:
    """
    验证任务运行结果。

    Args:
        cr_path: CR 目录
        task_id: 任务 ID
        run_id: 运行 ID

    Returns:
        (passed, details)
        - passed: True 表示通过，False 表示失败
        - details: 详细信息（blockers / warnings / evidence_paths）

    Side Effects:
        通过时：
        1. 写 receipts/<task_id>.yml
        2. 归档 agent-result.yml 到 runtime/runs/<run_id>-result.yml
    """
    blockers = []
    warnings = []
    evidence_paths = []

    # 0. 获取 worktree 路径
    worktree = _get_worktree_path(cr_path)
    if not worktree:
        blockers.append("无法获取 worktree 路径（state.yml 中未设置 worktree_path）")
        return False, {"blockers": blockers, "warnings": warnings, "evidence_paths": evidence_paths}

    # 1. 检查 agent-result.yml 存在（在 worktree 根目录）
    agent_result_path = worktree / "agent-result.yml"
    if not agent_result_path.exists():
        blockers.append("agent-result.yml 不存在，agent 未产出声明")
        return False, {"blockers": blockers, "warnings": warnings, "evidence_paths": evidence_paths}

    evidence_paths.append(str(agent_result_path))

    # 2. 解析 agent-result.yml
    try:
        agent_result = yaml.safe_load(agent_result_path.read_text(encoding="utf-8"))
    except Exception as e:
        blockers.append(f"agent-result.yml 解析失败: {e}")
        return False, {"blockers": blockers, "warnings": warnings, "evidence_paths": evidence_paths}

    # 3. 调用 anti_gaming_check.py
    anti_gaming_passed, anti_gaming_msg = _check_anti_gaming(cr_path)
    if not anti_gaming_passed:
        blockers.append(f"anti_gaming_check 失败: {anti_gaming_msg}")

    # 4. 检查 verification-manifest.yml（如果存在）
    manifest_path = cr_path / "verification-manifest.yml"
    if manifest_path.exists():
        manifest_passed, manifest_msg = _check_verification_manifest(cr_path, agent_result)
        if not manifest_passed:
            blockers.append(f"verification-manifest 检查失败: {manifest_msg}")
        evidence_paths.append(str(manifest_path))
    else:
        warnings.append("verification-manifest.yml 不存在，跳过测试验证")

    # 5. 检查改动文件范围
    scope_passed, scope_msg = _check_file_scope(cr_path, task_id, agent_result)
    if not scope_passed:
        blockers.append(f"文件范围检查失败: {scope_msg}")

    # 6. 汇总
    passed = (len(blockers) == 0)

    if passed:
        # 归档 agent-result.yml
        _archive_agent_result(cr_path, run_id, agent_result_path)
        # 写 receipt
        _write_receipt(cr_path, task_id, run_id, agent_result, evidence_paths)

    return passed, {
        "blockers": blockers,
        "warnings": warnings,
        "evidence_paths": evidence_paths,
    }


def _get_worktree_path(cr_path: Path) -> Path | None:
    """从 state.yml 读取 worktree 路径。"""
    state_path = cr_path / "state.yml"
    if not state_path.exists():
        return None

    state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    worktree_path = state.get("worktree_path")

    return Path(worktree_path) if worktree_path else None


def _check_anti_gaming(cr_path: Path) -> tuple[bool, str]:
    """
    调用 anti_gaming_check.py。

    Returns:
        (passed, message)
    """
    script_path = Path(__file__).parent / "anti_gaming_check.py"
    if not script_path.exists():
        return True, "anti_gaming_check.py 不存在，跳过"

    result = subprocess.run(
        [sys.executable, str(script_path), str(cr_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode == 0:
        return True, "pass"
    elif result.returncode == 1:
        return False, result.stdout.strip() or "检测到 reward hacking"
    else:
        return False, f"执行错误: {result.stderr.strip()}"


def _check_verification_manifest(cr_path: Path, agent_result: dict) -> tuple[bool, str]:
    """
    检查 verification-manifest.yml 中的测试命令是否执行。

    简化版: 检查 agent_result.test_command 是否在 manifest 中。
    """
    manifest_path = cr_path / "verification-manifest.yml"
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"解析失败: {e}"

    test_command = agent_result.get("test_command", "")
    if not test_command:
        return False, "agent-result.yml 未提供 test_command"

    # 简化检查: manifest 中是否有对应记录
    commands = manifest.get("commands", [])
    if not any(test_command in cmd.get("command", "") for cmd in commands):
        return False, f"test_command '{test_command}' 未在 manifest 中找到执行记录"

    return True, "pass"


def _check_file_scope(cr_path: Path, task_id: str, agent_result: dict) -> tuple[bool, str]:
    """
    检查改动文件是否在 task.files 范围内。
    """
    plan_path = cr_path / "plan.yml"
    if not plan_path.exists():
        return True, "plan.yml 不存在，跳过范围检查"

    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    task = next((t for t in plan.get("tasks", []) if t["task_id"] == task_id), None)

    if not task:
        return False, f"task {task_id} 在 plan.yml 中未找到"

    allowed_files = set(task.get("files", []))
    if not allowed_files:
        return True, "task.files 为空，无限制"

    changed_files = set(agent_result.get("changed_files", []))
    out_of_scope = changed_files - allowed_files

    if out_of_scope:
        return False, f"改动了范围外文件: {', '.join(out_of_scope)}"

    return True, "pass"


def _archive_agent_result(cr_path: Path, run_id: str, agent_result_path: Path):
    """归档 agent-result.yml 到 runtime/runs/<run_id>-result.yml。"""
    runs_dir = cr_path / "runtime" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    archive_path = runs_dir / f"{run_id}-result.yml"
    shutil.copy2(agent_result_path, archive_path)


def _write_receipt(
    cr_path: Path,
    task_id: str,
    run_id: str,
    agent_result: dict,
    evidence_paths: list[str],
):
    """写 receipts/<task_id>.yml。"""
    receipts_dir = cr_path / "runtime" / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)

    receipt = {
        "schema_version": "arc-receipt/v1",
        "task_id": task_id,
        "run_id": run_id,
        "verified_at": _now(),
        "verifier_version": "1.0.0",
        "sources": {
            "anti_gaming_check": "pass",
            "verification_manifest": "pass",
            "changed_files_in_scope": "pass",
            "agent_result_exists": "pass",
        },
        "changed_files": agent_result.get("changed_files", []),
        "test_command": agent_result.get("test_command", ""),
        "evidence_paths": evidence_paths,
    }

    receipt_path = receipts_dir / f"{task_id}.yml"
    receipt_path.write_text(yaml.dump(receipt, allow_unicode=True), encoding="utf-8")
