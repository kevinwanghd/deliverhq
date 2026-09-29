"""
Recovery Manager - 失败处理与恢复。

职责:
    1. 分类失败原因
    2. 委托 retry_guard.py 判断是否可重试
    3. 在特定失败类型时执行 git stash
    4. 转换任务状态（RECOVERABLE → READY 或 NEEDS_HUMAN）
"""
from enum import Enum
import subprocess
import sys
import yaml
from pathlib import Path
import json
import hashlib
from common import load_yaml, now_iso


class RecoveryClass(Enum):
    """失败分类（传递给 retry_guard）。"""
    TIMEOUT = "arc:timeout"
    NO_EVIDENCE = "arc:no_evidence"
    TEST_FAILURE = "arc:test_failure"
    ANTI_GAMING = "arc:anti_gaming"
    OUT_OF_SCOPE = "arc:out_of_scope"
    BUDGET_EXHAUSTED = "arc:budget_exhausted"
    UNKNOWN = "arc:unknown"


def record_retry(cr_path: Path, task_id: str, failure_details: dict) -> tuple[bool, str]:
    """Record one failed attempt in the retry ledger; orchestration owns when to call this."""
    recovery_class = _classify_failure(failure_details)
    attempt = _count_prior_attempts(cr_path, f"arc:{task_id}", recovery_class.value) + 1
    hypothesis = _retry_hypothesis(recovery_class, failure_details, attempt)
    script_path = Path(__file__).parent / "retry_guard.py"
    result = subprocess.run(
        [sys.executable, str(script_path), str(cr_path), "record",
         "--gate", f"arc:{task_id}", "--blocker", recovery_class.value,
         "--hypothesis", hypothesis],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    if result.returncode == 0:
        return True, result.stdout.strip() or "retry recorded"
    return False, result.stdout.strip() or result.stderr.strip() or "retry limit reached"


def handle(
    cr_path: Path,
    task_id: str,
    run_id: str,
    failure_details: dict,
) -> tuple[str, str]:
    """
    处理失败，返回下一状态。

    Args:
        cr_path: CR 目录
        task_id: 任务 ID
        run_id: 运行 ID
        failure_details: 失败详情（来自 AgentRunResult 或 evidence_verifier）

    Returns:
        (next_state, reason)
        - next_state: "READY" / "NEEDS_HUMAN"
        - reason: 状态转换原因
    """
    # 1. 分类失败
    recovery_class = _classify_failure(failure_details)

    # 2. 生成假设
    hypothesis = _generate_hypothesis(recovery_class, failure_details)

    # 3. 只读查询 retry_guard；恢复管理器绝不 record（避免重复计数）
    can_retry, retry_reason = _call_retry_guard(cr_path, task_id, recovery_class, hypothesis)

    if not can_retry:
        next_state = "NEEDS_HUMAN"
        _persist_recovery(cr_path, task_id, run_id, recovery_class, hypothesis, next_state, retry_reason, failure_details)
        return next_state, retry_reason

    # 4. git stash（仅特定失败类型）
    stash_note = ""
    if recovery_class in (RecoveryClass.NO_EVIDENCE, RecoveryClass.BUDGET_EXHAUSTED):
        stashed, stash_msg = _git_stash(cr_path, run_id)
        if not stashed:
            # 现场未保存：重试会在残留产出上运行，证据基线失真且现场可能被覆盖
            next_state = "NEEDS_HUMAN"
            reason = f"现场保存失败，需人工清理 worktree 后再重试: {stash_msg}"
            _persist_recovery(cr_path, task_id, run_id, recovery_class, hypothesis, next_state, reason, failure_details)
            return next_state, reason
        stash_note = f"；{stash_msg}"

    next_state = "READY"
    reason = f"可重试（{hypothesis}）{stash_note}"
    _persist_recovery(cr_path, task_id, run_id, recovery_class, hypothesis, next_state, reason, failure_details)
    return next_state, reason


def _classify_failure(failure_details: dict) -> RecoveryClass:
    """
    根据失败详情分类。

    Args:
        failure_details: 可能包含:
            - exit_kind: "timeout" / "error" / "no_evidence"
            - blockers: ["anti_gaming_check 失败", ...]
    """
    exit_kind = failure_details.get("exit_kind")
    blockers = failure_details.get("blockers", [])

    if exit_kind == "timeout":
        return RecoveryClass.TIMEOUT
    elif exit_kind == "error" and not blockers:
        # agent 进程错误但无具体 blocker
        return RecoveryClass.UNKNOWN

    # 从 blockers 推断
    for blocker in blockers:
        blocker_lower = blocker.lower()
        if "agent-result.yml 不存在" in blocker or "未产出" in blocker:
            return RecoveryClass.NO_EVIDENCE
        elif "anti_gaming" in blocker_lower:
            return RecoveryClass.ANTI_GAMING
        elif "范围外文件" in blocker or "out of scope" in blocker_lower:
            return RecoveryClass.OUT_OF_SCOPE
        elif "test" in blocker_lower or "verification" in blocker_lower:
            return RecoveryClass.TEST_FAILURE

    return RecoveryClass.UNKNOWN


def _generate_hypothesis(recovery_class: RecoveryClass, failure_details: dict) -> str:
    """生成修复假设（传递给 retry_guard）。"""
    hypotheses = {
        RecoveryClass.TIMEOUT: "增加超时时间或减少任务范围",
        RecoveryClass.NO_EVIDENCE: "agent 未产出 agent-result.yml，可能命令格式错误",
        RecoveryClass.TEST_FAILURE: "测试失败，需修复代码或调整测试",
        RecoveryClass.ANTI_GAMING: "检测到作弊行为（删测试/改门禁），需重新实现",
        RecoveryClass.OUT_OF_SCOPE: "改动了范围外文件，需限制修改范围",
        RecoveryClass.BUDGET_EXHAUSTED: "session pack 超预算，需拆分任务",
        RecoveryClass.UNKNOWN: "未知失败，需人工检查",
    }
    return hypotheses.get(recovery_class, "未知失败")


def _count_prior_attempts(cr_path: Path, gate: str, blocker: str) -> int:
    """统计账本中同 gate + 同 blocker（即同一签名）已记录的次数。"""
    ledger = load_yaml(cr_path / "evidence" / "retry-ledger.yml")
    entries = ledger.get("entries") or []
    return sum(1 for e in entries if isinstance(e, dict) and e.get("gate") == gate and e.get("blocker") == blocker)


def _retry_hypothesis(recovery_class: RecoveryClass, failure_details: dict, attempt: int) -> str:
    """带尝试序号与失败摘要的假设：未达上限的合法重试不会因类别相同被判为原地重复。"""
    blockers = failure_details.get("blockers") or []
    detail = f"exit_kind={failure_details.get('exit_kind')}"
    if blockers:
        detail += f"; blocker={str(blockers[0])[:80]}"
    digest = hashlib.sha256(
        json.dumps(failure_details, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:8]
    base = _generate_hypothesis(recovery_class, failure_details)
    return f"{base}（第 {attempt} 次尝试; {detail}; details={digest}）"


def _call_retry_guard(
    cr_path: Path,
    task_id: str,
    recovery_class: RecoveryClass,
    hypothesis: str,
) -> tuple[bool, str]:
    """
    调用 retry_guard.py record 判断是否可重试。

    Returns:
        (can_retry, reason)
    """
    script_path = Path(__file__).parent / "retry_guard.py"

    gate_label = f"arc:{task_id}"  # 区分普通 Gate
    blocker_summary = f"{recovery_class.value} - {hypothesis}"

    result = subprocess.run(
        [sys.executable, str(script_path), str(cr_path), "status"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    if result.returncode != 0:
        return False, f"retry_guard status 执行错误: {(result.stderr or result.stdout or '').strip()}"
    # 只看本任务签名（arc:{task_id}::...）的行，其他任务/Gate 耗尽不影响本任务
    prefix = f"{gate_label}::"
    for line in (result.stdout or "").splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix) and "[needs_human]" in stripped:
            return False, f"重试次数耗尽（{blocker_summary}）: {stripped}"
    return True, "retry_guard status: can_retry"


def _persist_recovery(cr_path: Path, task_id: str, run_id: str, recovery_class: RecoveryClass,
                      hypothesis: str, next_state: str, reason: str, failure_details: dict):
    """Persist a tamper-evident recovery package and state, without retry writes."""
    package = {
        "schema_version": "arc-recovery/v1", "task_id": task_id, "run_id": run_id,
        "recorded_at": now_iso(),
        "recovery_class": recovery_class.value, "hypothesis": hypothesis,
        "next_state": next_state, "reason": reason, "failure_details": failure_details,
    }
    canonical = json.dumps(package, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    package["sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    root = cr_path / "runtime" / "recovery"
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{run_id}.json").write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    state = {"schema_version": "arc-recovery-state/v1", "task_id": task_id, "run_id": run_id,
             "state": next_state, "recovery_class": recovery_class.value, "reason": reason,
             "updated_at": package["recorded_at"], "sha256": package["sha256"]}
    (root / "state.yml").write_text(yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _git_stash(cr_path: Path, run_id: str):
    """
    执行 git stash（保留失败运行的现场供人工检查）。

    仅在以下情况调用:
        - NO_EVIDENCE（agent 没产出任何东西，工作树可能脏）
        - BUDGET_EXHAUSTED（session pack 生成失败前可能有残留）

    Returns:
        (ok, message)；git 失败/超时时 ok=False，不再静默当作成功。
    """
    worktree_path = _get_worktree_path(cr_path)
    if not worktree_path:
        return True, "无 worktree，跳过 stash"

    try:
        # 检查是否有改动
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        if result.returncode != 0:
            return False, f"git status 失败: {result.stderr.strip()}"
        if not result.stdout.strip():
            return True, "无改动，跳过 stash"

        # 执行 stash
        stash_msg = f"arc-recovery:{run_id}"
        stash = subprocess.run(
            ["git", "stash", "push", "-m", stash_msg],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, f"git stash 执行失败: {exc}"
    if stash.returncode != 0:
        return False, f"git stash 失败: {stash.stderr.strip() or stash.stdout.strip()}"
    return True, f"已 stash 现场: {stash_msg}"


def _get_worktree_path(cr_path: Path) -> Path | None:
    """从 state.yml 读取 worktree 路径。"""
    state_path = cr_path / "state.yml"
    if not state_path.exists():
        return None

    state = load_yaml(state_path)
    worktree_path = state.get("worktree_path")
    if not worktree_path:
        return None
    path = Path(worktree_path)
    # 相对路径按 CR 目录解析（与 evidence_verifier / arc_scheduler 一致），避免 git stash 落到宿主仓库
    return path if path.is_absolute() else cr_path / path
