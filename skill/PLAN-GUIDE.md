# Plan 指南（执行层：结构化分解 + PlanChecker + Wave）

> 解决"大任务上下文腐烂、状态丢失、执行失控"——借鉴 GSD 的 plan.yml/wave/verifier 思想，
> 但**不照搬其 33 Agent / 86 命令**，且与 DeliverHQ 既有能力去重。

## 为什么需要

自由文本的"实现计划"无法机检:任务多大、有没有验收命令、并行任务会不会改同一文件、有没有漏掉验收条件——这些都靠人肉看。`plan.yml` + `plan_checker.py` 把这些变成 **fail-closed 的机器检查**:不合规不许执行。

## 去重原则（重要）

DeliverHQ 已经有半个执行层,所以本能力**只补真正缺的"结构化计划 + 机检"**,不重复造:

| GSD 概念 | DeliverHQ 复用什么（不新增） |
|----------|----------------------------|
| Worker | 现有 **Dev Agent**（读 `context-packs/dev-agent.md`，按 plan item 实现） |
| Verifier | 现有 **ReviewGate + QualityGate + anti_gaming_check**（信证据不信自报） |
| Planner | 由 Spec/人产出 `plan.yml`（不强制新增独立角色） |
| **PlanChecker** | **新增** `plan_checker.py`（这是唯一真缺口） |

## plan.yml 结构

每个 task 是"单个 Agent 可独立完成"的粒度（模板见 `change-requests/CR-TEMPLATE/plan.yml`）:

```yaml
schema: deliverhq-plan
cr_id: CR-001
goal: 为 /todos 增加分页
tasks:
  - task_id: T1
    goal: 实现分页查询
    files: ["src/api/todos.py"]   # 用于文件冲突检测
    depends_on: []
    covers: ["AC-2"]              # 对齐 acceptance-spec.md 的 AC-N
    verify: "pytest tests/test_todos.py::test_pagination"
    done: "GET /api/todos?page=1 返回分页结构且测试通过"
  - task_id: T2
    goal: 补充边界测试
    files: ["tests/test_todos.py"]
    depends_on: ["T1"]
    covers: ["AC-2"]
    verify: "pytest tests/test_todos.py"
    done: "边界用例全绿"
```

## PlanChecker（fail-closed）

```bash
python scripts/plan_checker.py change-requests/CR-001
```

BLOCK 条件（任一）:
1. task 缺 `task_id` / `goal` / `verify` / `done`
2. `acceptance-spec.md` 的某个 `AC-N` 没被任何 task 的 `covers` 覆盖
3. 多个 task 改同一文件但彼此无依赖链（并行文件冲突）
4. 依赖指向不存在的 task，或存在循环依赖
5. （告警，不阻断）单 task 改文件 >8，建议拆细

## Wave 派生（简化版，先不真并行）

```bash
python scripts/plan_checker.py change-requests/CR-001 --emit-waves
```

按依赖拓扑输出 wave plan（无依赖入同 wave，有依赖等上游）:

```yaml
waves:
  - wave: 1
    tasks: [T1]
  - wave: 2
    tasks: [T2]
    depends_on: [T1]
```

第一版只输出 wave plan,**不真并行执行**——并行需多 Agent 隔离（worktree 已有），等真实多 Agent 场景再接。

## 推荐串联

```bash
# 1. 写 plan.yml（覆盖所有 AC，声明文件与依赖）
# 2. PlanChecker 机检（不过不许执行）
python scripts/plan_checker.py change-requests/CR-001
# 3. （可选）看 wave 安排
python scripts/plan_checker.py change-requests/CR-001 --emit-waves
# 4. Dev Agent（=Worker）按 task 实现，读 context-packs/dev-agent.md
# 5. ReviewGate/QualityGate（=Verifier）信证据验收 —— 不新增 Verifier 角色
```

## 诚实边界

- 标记为 **experimental**（见 CAPABILITY-MATRIX.md）。
- 文件冲突检测基于 task 声明的 `files`,声明不全就检不出——它降低风险,不替代人工审查。
- wave 仅"派生计划",不执行;真并行依赖多 Agent，当前为单会话串行。
- selftest 的 `plan_checker_contract` 锁死这条链路始终可用（非文档摆设）。
