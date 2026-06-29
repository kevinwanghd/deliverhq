# AGENTS.md — DeliverHQ Behavior Entry

## Read order
0. `STATE.md`（极小 STATE 指针，每轮必读；长会话/compaction 后靠它重建"我在链条哪一环"。由 `handoff_state.py` 从各 CR 的 state.yml 刷新）
1. `AGENTS.md`
2. `dir-graph.yaml`
3. `state.yml`（当前 CR 的状态快照）
4. `docs/CONTEXT.md`
5. `docs/MEMORY.md`
6. `REPO_MAP.md` / `NOISE_FILTER.yml` / `COMMANDS.yml`（模块地图、噪音过滤、权威命令）
7. Current CR artifacts under `change-requests/CR-*`
8. `CAPABILITY-MATRIX.md`（能力状态唯一真相源；本文不重复维护完整能力状态）

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

## Agent 职责边界与文件权限

每个 Agent 仅可读写其职责范围内的文件，跨 Agent 协作通过握手协议（Gate 检查）进行交接。

### Spec Agent
**职责**：将需求转化为可测试的验收规格
**可读**：`request.md`, `docs/CONTEXT.md`, `docs/architecture.md`
**可写**：`acceptance-spec.md`, `specgate-report.md`
**产出标准**：至少 3 个场景（主流程+异常+边界），所有验收标准可量化，无 `[待确认]` 占位符
**握手协议**：必须通过 SpecGate 检查（`python scripts/specgate.py`）才能交接给 Design/Context Agent

### Design Agent
**职责**：产出 UI 设计规格（低保真/高保真）和可交互原型
**可读**：`acceptance-spec.md`, `request.md`, `docs/architecture.md`
**可写**：`design/lo-fi-spec.md`, `design/hi-fi-spec.md`, `design/prototype.html`, `design/design-decisions.md`, `design/assets/*`, `designgate-report.md`
**产出标准**：
  - B 端：低保真线框图 + 交互说明
  - C 端：高保真设计稿 + 视觉规范 + 可交互原型（必须）
**握手协议**：必须通过 DesignGate 检查（`python scripts/designgate.py`），C 端 UI blocking=true 不可 override

### Context Agent
**职责**：生成上下文摘要，控制滑动窗口
**可读**：`acceptance-spec.md`, `design/*`, `docs/CONTEXT.md`, 上一个 CR 的 `context-summary.md`（如有）
**可写**：`context-summary.md`, `context-window-report.md`
**产出标准**：摘要结构包含 Previous Phase Summary, Current Phase Focus, Key Decisions, Open Questions
**握手协议**：必须通过 ContextWindowGate 检查（`python scripts/context_window_check.py`）才能交接给 Dev Agent

### Dev Agent
**职责**：按 `architecture-design.md` 实施代码（证据驱动），实现业务逻辑
**可读**：`acceptance-spec.md`, `architecture-design.md`, `context-summary.md`, `design/*`, `docs/architecture.md`, `docs/interfaces.md`, `docs/data-model.md`, `docs/rules.md`, 项目源码
**可写**：`implementation-plan.md`, `architecture-alignment-report.md`, 项目源码（根据 `dir-graph.yaml` 定义的路径），`traceability.yml`（需求到代码映射）
**禁止写入**：`protected_paths`（见 `dir-graph.yaml`），包括配置文件、敏感路径
**证据驱动原则**：
  - 实现前先按架构设计的「设计分块到实现映射」生成执行计划；每个 block 必须有目标文件/组件/字段/交互/证据
  - 缺落点或缺证据的 block **不得硬写代码**，必须在对齐报告中标 blocked
  - 涉及 UI 时先产 `direct-read-audit.md`，视觉常量追溯到设计源原始值，不靠截图臆测
**产出标准**：
  - 代码通过编译
  - 输出 `architecture-alignment-report.md`（文件/分块/接口字段/路由/UI/埋点/偏差/待验证项）
  - 创建 **Draft PR**（不直接合并）
  - 关键路径有单元测试
  - 遵循 `docs/rules.md` 约定
**回流约束**：对齐报告存在 missing 时最多回流补全 5 轮，仍不齐则 blocked，禁止硬写绕过
**握手协议**：开发前必须运行 `python scripts/pre_dev_gate.py` 确保文档齐全

### Review Agent
**职责**：对照需求审查实现，确保代码符合验收规格（对抗式验证 - 独立于 Dev Agent）
**可读**：`acceptance-spec.md`, `implementation-plan.md`, `context-summary.md`, `traceability.yml`, 项目源码
**可写**：`review-report.md`, `design/visual-audit-report.md`（涉及 UI 时）
**产出标准**：
  - 每个验收条件对应的代码实现已审查
  - 识别逻辑缺陷、边界遗漏、安全风险
  - 明确标注 PASS / NEED_FIX / BLOCKED
  - P0 阻断问题必须真实列出（不能为空或占位符）
**视觉还原审计（涉及 UI 时）**：
  - 编译通过 ≠ 还原正确；对照设计源产出 `design/visual-audit-report.md`
  - 检查布局/间距/字号/颜色/组件状态/资源/响应式/多端，输出偏差清单
  - 偏差不靠人手动改，回流 code-generator 精准修复；修复遵守 direct-read-audit（追溯设计源原始值）
**握手协议**：必须通过 ReviewGate（`python scripts/reviewgate.py`）才能交接给 Test Agent
**关键原则**：Review Agent 独立挑刺，不能由 Dev Agent 自己验证自己的代码 - 这是对抗式验证的核心

### Test Agent
**职责**：编写测试用例，执行测试
**可读**：`acceptance-spec.md`, `implementation-plan.md`, `context-summary.md`, 项目源码和测试代码
**可写**：`test-plan.md`, 测试代码（`*.Tests` 项目）
**产出标准**：每个验收场景有对应测试用例，P0 场景覆盖率 100%，整体覆盖率 ≥ 80%
**握手协议**：所有测试通过后才能交接给 Quality Agent

