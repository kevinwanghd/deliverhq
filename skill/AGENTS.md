# AGENTS.md — DeliverHQ Behavior Entry

> **核心概念**：本文档中的 "Agent" 实际指 **Phase（阶段）**——工作流中的步骤节点。
> 每个阶段有明确的输入/输出规范和 Gate 握手协议，但并非独立的 Agent 实例。
> 真正的多 Agent 协作（如并行 worktree、subagent 验证）会在具体实现中单独标注。

```
DeliverHQ 流程图（单人多阶段，不是多 Agent 系统）
────────────────────────────────────────────────────────
  Spec ──▶ SpecGate ──▶ Design ──▶ DesignGate
                            │
                    ArchitectureGate ──▶ Context ──▶ Dev
                                                          │
                              PermissionGate ◀── (high-risk)
                                                          │
                             Review ──▶ Test ──▶ Quality
                                                    │
                                           WritebackGate ──▶ Archive
────────────────────────────────────────────────────────
每个节点是阶段（Phase），不是独立 Agent
Gate 是质量门禁，不是任务分发器
```

> **入口纪律**：会话启动/每轮只强制读 **1 个文件**（`STATE.md`，~100 tokens）。
> 其余文件**按阶段/按需**加载，禁止在入口一次性全量吃进上下文。
> 违反此纪律 = 上下文浪费，等同治理债（借"只加载当前阶段必需文档"原则，见文末《按阶段加载文档》）。

**每轮必读（仅此一项）**
- `STATE.md`（极小 STATE 指针；长会话/compaction 后靠它重建"我在链条哪一环"。由 `handoff_state.py` 从各 CR 的 state.yml 刷新）

**行为规则层（首次进入本 skill 或不确定规则时读一次，通常已在上下文）**
- `AGENTS.md`（本文——不变式 / fail-closed / Gate 冻结 / human-in-the-loop 等行为规则）

**动手前按需读（进入具体开发动作时才拉，用完不必常驻）**
- `dir-graph.yaml` — 权限路径、protected_paths（改文件前读）
- `<当前CR>/state.yml` — 当前 CR 的状态快照（推进某个 CR 时读）
- `docs/CONTEXT.md` — 项目上下文、技术栈（需要项目背景时读）
- Current CR artifacts under `change-requests/CR-*`（推进该 CR 时读对应产物）

**按需查（不进强制链，用到才读对应片段）**
- `references/agent-roles.md` — 9 个 Agent 职责边界与文件权限（扮演某 Agent 时只读那一节）
- `CAPABILITY-MATRIX.md` — 能力状态唯一真相源（查"某能力能不能用/是否 default_enabled"时读）
- `docs/MEMORY.md` / `REPO_MAP.md` / `NOISE_FILTER.yml` / `COMMANDS.yml` — 组织记忆、模块地图、噪音过滤、权威命令（各自场景触发时读）

> **STATE 指针纪律（替代 SessionStart hook）**：阶段切换 / Gate 通过后，运行
> `python scripts/handoff_state.py --home <项目根>/DeliverHQ` 刷新 `STATE.md`。
> 它 agent 无关、零 hook，是长会话里"别忘了自己在治理链哪一环"的最便宜手段。

## 统一交付不变式（贯穿全链）

> **done = 建出来的 = 计划的 = 决定的**
> （done = what was *built* equals what was *planned*, and what was *planned* equals what was *decided*。借 GSD。）

这是串起 PRD → acceptance-spec → Architecture → Dev → Review → Quality 全链的总判据，
每道 Gate 都是它在某一环的可执行投影：

- **决定的**：`docs/PRD.md` 的功能锚点（产品意图，人工维护）。
- **计划的**：CR 的 `acceptance-spec.md`（用 `derived_from` 回指 PRD 锚点）+ `architecture-design.md`。
- **建出来的**：实际 diff / `traceability.yml` / verification-manifest 真实执行结果。

任一环断裂即视为"未 done"：
- 建出来的 ≠ 计划的 → ReviewGate（对照 spec/diff）、anti_gaming_check（从 diff 取证）拦截。
- 计划的 ≠ 决定的 → drift_check（PRD↔CR 哈希对账）、SpecGate 检查 9 拦截。

声明"完成"而无证据闭合此不变式的，按 fail-closed 处理，不予放行。

## Loop 可控性（防 Goodhart + 收敛出口）

`verify` 动词已集成 loop 可控性三件套（5.11.0+）：goal_contract*（条件）→ review → quality → anti_gaming，失败后 retry_guard 只读 status（不自动 record）。详见 `references/loop-control.md`。

## Fail-closed rules
- If CR-ID, current phase, source of truth, path, or permission is unclear, stop and ask.
- Do not develop when SpecGate, DesignGate, ArchitectureGate, or ContextWindowGate blocks.
- Do not modify protected paths unless explicitly approved.

## DeliverHQ Home 目录规则（强制）
- 凡经 DeliverHQ 分析/治理的项目，**必须在项目主目录创建并使用 `DeliverHQ/` 目录**作为唯一治理空间。
- **所有 DeliverHQ 相关文件强制放入 `DeliverHQ/` 内**：`docs/`、`change-requests/`、`delivery/`、`_archived/`、`scripts/`、各类 Gate 报告、PRD、acceptance-spec 等。
- 这些路径**一律相对 `DeliverHQ/` 解析**（如 `DeliverHQ/docs/PRD.md`、`DeliverHQ/change-requests/CR-*`），**严禁散落到项目根目录、根 `docs/` 或根 `change-requests/`**。
- 项目自身的工程文件（源码、根 README、根 docs 等）不属于 DeliverHQ，保持原位；DeliverHQ 与其互补、不覆盖、不混放。
- 违反即视为路径不清，按 fail-closed：停止并要求归位到 `DeliverHQ/`。

