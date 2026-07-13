#!/usr/bin/env python3
"""
plan_checker.py —— Plan 机检 + Wave 派生（执行层，借鉴 GSD）

校验 plan.yml（fail-closed），通过后才允许进入执行。检查项：
  1. 结构：每个 task 有 task_id / goal / verify / done（缺则 BLOCK）
  1b. 写作约束（借 GSD）：verify 必须能区分 pass/fail（拒 echo/print 等 no-op）；
      done/verify 禁主观语言（looks correct/看起来…）；goal/action 不内嵌大段实现代码（BLOCK）
  2. 验收覆盖：acceptance-spec.md 的每个 AC-N 必须被某 task 的 covers 覆盖（漏则 BLOCK）
  3. 文件冲突：多个 task 改同一文件但彼此无 depends_on 链 → BLOCK
  4. 依赖完整 + 无环：depends_on 指向存在的 task 且无循环（环则 BLOCK）
  5. 任务粒度：files 过多（默认 >8）告警（提示拆细，不强制 BLOCK）

与既有能力的去重：Worker=Dev Agent，Verifier=ReviewGate/QualityGate，本脚本只补"计划机检"。

--emit-waves：通过检查后，按依赖拓扑派生 waves（无依赖同 wave，有依赖等上游），打印 YAML。

跨平台 / Python 3.10+。

用法：
  python plan_checker.py <CR目录 或 plan.yml 路径>
  python plan_checker.py <CR目录> --emit-waves
"""

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("需要 PyYAML：pip install PyYAML")
    sys.exit(2)

from runtime_support import configure_console


class Color:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    END = "\033[0m"


GRANULARITY_FILE_LIMIT = 8

# ── GSD 写作约束（借 GSD plan 写作规约）──────────────────────────
# verify 必须能区分 pass/fail：纯 echo/print/true 这类无判定的 no-op 不算验证。
NOOP_VERIFY_RE = re.compile(
    r"^\s*(echo\b|print\b|true\b|:\s*$|#)|^\s*(echo|print)\s+['\"]?(done|ok|pass|完成|成功)",
    re.IGNORECASE,
)
# 主观/不可判定语言：done/verify 里出现即视为非客观判据。
SUBJECTIVE_TERMS = [
    "looks correct", "looks good", "looks right", "seems to work", "should work",
    "works as expected", "看起来", "应该没问题", "差不多", "大概率", "感觉",
]
DESTRUCTIVE_TERMS = (
    "delete", "remove", "rename", "migration", "schema", "public api", "public interface",
    "删除", "移除", "重命名", "迁移", "公共接口", "公开接口",
)
PROTECTED_WRITE_NAMES = {
    "package.json", "pyproject.toml", "requirements.txt", ".env",
    "schema.sql", "openapi.yml", "openapi.yaml",
}


def _is_noop_verify(verify):
    """verify 是否为无法区分 pass/fail 的 no-op。"""
    if not isinstance(verify, str):
        return False
    v = verify.strip()
    if not v:
        return True
    # 多行取每一行判断：只要存在一条实际断言（含退出码/比较/测试命令）即算有效
    lines = [ln.strip() for ln in v.splitlines() if ln.strip()]
    meaningful = False
    for ln in lines:
        if NOOP_VERIFY_RE.match(ln):
            continue
        meaningful = True
        break
    return not meaningful


def _has_subjective(text):
    if not isinstance(text, str):
        return None
    low = text.lower()
    for term in SUBJECTIVE_TERMS:
        if term in low:
            return term
    return None


def _looks_like_code_block(text):
    """goal/action 内嵌大段实现代码（fenced block 或多行带分号/缩进的代码）。"""
    if not isinstance(text, str):
        return False
    if "```" in text:
        return True
    code_lines = [
        ln for ln in text.splitlines()
        if re.search(r"[;{}]\s*$", ln) or re.match(r"\s{4,}\S", ln)
    ]
    return len(code_lines) >= 3


def _resolve(arg):
    p = Path(arg)
    if p.is_dir():
        return p / "plan.yml", p
    return p, p.parent


