#!/usr/bin/env python3
"""PermissionGate - 权限边界检查（最小可用版）"""


import fnmatch
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import yaml

from cr_state import ensure_state, update_gate_from_result
from runtime_support import configure_console

DELIVERHQ_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = DELIVERHQ_ROOT.parent
configure_console()


def _load_dir_graph():
    graph_path = DELIVERHQ_ROOT / "dir-graph.yaml"
    if not graph_path.exists():
        return []

    data = {}
    for doc in yaml.safe_load_all(graph_path.read_text(encoding="utf-8")):
        if isinstance(doc, dict):
            data.update(doc)
    protected_paths = data.get("protected_paths", []) or []
    normalized = []
    for pattern in protected_paths:
        if pattern.startswith("../"):
            normalized.append(pattern[3:])
        else:
            normalized.append(pattern)
    return normalized


def _load_exceptions(cr_path: Path):
    exceptions_path = cr_path / "exceptions.yml"
    if not exceptions_path.exists():
        return []

    data = yaml.safe_load(exceptions_path.read_text(encoding="utf-8")) or {}
    return data.get("exceptions", []) or []


class NoGitRepoError(RuntimeError):
    """目标目录不是 git 仓库（良性环境，非真实错误）。"""


def _git_changed_files():
    result = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), "status", "--porcelain"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=10,
    )

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        if "not a git repository" in stderr.lower():
            raise NoGitRepoError(stderr or "not a git repository")
        raise RuntimeError(stderr or "git status failed")

    files = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ")[-1].strip()
        files.append(path.replace("\\", "/"))
    return files


def _is_protected(file_path: str, protected_patterns):
    for pattern in protected_patterns:
        if fnmatch.fnmatch(file_path, pattern):
            return True
    return False


def _has_gate_override(exceptions, gate_name: str):
    for item in exceptions:
        if not isinstance(item, dict):
            continue
        gate_override = item.get("gate_override") or item
        if not isinstance(gate_override, dict):
            continue
        if gate_override.get("gate") == gate_name and gate_override.get("approved_by"):
            return True
    return False


def check_permission_gate(cr_path, lane: Optional[str] = None):
    """检查权限边界 - 最小可用实现"""

    cr_path = Path(cr_path)
    state = ensure_state(cr_path)
    effective_lane = lane or state.lane
    print("=" * 50)
    print("  PermissionGate - 权限边界检查")
    print("=" * 50)
    print()
    print(f"lane: {effective_lane}")

    protected_patterns = _load_dir_graph()
    exceptions = _load_exceptions(cr_path)

    if os.environ.get("DELIVERHQ_SELFTEST", "0") == "1":
        print("ℹ️  selftest 模式跳过 git 工作区权限核对")
        changed_files = []
    else:
        try:
            changed_files = _git_changed_files()
        except NoGitRepoError as exc:
            print("⚠️  PASS WITH WARNING - 目标目录不是 git 仓库，跳过受保护路径核对")
            print(f"   {exc}")
            warning_msg = "非 git 仓库，PermissionGate 跳过 git diff 核对（建议在目标项目仓库内运行以启用权限边界检查）"
            update_gate_from_result(
                cr_path,
                "permission",
                True,
                blockers=[],
                state_after_pass="dev",
                current_phase="dev",
                current_owner="dev-agent",
                next_required_gate="pre_dev",
                warnings=[warning_msg],
                commands_run=["git status --porcelain"],
                next_action="如需启用权限边界检查，请在目标项目的 git 仓库内运行",
            )
            return True, []
        except Exception as exc:
            print("❌ BLOCKED - 无法读取 Git 变更")
            print(f"   {exc}")
            update_gate_from_result(
                cr_path,
                "permission",
                False,
                blockers=["无法读取 Git 变更"],
                state_after_pass="blocked",
                current_phase="request",
                current_owner="human",
                next_required_gate="pre_dev",
                commands_run=["git status --porcelain"],
                next_action="修复 Git 状态读取问题后重新运行 PermissionGate",
            )
            return False, ["PermissionGate 无法读取 Git 变更"]
    protected_hits = [path for path in changed_files if _is_protected(path, protected_patterns)]

    print(f"变更文件: {len(changed_files)}")
    print(f"受保护路径匹配: {len(protected_hits)}")

    if protected_hits:
        if effective_lane == "high-risk" and _has_gate_override(exceptions, "PermissionGate"):
            print("✅ PASS - 受保护路径已获得例外审批")
            update_gate_from_result(
                cr_path,
                "permission",
                True,
                blockers=[],
                state_after_pass="dev",
                current_phase="dev",
                current_owner="dev-agent",
                next_required_gate="pre_dev",
                commands_run=["git status --porcelain"],
                artifacts=["exceptions.yml"],
                next_action="继续执行 PreDevGate",
            )
            return True, []

        print("❌ BLOCKED - 发现未授权的受保护路径变更")
        for path in protected_hits[:10]:
            print(f"   - {path}")
        if effective_lane == "high-risk":
            blockers = [f"high-risk 触及受保护路径，需 human approval + exceptions.yml: {', '.join(protected_hits[:5])}"]
            next_action = "补充 exceptions.yml 中的 PermissionGate 审批并重新运行"
        else:
            blockers = [f"{effective_lane} lane 不允许改动 protected_paths: {', '.join(protected_hits[:5])}"]
            next_action = "移除受保护路径改动或切换到 high-risk + human approval"
        update_gate_from_result(
            cr_path,
            "permission",
            False,
            blockers=blockers,
            state_after_pass="blocked",
            current_phase="request",
            current_owner="human",
            next_required_gate="pre_dev",
            commands_run=["git status --porcelain"],
            next_action=next_action,
            metadata={"protected_hits": protected_hits, "lane": effective_lane},
        )
        return False, blockers

    print("✅ PASS - 未触及受保护路径")
    update_gate_from_result(
        cr_path,
        "permission",
        True,
        blockers=[],
        state_after_pass="dev",
        current_phase="dev",
        current_owner="dev-agent",
        next_required_gate="pre_dev",
        commands_run=["git status --porcelain"],
        next_action="继续执行 PreDevGate",
        metadata={"protected_hits": [], "lane": effective_lane},
    )
    return True, []


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python permissiongate.py <CR目录>")
        print("      python permissiongate.py <CR目录> --skip (跳过检查)")
        sys.exit(1)

    if "--skip" in sys.argv or "--skip-permission-gate" in sys.argv:
        print("⚠️  PermissionGate 已跳过（用户显式允许）")
        sys.exit(0)

    passed, blockers = check_permission_gate(sys.argv[1])
    sys.exit(0 if passed else 1)
