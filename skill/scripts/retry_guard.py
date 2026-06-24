#!/usr/bin/env python3
"""
retry_guard.py —— 重试上限 + needs-human 出口（防无限重试）

规则（建议#8）：
  - 同类失败最多重试 max_retries 次（默认 3，可被 goal-contract.on_failure.max_retries 覆盖）
  - 每次重试必须说明**新假设**，禁止原地重复（--hypothesis，且不得与上次相同）
  - 重试耗尽 → CR 进入 needs_human 状态

"同类失败"判定：复用 failure_attribution.classify_failure 的 failure_type
（同一 gate + 同一 failure_type 视为同类，避免"换个错误信息就重置计数"的钻空子）。

重试账本独立存于 <CR>/evidence/retry-ledger.yml，不侵入 state.yml 序列化。
needs_human 决策仍写回 state.yml（通过 cr_state）。

跨平台 / Python 3.10+。

用法：
  # 记录一次失败并判定是否还能重试
  python retry_guard.py <CR目录> record --gate QualityGate --blocker "单元测试失败" \
      --hypothesis "怀疑是异步竞争，改用 await"
  # 查看当前重试状态
  python retry_guard.py <CR目录> status
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("需要 PyYAML：pip install PyYAML")
    sys.exit(2)


DEFAULT_MAX_RETRIES = 3


def _ledger_path(cr_dir):
    return cr_dir / "evidence" / "retry-ledger.yml"


def load_ledger(cr_dir):
    p = _ledger_path(cr_dir)
    if not p.exists():
        return {"entries": []}
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {"entries": []}
    except Exception:
        return {"entries": []}


def save_ledger(cr_dir, ledger):
    p = _ledger_path(cr_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(ledger, f, allow_unicode=True, sort_keys=False)


def _failure_signature(gate, blocker):
    """同类失败签名：gate + failure_type（复用归因，比原始文本稳定）。"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from failure_attribution import classify_failure
        attr = classify_failure(gate, blocker)
        return "%s::%s" % (gate, attr.failure_type.value)
    except Exception:
        # 退化：gate + blocker 前 40 字
        return "%s::%s" % (gate, (blocker or "")[:40])


def _max_retries(cr_dir):
    gc = cr_dir / "goal-contract.yml"
    if gc.exists():
        try:
            data = yaml.safe_load(gc.read_text(encoding="utf-8")) or {}
            mr = (data.get("on_failure", {}) or {}).get("max_retries")
            if isinstance(mr, int) and mr >= 1:
                return mr
        except Exception:
            pass
    return DEFAULT_MAX_RETRIES


def record_failure(cr_dir, gate, blocker, hypothesis):
    sig = _failure_signature(gate, blocker)
    ledger = load_ledger(cr_dir)
    entries = ledger.setdefault("entries", [])

    same = [e for e in entries if e.get("signature") == sig]
    attempt = len(same) + 1
    max_retries = _max_retries(cr_dir)

    # 禁止原地重复：新假设不得与同类上次相同
    if same and hypothesis and same[-1].get("hypothesis", "").strip() == hypothesis.strip():
        print("❌ 拒绝记录：本次假设与上次同类失败相同，禁止原地重复重试。")
        print("   必须提出新假设（--hypothesis）。")
        return False, "repeat_hypothesis"
    if not hypothesis or not hypothesis.strip():
        # 第一次失败可不带假设；重试必须带
        if same:
            print("❌ 重试必须说明新假设（--hypothesis）。")
            return False, "missing_hypothesis"

    entries.append({
        "signature": sig,
        "gate": gate,
        "blocker": blocker,
        "hypothesis": hypothesis or "",
        "attempt": attempt,
        "timestamp": datetime.now().isoformat(),
    })
    save_ledger(cr_dir, ledger)

    print("记录同类失败：%s" % sig)
    print("  本类已尝试 %d / %d 次" % (attempt, max_retries))

    if attempt >= max_retries:
        print("\n❌ 重试耗尽（%d 次）→ 转交人类（needs_human）" % max_retries)
        _escalate_needs_human(cr_dir, sig, attempt)
        return False, "needs_human"

    print("\n✅ 仍可重试（剩余 %d 次），但下次必须带新假设。" % (max_retries - attempt))
    return True, "can_retry"


def _escalate_needs_human(cr_dir, sig, attempt):
    """写回 state.yml：进入 needs_human。"""
    try:
        from cr_state import load_state, save_state, CRState, StateTransition
        state = load_state(cr_dir)
        if not state:
            return
        prev = state.current_state.value
        state.current_state = CRState.NEEDS_HUMAN
        state.requires_human = True
        state.blocking_reason = "重试耗尽（%s，%d 次）需人工介入" % (sig, attempt)
        state.updated_at = datetime.now().isoformat()
        try:
            state.transitions.append(StateTransition(
                from_state=prev, to_state="needs_human",
                timestamp=datetime.now().isoformat(),
                trigger="retry_exhausted", operator="retry_guard"))
        except Exception:
            pass
        save_state(cr_dir, state)
        print("   已写回 state.yml: current_state=needs_human")
    except Exception as e:
        print("   （写回 state.yml 失败，不影响判定：%s）" % e)


def show_status(cr_dir):
    ledger = load_ledger(cr_dir)
    entries = ledger.get("entries", [])
    max_retries = _max_retries(cr_dir)
    print("=== 重试状态（max_retries=%d）===" % max_retries)
    if not entries:
        print("（无失败记录）")
        return
    by_sig = {}
    for e in entries:
        by_sig.setdefault(e["signature"], []).append(e)
    for sig, items in by_sig.items():
        status = "needs_human" if len(items) >= max_retries else "can_retry"
        print("  %s : %d/%d 次 [%s]" % (sig, len(items), max_retries, status))
        for it in items:
            print("      attempt %d @ %s — 假设: %s"
                  % (it["attempt"], it["timestamp"][:19], it.get("hypothesis", "")[:50]))


def main():
    parser = argparse.ArgumentParser(description="重试上限 + needs-human 守卫")
    parser.add_argument("cr_path", help="CR 目录")
    parser.add_argument("action", choices=["record", "status"])
    parser.add_argument("--gate", help="失败的 gate 名")
    parser.add_argument("--blocker", help="失败信息")
    parser.add_argument("--hypothesis", help="本次重试的新假设")
    args = parser.parse_args()

    cr_dir = Path(args.cr_path)
    if not cr_dir.exists():
        print("CR 目录不存在: %s" % cr_dir)
        sys.exit(1)

    if args.action == "status":
        show_status(cr_dir)
        sys.exit(0)

    if not args.gate or not args.blocker:
        print("record 需要 --gate 和 --blocker")
        sys.exit(1)

    can_retry, reason = record_failure(cr_dir, args.gate, args.blocker, args.hypothesis)
    # exit 0=可继续重试；非0=不可（needs_human / 拒绝原地重复）
    sys.exit(0 if can_retry else 1)


if __name__ == "__main__":
    main()