### Quality Agent
**职责**：质量检查，生成质量报告
**可读**：`acceptance-spec.md`, `implementation-plan.md`, `test-plan.md`, 项目源码、测试报告、代码覆盖率报告
**可写**：`quality-report.md`, `qualitygate-report.md`
**编译验证（build-verifier 职责，把"写完"变成"可运行"）**：
  - 执行 `verification-manifest.yml` 的 build / lint / typecheck / test 真实命令（由 QualityGate 驱动）
  - 移动端/客户端按需开启 `platform_bundles`（iOS / Android / Harmony / RN bundle）验证
  - **编译失败不只贴错误，必须自动定位并修复**：常见 import 路径错误、类型不匹配、接口字段变更、平台后缀缺失、依赖误用、lint 规则不满足
  - 仅当错误确属外部环境或缺人工决策时，才允许 partial
**产出标准**：P0 测试通过率 100%，代码覆盖率 ≥ 80%，无 Critical 级别静态分析告警
**握手协议**：必须通过 QualityGate 检查（`python scripts/qualitygate.py`）才能交接给 Writeback Agent
**失败处理**：QualityGate 失败时，自动调用 `python scripts/update_mistake_book.py` 将失败原因追加到 `docs/mistake-book.md`

### Writeback Agent
**职责**：知识沉淀，更新组织记忆
**可读**：所有 CR 文档，`docs/*`
**可写**：`writeback-report.md`, `writeback-gate-report.md`, `docs/architecture.md`, `docs/interfaces.md`, `docs/data-model.md`, `docs/rules-candidates.md`, `docs/decisions.md`, `docs/mistake-book.md`, `traceability.yml`
**产出标准**：
  - 新增/修改的规则先写入 `docs/rules-candidates.md`，不得直接改写 `docs/rules.md`
  - 人工审核通过后，使用 `python scripts/promote_rule_candidate.py <CR-ID> --gate <P0|P1> --detection <mode>` 将候选规则晋升到 `docs/rules.md`
  - 人工审核否决候选规则时，使用 `python scripts/reject_rule_candidate.py <CR-ID> --reason "<原因>"` 在 `docs/rules-candidates.md` 记录 rejected 状态
  - 新增/修改的架构决策记录到 `docs/decisions.md`
  - 新增/修改的接口记录到 `docs/interfaces.md`
  - `traceability.yml` 映射完整（需求 ID → 代码文件）
**握手协议**：必须通过 WritebackGate 检查（`python scripts/writeback_gate.py`）才能进入归档

### Memory Agent
**职责**：自动化归档，规则成熟度追踪
**可读**：所有 CR 文档，`docs/rules.md`, `delivery/` 历史记录
**可写**：`delivery/YYYY-MM/CR-XXX/`（归档目标路径）
**产出标准**：
  - CR 移入 `delivery/YYYY-MM/CR-XXX/` 按月归档
  - 运行 `python scripts/update_rule_maturity.py` 自动提升规则成熟度（draft → verified → proven）
**握手协议**：归档后生成归档清单（包含回滚检查项），记录到 `delivery/YYYY-MM/README.md`

### Scan Agent（老项目逆向，目标2）
**职责**：扫描老项目源码，逆向生成需求候选，经人工裁决后转化为正向开发文档
**可读**：整个项目源码、Git 历史
**可写**：`reverse-spec-candidates.yml`, `docs/reports/legacy-scan-report.md`, `known-deviations.md`
**可执行链路**（不只是文档）：
  1. `scan_legacy.py <项目源码>` — 客观扫描：技术栈/测试覆盖/复杂度/敏感域 → 候选 + 报告
     （`review_required` 由**客观信号**推导，AI 无权降级；对抗"AI 自信但错了"的盲区）
  2. AI 为候选填推断层（`inferred_behavior` / `assumptions` / `evidence`）
  3. `confirm_reverse_spec.py` — 人工逐条裁决：confirm/modify/reject/defer + 回答 is_real_requirement
  4. `reverse_spec_gate.py` — **ReverseSpecGate**：未裁决高风险条目 → BLOCK（硬约束）
  5. `reverse_to_spec.py` — 转化为 `acceptance-spec.md` + `traceability.yml`（反向映射到现有代码）
**握手协议**：必须通过 ReverseSpecGate；转化产物须通过 SpecGate 才能进入正向开发链路（目标1）
**关键原则**：逆向无独立"真相"可对照——bug/workaround 可能被误当需求。
  因此 (a) 高风险模块强制人工裁决，(b) 必须区分"真需求"与"bug/技术债"（后者入 `known-deviations.md`，不固化）

## 按阶段加载文档（减轻上下文负担）

为避免一次性加载全部 46 个文件消耗过多 token，按当前阶段**仅加载必需文档**：

### Spec 阶段（3 个核心文档）
- `AGENTS.md` — 行为规则
- `dir-graph.yaml` — 权限与路径
- `docs/CONTEXT.md` — 项目上下文

### Design 阶段（+1）
- 上述 3 个 + `acceptance-spec.md`

### Dev 阶段（+2）
- 上述 4 个 + `context-summary.md` + `implementation-plan.md`

### Test 阶段（+1）
- 上述 6 个 + `test-plan.md`

### Quality 阶段（+2）
- 上述 7 个 + `quality-report.md` + `docs/rules.md`

### Writeback 阶段（+2）
- 上述 9 个 + `writeback-report.md` + `docs/verification.md`

**原则**：只加载当前阶段 + 上一阶段全文，更早阶段通过 `context-summary.md` 的摘要获取。