def load_plan(plan_path):
    if not plan_path.exists():
        return None, "plan.yml 不存在: %s" % plan_path
    try:
        data = yaml.safe_load(plan_path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return None, "解析 plan.yml 失败: %s" % e
    return data, None


def extract_acceptance_ids(cr_dir):
    """从 acceptance-spec.md 提取 AC-N 验收条件 ID。"""
    spec = cr_dir / "acceptance-spec.md"
    if not spec.exists():
        return []
    content = spec.read_text(encoding="utf-8", errors="ignore")
    # 匹配 ### AC-1: ... 或 AC-12 等
    ids = re.findall(r"\bAC-\d+\b", content)
    # 去重保序
    seen = []
    for i in ids:
        if i not in seen:
            seen.append(i)
    return seen


def detect_cycle(tasks):
    """检测 depends_on 是否成环。返回环路径或 None。"""
    graph = {t["task_id"]: list(t.get("depends_on", []) or []) for t in tasks}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {k: WHITE for k in graph}
    stack = []

    def dfs(node):
        color[node] = GRAY
        stack.append(node)
        for dep in graph.get(node, []):
            if dep not in graph:
                continue  # 悬空依赖在别处报
            if color[dep] == GRAY:
                return stack[stack.index(dep):] + [dep]
            if color[dep] == WHITE:
                r = dfs(dep)
                if r:
                    return r
        color[node] = BLACK
        stack.pop()
        return None

    for k in graph:
        if color[k] == WHITE:
            r = dfs(k)
            if r:
                return r
    return None


def _reachable(task_id, tasks_by_id, cache):
    """task_id 通过 depends_on 可达的全部祖先（含间接）。"""
    if task_id in cache:
        return cache[task_id]
    result = set()
    for dep in tasks_by_id.get(task_id, {}).get("depends_on", []) or []:
        result.add(dep)
        result |= _reachable(dep, tasks_by_id, cache)
    cache[task_id] = result
    return result


def check_plan(arg):
    print("%s=== PlanChecker ===%s\n" % (Color.BLUE, Color.END))
    plan_path, cr_dir = _resolve(arg)
    data, error = load_plan(plan_path)
    if error:
        print("%s✗ %s%s" % (Color.RED, error, Color.END))
        return False, [error], None

    tasks = data.get("tasks", []) or []
    project_mode = str(data.get("project_mode", "unspecified")).lower()
    blockers = []
    warnings = []

    if not tasks:
        print("%s✗ plan.yml 无 tasks%s" % (Color.RED, Color.END))
        return False, ["plan.yml 无 tasks"], None

    # 1. 结构完整 + task_id 唯一
    print("%s[1. 结构完整性]%s" % (Color.BLUE, Color.END))
    ids = []
    for i, t in enumerate(tasks):
        tid = t.get("task_id") or "(第%d项无ID)" % (i + 1)
        if not t.get("task_id"):
            blockers.append("task 缺 task_id（第%d项）" % (i + 1))
        if tid in ids:
            blockers.append("task_id 重复: %s" % tid)
        ids.append(tid)
        for field in ("goal", "verify", "done"):
            v = t.get(field)
            if not v or (isinstance(v, str) and (not v.strip() or "{{" in v)):
                blockers.append("%s 缺 %s" % (tid, field))
    if not [b for b in blockers]:
        print("%s  ✓ 所有 task 有 task_id/goal/verify/done%s" % (Color.GREEN, Color.END))
    else:
        for b in blockers:
            print("%s  ✗ %s%s" % (Color.RED, b, Color.END))

    tasks_by_id = {t.get("task_id"): t for t in tasks if t.get("task_id")}

    # 1a. Brownfield 证据：阅读计划、修改边界、复用搜索、破坏性变更声明。
    print("\n%s[1a. Brownfield 证据]%s" % (Color.BLUE, Color.END))
    evidence_issues = []
    if project_mode == "brownfield":
        for t in tasks:
            tid = t.get("task_id") or "(无ID)"
            read_files = t.get("read_files") or []
            write_files = t.get("write_files") or t.get("files") or []
            if not read_files:
                evidence_issues.append("%s 缺 read_files 阅读计划" % tid)
            if not write_files:
                evidence_issues.append("%s 缺 write_files 修改边界" % tid)
            checks = t.get("reuse_checks") or []
            if not checks:
                evidence_issues.append("%s 缺 reuse_checks 既有抽象搜索证据" % tid)
            else:
                for check in checks:
                    if not isinstance(check, dict) or not all(check.get(key) for key in ("intent", "command", "result")):
                        evidence_issues.append("%s 的 reuse_checks 必须含 intent/command/result" % tid)
            destructive = t.get("destructive_change")
            if not isinstance(destructive, dict) or not isinstance(destructive.get("detected"), bool):
                evidence_issues.append("%s 缺 destructive_change.detected 布尔声明" % tid)
                continue
            text = " ".join(str(t.get(key, "")) for key in ("goal", "action")).lower()
            semantic_risk = any(term in text for term in DESTRUCTIVE_TERMS)
            protected_writes = [
                path for path in write_files
                if Path(str(path)).name.lower() in PROTECTED_WRITE_NAMES
            ]
            signals = destructive.get("signals") or []
            if protected_writes and "protected-path" not in signals:
                evidence_issues.append(
                    "%s writes protected paths but lacks destructive_change.signals protected-path: %s"
                    % (tid, ", ".join(protected_writes))
                )
            if semantic_risk and not destructive.get("detected") and not destructive.get("reason"):
                evidence_issues.append("%s 含破坏性语义但 detected=false 且缺 reason" % tid)
            if destructive.get("detected"):
                if not destructive.get("affected_interfaces"):
                    evidence_issues.append("%s 破坏性变更缺 affected_interfaces" % tid)
                if not destructive.get("reference_scan"):
                    evidence_issues.append("%s 破坏性变更缺 reference_scan" % tid)
                decision = destructive.get("human_decision") or {}
                if decision.get("status") != "approved":
                    evidence_issues.append("%s 破坏性变更缺 approved human_decision" % tid)
    if evidence_issues:
        for issue in evidence_issues:
            print("%s  ✗ %s%s" % (Color.RED, issue, Color.END))
        blockers.extend(evidence_issues)
    elif project_mode == "brownfield":
        print("%s  ✓ read/write、复用搜索和破坏性变更证据完整%s" % (Color.GREEN, Color.END))
    else:
        print("%s  ✓ 非 brownfield plan，跳过专项证据%s" % (Color.GREEN, Color.END))

    # 1b. GSD 写作约束：verify 可判定 / done 无主观语言 / goal·action 不内嵌大段代码
    print("\n%s[1b. 写作约束 (GSD)]%s" % (Color.BLUE, Color.END))
    writing_issues = []
    for t in tasks:
        tid = t.get("task_id") or "(无ID)"
        verify = t.get("verify")
        if verify is not None and _is_noop_verify(verify):
            writing_issues.append("%s 的 verify 无法区分 pass/fail（疑似 echo/print 等 no-op）" % tid)
        for field in ("done", "verify"):
            term = _has_subjective(t.get(field))
            if term:
                writing_issues.append("%s 的 %s 含主观/不可判定语言：'%s'" % (tid, field, term))
        for field in ("goal", "action"):
            if _looks_like_code_block(t.get(field)):
                writing_issues.append("%s 的 %s 内嵌大段实现代码（plan 应描述意图，非实现）" % (tid, field))
    if writing_issues:
        for w in writing_issues:
            print("%s  ✗ %s%s" % (Color.RED, w, Color.END))
        blockers.extend(writing_issues)
    else:
        print("%s  ✓ verify 可判定、无主观语言、无内嵌代码%s" % (Color.GREEN, Color.END))

    # 2. 验收覆盖
    print("\n%s[2. 验收条件覆盖]%s" % (Color.BLUE, Color.END))
    ac_ids = extract_acceptance_ids(cr_dir)
    if not ac_ids:
        print("%s  ⚠ 未从 acceptance-spec.md 找到 AC-N（跳过覆盖检查）%s" % (Color.YELLOW, Color.END))
        warnings.append("acceptance-spec.md 无 AC-N，未做覆盖校验")
    else:
        covered = set()
        for t in tasks:
            for c in (t.get("covers", []) or []):
                covered.add(c)
        missing = [ac for ac in ac_ids if ac not in covered]
        if missing:
            print("%s  ✗ 未被任何 task 覆盖的验收条件: %s%s" % (Color.RED, ", ".join(missing), Color.END))
            blockers.append("验收条件未覆盖: %s" % ", ".join(missing))
        else:
            print("%s  ✓ 全部 %d 条 AC 被覆盖%s" % (Color.GREEN, len(ac_ids), Color.END))

    # 3. 依赖完整 + 无环
    print("\n%s[3. 依赖关系]%s" % (Color.BLUE, Color.END))
    for t in tasks:
        for dep in (t.get("depends_on", []) or []):
            if dep not in tasks_by_id:
                blockers.append("%s 依赖不存在的 task: %s" % (t.get("task_id"), dep))
    cycle = detect_cycle([t for t in tasks if t.get("task_id")])
    if cycle:
        print("%s  ✗ 循环依赖: %s%s" % (Color.RED, " → ".join(cycle), Color.END))
        blockers.append("循环依赖: %s" % " → ".join(cycle))
    else:
        print("%s  ✓ 无循环依赖%s" % (Color.GREEN, Color.END))

    # 4. 文件冲突（改同一文件但无依赖链）
    print("\n%s[4. 文件冲突]%s" % (Color.BLUE, Color.END))
    cache = {}
    file_map = {}
    for t in tasks:
        for f in (t.get("write_files") or t.get("files") or []):
            file_map.setdefault(f, []).append(t.get("task_id"))
    conflict = False
    for f, owners in file_map.items():
        if len(owners) < 2:
            continue
        # 任意两个 owner 之间必须有依赖链（一个可达另一个），否则视为并行冲突
        for a in range(len(owners)):
            for b in range(a + 1, len(owners)):
                ta, tb = owners[a], owners[b]
                if tb not in _reachable(ta, tasks_by_id, cache) and \
                   ta not in _reachable(tb, tasks_by_id, cache):
                    print("%s  ✗ 文件冲突: %s 被 %s 和 %s 修改但无依赖关系%s"
                          % (Color.RED, f, ta, tb, Color.END))
                    blockers.append("文件冲突(无依赖): %s (%s, %s)" % (f, ta, tb))
                    conflict = True
    if not conflict:
        print("%s  ✓ 无未声明依赖的文件冲突%s" % (Color.GREEN, Color.END))

    # 5. 粒度告警
    for t in tasks:
        nf = len(t.get("write_files") or t.get("files") or [])
        if nf > GRANULARITY_FILE_LIMIT:
            warnings.append("%s 改 %d 个文件，建议拆细" % (t.get("task_id"), nf))

    # 汇总
    print("\n%s=== PlanChecker 结果 ===%s" % (Color.BLUE, Color.END))
    if blockers:
        print("%s❌ BLOCKED%s" % (Color.RED, Color.END))
        for i, b in enumerate(blockers, 1):
            print("  %d. %s" % (i, b))
        print("\n%s⛔ Plan 不合规，不允许进入执行。%s" % (Color.RED, Color.END))
        return False, blockers, None

    if warnings:
        print("%s⚠️  PASS WITH WARNINGS%s" % (Color.YELLOW, Color.END))
        for i, w in enumerate(warnings, 1):
            print("  %d. %s" % (i, w))
    print("%s✅ PASS - Plan 合规%s" % (Color.GREEN, Color.END))
    return True, [], tasks


def emit_waves(tasks):
    """按依赖拓扑派生 waves：无未完成依赖的 task 入当前 wave。"""
    by_id = {t["task_id"]: t for t in tasks}
    done = set()
    waves = []
    remaining = [t["task_id"] for t in tasks]
    while remaining:
        ready = [tid for tid in remaining
                 if all(d in done for d in (by_id[tid].get("depends_on", []) or []))]
        if not ready:
            # 理论上 check_plan 已挡掉环，这里兜底
            print("%s✗ 无法派生 wave（疑似循环依赖）%s" % (Color.RED, Color.END))
            return None
        waves.append(ready)
        done |= set(ready)
        remaining = [tid for tid in remaining if tid not in done]

    out = {"waves": []}
    for i, w in enumerate(waves, 1):
        entry = {"wave": i, "tasks": w}
        deps = sorted({d for tid in w for d in (by_id[tid].get("depends_on", []) or [])})
        if deps:
            entry["depends_on"] = deps
        out["waves"].append(entry)
    return out


def main():
    configure_console()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("用法: python plan_checker.py <CR目录 或 plan.yml> [--emit-waves]")
        sys.exit(1)
    arg = args[0]
    passed, blockers, tasks = check_plan(arg)

    if passed and "--emit-waves" in sys.argv and tasks:
        print("\n%s=== Wave Plan ===%s" % (Color.BLUE, Color.END))
        waves = emit_waves(tasks)
        if waves is not None:
            print(yaml.safe_dump(waves, allow_unicode=True, default_flow_style=False))

    # 写回状态机（若可用）
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from cr_state import record_from_arg
        record_from_arg(arg, "plan", passed)
    except Exception:
        pass

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
