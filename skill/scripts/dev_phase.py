#!/usr/bin/env python3
"""
DevPhase — development handoff gate for DeliverHQ.

This script prepares the development phase but deliberately does not write code.
It validates PreDevGate status, checks or attempts worktree setup, emits the
paths/context a Dev Agent or human developer needs, and then stops the default
pipeline at a clear development handoff point.
"""


import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from cr_state import ensure_state, set_worktree_path, update_gate_from_result
from runtime_support import configure_console

DELIVERHQ_ROOT = Path(__file__).resolve().parent.parent
WORKTREE_SCRIPT = DELIVERHQ_ROOT / "scripts" / "worktree_manager.py"
VALID_LANES = {"fast", "standard", "high-risk"}

configure_console()


class Color:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'


def _is_git_repo(path: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode == 0


def _try_create_worktree(cr_id: str) -> Tuple[Optional[str], str]:
    if not WORKTREE_SCRIPT.exists():
        return None, "worktree_manager.py 不存在，跳过自动 worktree 创建"

    if not _is_git_repo(DELIVERHQ_ROOT):
        return None, "DeliverHQ 当前不在 git repo 内，无法自动创建 worktree；请在目标项目仓库中手动准备开发目录"

    result = subprocess.run(
        [sys.executable, str(WORKTREE_SCRIPT), "create", cr_id],
        cwd=str(DELIVERHQ_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip() or "worktree 创建失败"

    expected_path = DELIVERHQ_ROOT / ".claude" / "worktrees" / cr_id
    return str(expected_path.resolve()), "worktree 创建成功"


def prepare_dev_phase(cr_path: str, lane: Optional[str] = None) -> bool:
    cr_dir = Path(cr_path).resolve()
    state = ensure_state(cr_dir)
    lane = lane or state.lane

    print(f"{Color.BLUE}=== DevPhase 开发交接 ==={Color.END}")
    print(f"CR: {cr_dir}")
    print(f"lane: {lane}\n")

    blockers: List[str] = []
    warnings: List[str] = []
    commands_run = ["dev_phase.py"]

    if lane not in VALID_LANES:
        blockers.append(f"无效 lane: {lane}")

    pre_dev_status = state.gate_status.get("pre_dev")
    if pre_dev_status == "pass":
        print(f"{Color.BLUE}state.yml 标记 pre_dev=pass，仍重新运行 pre_dev_gate.py 以现实校验。{Color.END}")
    else:
        print(f"{Color.YELLOW}PreDevGate 未显示 PASS，运行 pre_dev_gate.py。{Color.END}")
    result = subprocess.run(
        [sys.executable, str(DELIVERHQ_ROOT / "scripts" / "pre_dev_gate.py"), cr_dir.name, "--lane", lane],
        cwd=str(DELIVERHQ_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace",
    )
    commands_run.append("pre_dev_gate.py")
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr)
        blockers.append("PreDevGate 未通过，不能进入开发阶段")
    else:
        state = ensure_state(cr_dir)

    worktree_path = state.worktree_path
    if worktree_path:
        if Path(worktree_path).exists():
            print(f"{Color.GREEN}✓ worktree 已存在: {worktree_path}{Color.END}")
        else:
            warnings.append(f"state.yml 中的 worktree_path 不存在: {worktree_path}")
            worktree_path = None

    if not worktree_path and lane in {"standard", "high-risk"} and not blockers:
        if os.environ.get("DELIVERHQ_SELFTEST", "0") == "1":
            message = "selftest 模式跳过自动 worktree 创建"
            warnings.append(message)
            print(f"{Color.BLUE}ℹ {message}{Color.END}")
            created_path = None
        else:
            created_path, message = _try_create_worktree(cr_dir.name)
            commands_run.append("worktree_manager.py create")
        if created_path:
            worktree_path = created_path
            set_worktree_path(cr_dir, worktree_path)
            print(f"{Color.GREEN}✓ {message}: {worktree_path}{Color.END}")
        else:
            warnings.append(message)
            print(f"{Color.YELLOW}⚠ {message}{Color.END}")

    dev_context = {
        "cr_id": cr_dir.name,
        "cr_path": str(cr_dir),
        "lane": lane,
        "worktree_path": worktree_path,
        "must_read_files": [
            "request.md",
            "acceptance-spec.md",
            "implementation-plan.md",
            "context-summary.md",
            "traceability.yml",
            "human-decisions.md",
        ],
        "next_agent_instructions": [
            "在 worktree_path 或目标项目仓库中实现代码；本脚本不会自动写代码。",
            "实现完成后更新 changed_files / traceability，并运行 ReviewGate。",
            "不要跳过 verification-manifest.yml 中的真实验证命令。",
        ],
    }

    evidence_dir = cr_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / "dev-phase-result.json"
    evidence_path.write_text(json.dumps(dev_context, ensure_ascii=False, indent=2), encoding="utf-8")

    if blockers:
        print(f"\n{Color.RED}❌ BLOCKED - 不能交接开发{Color.END}")
        for idx, blocker in enumerate(blockers, 1):
            print(f"  {idx}. {blocker}")
        update_gate_from_result(
            cr_dir,
            "dev",
            False,
            blockers=blockers,
            state_after_pass="dev",
            current_phase="dev",
            current_owner="dev-agent",
            next_required_gate="dev",
            warnings=warnings,
            commands_run=commands_run,
            artifacts=["evidence/dev-phase-result.json"],
            next_action="修复 PreDevGate/开发环境阻断项后重新运行 DevPhase",
            metadata=dev_context,
        )
        return False

    print(f"\n{Color.GREEN}✅ DEV HANDOFF READY{Color.END}")
    print("本阶段只完成开发交接，不自动写代码；默认 pipeline 会在这里停止。")
    print(f"上下文输出: {evidence_path}")
    if worktree_path:
        print(f"开发目录: {worktree_path}")
    if warnings:
        print(f"\n{Color.YELLOW}Warnings:{Color.END}")
        for idx, warning in enumerate(warnings, 1):
            print(f"  {idx}. {warning}")

    update_gate_from_result(
        cr_dir,
        "dev",
        True,
        blockers=[],
        state_after_pass="dev",
        current_phase="dev",
        current_owner="dev-agent",
        next_required_gate="review",
        warnings=warnings,
        commands_run=commands_run,
        artifacts=["evidence/dev-phase-result.json"],
        next_action="人工/Dev Agent 完成代码实现后运行 ReviewGate",
        metadata=dev_context,
    )
    return True


def main():
    parser = argparse.ArgumentParser(description="Prepare DeliverHQ development handoff")
    parser.add_argument("cr_path", help="CR directory path")
    parser.add_argument("--lane", choices=sorted(VALID_LANES), help="override state.yml lane")
    args = parser.parse_args()

    passed = prepare_dev_phase(args.cr_path, lane=args.lane)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