## 10 Agent phases
Spec → Design (if UI) → SpecGate/DesignGate → Architecture → ArchitectureGate → Context → Dev → PermissionGate (high-risk) → Review → Test → Quality → Writeback → Memory → WritebackGate → Archive.

### CR 创建命令（统一入口）

每个 CR 必须通过 `init_cr.py` 创建，确保使用统一模板：

```bash
# 标准流程（自动使用 CR-TEMPLATE）
python skill/scripts/init_cr.py CR-001 "需求标题" [REQUESTER]

# 快速修复（fast lane）
python skill/scripts/init_cr.py CR-002 "Bug 修复" --lane fast

# 指定 DeliverHQ 目录
python skill/scripts/init_cr.py CR-003 "新功能" --home /path/to/project/DeliverHQ
```

- **模板来源**：`skill/change-requests/CR-TEMPLATE/`（自动使用，无需手动复制）
- **产物落点**：`<home>/change-requests/<CR-ID>/`
- **Lane 选择**：`fast`（小改动）/ `standard`（常规）/ `high-risk`（高风险，需人工审批）

> ArchitectureGate（第二道人工门禁）：编码前必须有 `architecture-design.md` 并经人工确认。
> 缺架构设计或未替换模板变量 → BLOCKED；未人工确认 → 警告。对应 `python scripts/architecturegate.py`。

流程说明：
- Review Agent 在 Test 之前审查代码逻辑（对照需求）
- Test Agent 执行测试用例
- Quality Agent 验证测试结果和质量指标

## 用户面动词（脚本收口，默认入口）
5 个动词收口日常 CR：`spec`/`design`/`dev`(停在写码前)/`verify`/`archive`（`skill_orchestrator.py verb <动词> <CR>`）。默认入口非唯一入口、任一步 BLOCK 即停并透传原报告、派生自 `FROZEN_GATES`、不碰 `get_default_pipeline()`——详见 `references/verbs.md`（`verb_layer_contract` 锁死）。

## Gate 冻结 + 组合规则（治理债红线）
- **Gate 集合已冻结**：当前 11 道 Gate（见 `scripts/gate_composition_check.py` 的 `FROZEN_GATES`）是基线。
  新增一道 Gate 前，必须在 CR 里论证"现有 Gate 无法覆盖"，并显式更新 `FROZEN_GATES`；否则 `gate_composition_check.py` BLOCK。
- **禁 Gate 套 Gate**（借 Pocock 组合纪律）：Gate 脚本之间默认不得相互 import/调用，避免隐藏耦合链。
  唯一例外是 `ALLOWED_GATE_EDGES` 显式登记的边（当前仅 `pre_dev_gate → permissiongate`）。
  Gate 的串联只能由编排器（`skill_orchestrator.py`）显式完成，不是 Gate 内部偷偷调另一个 Gate。
- 运行：`python scripts/gate_composition_check.py`（selftest 的 `gate_composition_contract` 已锁死正反例）。

## Human-in-the-loop contract
- Dev Agent 产出为 **Draft PR**，不直接合并到主分支
- Human Review 为必经点，包括：代码审查、业务验证、安全检查
- 仅在 Human Approval 后方可合并，自动化流程不可绕过此契约

## UI gate
- UI work must pass Design Agent.
- C-end UI requires high-fidelity design and prototype/equivalent.

## Context window
- Update `context-summary.md` before phase transition.
- Never carry more than two phases of full context.

## Agent 职责边界与文件权限（按需读，不进强制链）

> 9 个 Agent（Spec / Design / Context / Dev / Review / Test / Quality / Writeback / Memory / Scan）的完整
> 可读/可写/产出标准/握手协议已抽到 **`references/agent-roles.md`**。
> **扮演某个 Agent 时只读你当前那一节**，不必一次性加载全部——这是入口瘦身的关键一环。
>
> 一句话记忆：每个 Agent 只碰自己职责内的文件，跨 Agent 交接一律走 Gate 握手（信证据不信声明）。

## 按阶段加载文档（唯一权威加载策略）

> 这是 DeliverHQ 的**唯一**文档加载策略，与顶部《Read order》一致：入口只读 `STATE.md`，
> 其余按当前阶段**仅加载必需文档**。任何"每轮必读一堆文件"的说法都以本节为准被推翻。

### Spec 阶段（3 个核心文档）
- `AGENTS.md` — 行为规则（通常已在上下文）
- `dir-graph.yaml` — 权限与路径
- `docs/CONTEXT.md` — 项目上下文
- 扮演具体 Agent 时，另读 `references/agent-roles.md` 对应那一节

### Design 阶段（+1）
- 上述 3 个 + `acceptance-spec.md`

### Dev 阶段（+2）
- 上述 4 个 + `context-summary.md` + `implementation-plan.md`

### Test 阶段（+1）
- 上述 6 个 + `test-plan.md`

> **Roadmap 功能（不在本文档承诺范围内）**：Legacy Scan（逆向需求发现）是 roadmap 状态，
> 详见 `CAPABILITY-MATRIX.md` 中的 `default_enabled` 列。当前默认 pipeline 不包含此功能。

### Quality 阶段（+2）
- 上述 7 个 + `quality-report.md` + `docs/rules.md`

### Writeback 阶段（+2）
- 上述 9 个 + `writeback-report.md` + `docs/verification.md`

**原则**：只加载当前阶段 + 上一阶段全文，更早阶段通过 `context-summary.md` 的摘要获取。
