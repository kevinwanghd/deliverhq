#!/usr/bin/env python3
"""
goal_contract.py —— Goal Contract 校验器

校验 goal-contract.yml 的结构完整性与防 Goodhart 约束。

核心校验（fail-closed）：
  - 五段式齐全：goal / success_criteria / verification_commands / boundaries / on_failure / escalate_to_human_when
  - 目标非模糊：goal 不得为模板占位符或"自动修复/自动交付"这类模糊词
  - 双轨完成标准：success_criteria 必须同时有 metrics 和 invariants
       （只有 metrics = Goodhart 陷阱：指标可被钻空子达成。必须有 invariants 兜底）
  - 每个 metric 有可执行 command 和明确 expect
  - boundaries 有 forbidden_actions（防钻空子边界）
  - on_failure 有 max_retries（防无限重试）

跨平台 / Python 3.10+。

用法：
  python goal_contract.py <CR目录 或 goal-contract.yml 路径>
"""

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("需要 PyYAML：pip install PyYAML")
    sys.exit(2)


class Color:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    END = "\033[0m"


# 模糊目标黑名单（必须改成可验证目标）
FUZZY_GOALS = ["自动修复", "自动交付", "自动优化", "优化代码", "修复bug",
               "auto fix", "auto deliver", "improve", "make it work"]


def _resolve_path(arg):
    p = Path(arg)
    if p.is_dir():
        return p / "goal-contract.yml"
    return p


def load_contract(path):
    if not path.exists():
        return None, "goal-contract.yml 不存在: %s" % path
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return None, "解析失败: %s" % e
    return data, None


def check_goal_contract(arg):
    print("%s=== Goal Contract 校验 ===%s\n" % (Color.BLUE, Color.END))
    path = _resolve_path(arg)
    data, error = load_contract(path)
    if error:
        print("%s✗ %s%s" % (Color.RED, error, Color.END))
        return False, [error]

    blockers = []

    # 1. 五段式齐全
    print("%s[结构完整性]%s" % (Color.BLUE, Color.END))
    required = ["goal", "success_criteria", "verification_commands",
                "boundaries", "on_failure", "escalate_to_human_when"]
    for key in required:
        if key not in data or data[key] in (None, "", [], {}):
            print("%s  ✗ 缺少 %s%s" % (Color.RED, key, Color.END))
            blockers.append("缺少必需段: %s" % key)
        else:
            print("%s  ✓ %s%s" % (Color.GREEN, key, Color.END))

    # 2. 目标非模糊 / 非占位符
    print("\n%s[目标可验证性]%s" % (Color.BLUE, Color.END))
    goal = str(data.get("goal", ""))
    if "{{" in goal or not goal.strip():
        print("%s  ✗ goal 仍是占位符/为空%s" % (Color.RED, Color.END))
        blockers.append("goal 未填写")
    elif any(fz in goal.lower() for fz in FUZZY_GOALS):
        print("%s  ✗ goal 过于模糊: '%s'%s" % (Color.RED, goal[:40], Color.END))
        blockers.append("goal 模糊，需改成可验证目标")
    else:
        print("%s  ✓ goal 具体%s" % (Color.GREEN, Color.END))

    # 3. 双轨完成标准（核心防 Goodhart）
    print("\n%s[完成标准双轨：指标 + 不变量]%s" % (Color.BLUE, Color.END))
    sc = data.get("success_criteria", {}) or {}
    metrics = sc.get("metrics", []) or []
    invariants = sc.get("invariants", []) or []
    if not metrics:
        print("%s  ✗ 缺少 metrics（可测指标）%s" % (Color.RED, Color.END))
        blockers.append("success_criteria 缺少 metrics")
    else:
        print("%s  ✓ metrics: %d 个%s" % (Color.GREEN, len(metrics), Color.END))
        for m in metrics:
            if not isinstance(m, dict) or not m.get("command") or not m.get("expect"):
                print("%s    ✗ metric 缺 command/expect: %s%s"
                      % (Color.RED, m.get("id", "?") if isinstance(m, dict) else m, Color.END))
                blockers.append("metric 缺少 command 或 expect")
    if not invariants:
        # 这是关键：只有指标没有不变量 = Goodhart 陷阱
        print("%s  ✗ 缺少 invariants（不变量）—— 仅靠指标会被钻空子达成%s" % (Color.RED, Color.END))
        blockers.append("success_criteria 缺少 invariants（防 Goodhart 必需）")
    else:
        print("%s  ✓ invariants: %d 个%s" % (Color.GREEN, len(invariants), Color.END))

    # 4. 验收命令存在
    print("\n%s[验收命令]%s" % (Color.BLUE, Color.END))
    vcmds = data.get("verification_commands", []) or []
    if not vcmds:
        print("%s  ✗ 无验收命令（缺验证 = 不可验收）%s" % (Color.RED, Color.END))
        blockers.append("缺少 verification_commands")
    else:
        print("%s  ✓ %d 条验收命令%s" % (Color.GREEN, len(vcmds), Color.END))

    # 5. 边界禁止项
    print("\n%s[边界]%s" % (Color.BLUE, Color.END))
    boundaries = data.get("boundaries", {}) or {}
    if not boundaries.get("forbidden_actions"):
        print("%s  ✗ 缺少 forbidden_actions%s" % (Color.RED, Color.END))
        blockers.append("boundaries 缺少 forbidden_actions")
    else:
        print("%s  ✓ forbidden_actions: %d 条%s"
              % (Color.GREEN, len(boundaries["forbidden_actions"]), Color.END))

    # 6. 失败降级
    print("\n%s[失败降级]%s" % (Color.BLUE, Color.END))
    on_failure = data.get("on_failure", {}) or {}
    mr = on_failure.get("max_retries")
    if not isinstance(mr, int) or mr < 1:
        print("%s  ✗ on_failure.max_retries 缺失/非法%s" % (Color.RED, Color.END))
        blockers.append("on_failure 缺少合法 max_retries")
    else:
        print("%s  ✓ max_retries=%d%s" % (Color.GREEN, mr, Color.END))

    # 汇总
    print("\n%s=== Goal Contract 结果 ===%s" % (Color.BLUE, Color.END))
    if blockers:
        print("%s❌ BLOCKED%s" % (Color.RED, Color.END))
        for i, b in enumerate(blockers, 1):
            print("  %d. %s" % (i, b))
        print("\n%s⛔ Goal Contract 不合规，loop 不应启动。%s" % (Color.RED, Color.END))
        return False, blockers

    print("%s✅ PASS - Goal Contract 合规（含防 Goodhart 不变量）%s" % (Color.GREEN, Color.END))
    return True, []


def main():
    if len(sys.argv) < 2:
        print("用法: python goal_contract.py <CR目录 或 goal-contract.yml>")
        sys.exit(1)
    arg = sys.argv[1]
    passed, _ = check_goal_contract(arg)
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from cr_state import record_from_arg
        record_from_arg(arg, "goal_contract", passed)
    except Exception:
        pass
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
