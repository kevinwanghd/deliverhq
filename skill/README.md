# DeliverHQ — AI 交付防翻车系统

> **AI 写代码前、中、后主动防翻车**：发现规格缺口、权限风险、测试缺口和知识沉淀缺口。

---

## ⚠️ AI 开发者必读

**在执行任何任务前，请先阅读：**
1. **`.ai-instructions`** — 强制性入口指令
2. **`AGENTS.md`** — 行为规则与 fail-closed 原则
3. **`dir-graph.yaml`** — 权限、受保护路径、Agent 契约

**开发前门禁**：运行 `python scripts/pre_dev_gate.py <CR-ID>`，如返回 BLOCKED，必须提醒人类工程师。

**低噪路由建议**：不确定是否该启用 DeliverHQ 时，先运行 `python scripts/workflow_router.py "用户请求"`。它只输出建议 JSON，不自动创建 CR、不拦截操作。

**项目结构治理（可选）**：新项目可用 `deliverhq init-project --profile fullstack-web` 初始化 AI 友好、人类易复查的目录契约；老项目先运行 `python scripts/scan_legacy_structure.py <项目根>` 生成结构评估报告，再用 progressive StructureGate 渐进约束。

---

## 核心价值

1. 防止没需求就开干
2. 防止自己写自己验
3. 防止测试报告作假
4. 防止高风险路径被 AI 偷偷改
5. 防止交付经验不沉淀
6. 防止多 Agent 上下文爆炸

---

## 三层定位

DeliverHQ 借鉴三个开源实践的**能力**，但不照搬任何一个的复杂度：

| 层 | 借鉴 | DeliverHQ 落地 |
|----|------|---------------|
| **规范层** | OpenSpec | 验收条件（AC-N）、acceptance-spec、GIVEN/WHEN/THEN，由 SpecGate 强制 |
| **纪律层** | Superpowers | TDD（test-plan/QualityGate 真跑）、独立 Review（ReviewGate 信证据）、worktree 隔离、收尾检查 |
| **执行层** | GSD | `state.yml`（文件化状态，不靠会话记忆）、`plan.yml` + PlanChecker（结构化分解）、wave 派生、独立 context-pack |

**刻意不做**：GSD 式的 33 Agent / 86 命令。执行层只新增"结构化计划 + PlanChecker"这一真缺口——Worker 复用现有 Dev Agent，Verifier 复用 ReviewGate/QualityGate，不新增平行角色。详见 `PLAN-GUIDE.md`。

---

## 目录结构

```
DeliverHQ/
├── CLAUDE.md                    # 薄工具入口
├── REPO_MAP.md                  # 模块地图（让 Agent 先读地图）
├── NOISE_FILTER.yml             # 噪音过滤规则
├── COMMANDS.yml                 # 权威 build/test/lint/typecheck 命令
├── AGENTS.md                    # Agent 行为入口
├── dir-graph.yaml               # 机器契约（agents/states/gates/protected_paths）
├── README.md                    # 本文档
│
├── docs/                        # 组织记忆（baseline knowledge）
│   ├── CONTEXT.md              # 项目上下文
│   ├── architecture.md         # 系统架构
│   ├── interfaces.md           # 接口契约
│   ├── data-model.md           # 数据模型
│   ├── rules.md                # 正式规则源（canonical）
│   ├── rules-candidates.md     # 候选规则区（Writeback Agent 写入）
│   ├── rules-deprecated.md     # 废弃规则区
│   ├── decisions.md            # 设计决策记录
│   ├── mistake-book.md         # 错题本
│   ├── verification.md         # 验收标准
│   └── reports/                # 扫描报告
│       ├── code-health-report.md
│       └── legacy-scan-report.md
│
├── change-requests/            # 活跃交付（开发中的 CR）
│   └── CR-TEMPLATE/           # 模板（复制此目录开始新 CR）
│       ├── request.md         # 需求输入
│       ├── acceptance-spec.md # 验收规格（Spec Agent）
│       ├── context-summary.md # 上下文摘要（Context Agent）
│       ├── implementation-plan.md # 实施计划（Dev Agent）
│       ├── test-plan.md       # 测试计划（Test Agent）
│       ├── quality-report.md  # 质量报告（Quality Agent）
│       ├── writeback-report.md # 归档报告（Writeback Agent）
│       ├── human-decisions.md # 人工决策记录
│       ├── traceability.yml   # 需求到代码/测试/影响面的映射
│       ├── exceptions.yml     # 例外审批
│       ├── specgate-report.md
│       ├── designgate-report.md
│       ├── context-window-report.md
│       ├── qualitygate-report.md
│       ├── writeback-gate-report.md
│       └── design/            # 设计产物
│           ├── lo-fi-spec.md
│           ├── hi-fi-spec.md
│           ├── design-decisions.md
│           └── assets/
│
├── delivery/                   # 已交付归档（按月）
│   └── YYYY-MM/
│       └── CR-XXX/
│
├── _archived/                  # 历史归档
│
└── scripts/                    # 治理脚本（12+ 个）
    ├── init_cr.py
    ├── check_skeleton.py
    ├── pre_dev_gate.py
    ├── specgate.py
    ├── designgate.py
    ├── context_window_check.py
    ├── qualitygate.py
    ├── workflow_router.py
    ├── writeback_gate.py
    ├── update_rule_maturity.py
    ├── update_mistake_book.py
    ├── permissiongate.py
    └── cr_state.py
```

---

## 核心概念

### PRD 层：产品意图唯一来源

`docs/PRD.md` 是产品**意图**的唯一来源——薄、叙事、给人看全貌，仅人工维护，Agent 只读。功能锚点 `[PRD-XXX]` 是 CR 的挂载点。

```
docs/PRD.md（意图，给人看） → [Spec Agent 切片] → acceptance-spec.md（可执行，给机器验）
```

- 每个 CR 的 `acceptance-spec.md` 用 `derived_from{prd_section, prd_hash}` 回指它派生的 PRD 锚点。
- PRD 锚点被改后哈希失配 → `drift_check.py` 提示对账（改 CR / 改 PRD / 记差异）。
- `confirmed` 锚点强制对账；`reverse-engineered` 锚点（老项目逆向生成）仅警告。
- 分工：PRD 给人看意图（不写 ID/schema/Do-Not-Touch），acceptance-spec 给机器验；拆分是 Spec Agent 职责，SpecGate 只检查、不生产。

### 文档驱动开发

```
PRD.md → request.md → acceptance-spec.md → implementation-plan.md → 代码 → tests → quality-report.md
```

每个阶段产出必须通过 Gate 检查才能进入下一阶段。

### 9 个协作 Agent

| Agent | 输入 | 输出 | Gate |
|---|---|---|---|
| **Spec Agent** | request.md | acceptance-spec.md | SpecGate |
| **Design Agent** | acceptance-spec.md | design/* | DesignGate |
| **Context Agent** | 所有前置文档 | context-summary.md | ContextWindowGate |
| **Dev Agent** | implementation-plan.md | 源码 | pre_dev_gate |
| **Review Agent** | 源码 + acceptance-spec | review-report.md | ReviewGate |
| **Test Agent** | 源码 | test-plan.md + 测试代码 | - |
| **Quality Agent** | 源码 + 测试 | quality-report.md | QualityGate |
| **Writeback Agent** | quality-report.md | 更新 rules/decisions | WritebackGate |
| **Memory Agent** | 所有 CR 文档 | 归档到 delivery/ | - |
| **Scan Agent** | 源码 | code-health-report.md | - |

### 8 个核心 Gates

1. **SpecGate**：验收规格完备性检查
2. **DesignGate**：设计产物完备性检查（C端强制高保真）
3. **PreDevGate**：开发前综合检查
4. **ContextWindowGate**：上下文滑动窗口纪律检查
5. **ReviewGate**：代码审查门禁（对抗式验证 - 开发和审查必须分离）
6. **QualityGate**：质量门禁（P0 通过率 100%）
7. **DeployGate**：部署就绪检查
8. **WritebackGate**：知识沉淀完整性检查

**关键原则**：ReviewGate 实现对抗式验证 - Dev Agent 实现代码，Review Agent 独立挑刺，确保"干活的人和验收的人不是同一个 agent"。

---

## 快速开始

### 1. 初始化新 CR

```bash
python scripts/init_cr.py CR-001 "添加用户登录日志" "产品经理"
```

### 2. 编写需求

```bash
vim change-requests/CR-001/request.md
```

### 3. 生成验收规格（Spec Agent）

AI 读取 `request.md` 生成 `acceptance-spec.md`。

### 4. 运行 SpecGate

```bash
python scripts/specgate.py change-requests/CR-001/acceptance-spec.md
```

### 5. 开发（Dev Agent）

先运行 PreDevGate，再运行 DevPhase 交接。DevPhase 会输出 worktree/上下文路径并停止，不自动写代码，也不跳过人工开发点。

```bash
python scripts/pre_dev_gate.py CR-001 --lane standard
python scripts/dev_phase.py change-requests/CR-001
```

### 6. 质量检查（Quality Agent）

生成 `quality-report.md` 并运行 QualityGate。默认 `hybrid` 模式会先执行 `verification-manifest.yml` 中的真实 build/test/lint/typecheck 命令；缺少 manifest 不会直接 PASS。

```bash
python scripts/qualitygate.py change-requests/CR-001/
```

### 7. 归档（Memory Agent）

```bash
mv change-requests/CR-001 delivery/2026-06/CR-001
```

---

## 老项目逆向改造（目标2）

把老项目转化成"可通过需求文档驱动开发"的项目。详见 `LEGACY-REVERSE-GUIDE.md`。

```bash
# 1. 客观扫描（技术栈/测试覆盖/复杂度/敏感域 → 候选 + 报告）
python scripts/scan_legacy.py <老项目源码> --out change-requests/CR-XXX/reverse-spec-candidates.yml

# 2. AI 填推断层，人工逐条裁决（真需求 or bug/技术债？）
python scripts/confirm_reverse_spec.py change-requests/CR-XXX/reverse-spec-candidates.yml --list
python scripts/confirm_reverse_spec.py <yml> --id RC-002 --action confirm --criteria "..." --by "张三"

# 3. ReverseSpecGate（未裁决高风险条目 → BLOCK）
python scripts/reverse_spec_gate.py change-requests/CR-XXX

# 4. 转化为正向开发文档（产物须能过 SpecGate）
python scripts/reverse_to_spec.py change-requests/CR-XXX
```

**核心原则**：逆向无独立真相可对照，所以 `review_required` 由**客观信号**（无测试/敏感域/高复杂/高频改动）推导，AI 无权降级；高风险模块强制人工裁决；bug/技术债不得固化为需求（入 `known-deviations.md`）。能力状态见 `CAPABILITY-MATRIX.md`（标记为 experimental）。

---

## Loop 可控性（Goal Contract / 防 Goodhart / 重试上限）

把自动化 loop 从"跑任务"升级成"可控循环"。详见 `LOOP-CONTROL-GUIDE.md`。

```bash
# 0. 目标契约：五段式 + 完成标准双轨（指标+不变量），缺 invariants→BLOCK（防 Goodhart）
python scripts/goal_contract.py change-requests/CR-XXX

# 1. 反钻空子：从 git diff 客观检测删测试/降阈值/改门禁/超范围（不问 Agent 自评）
python scripts/anti_gaming_check.py change-requests/CR-XXX

# 2. 重试守卫：同类失败达上限 → needs_human；拒绝原地重复假设
python scripts/retry_guard.py change-requests/CR-XXX record --gate QualityGate --blocker "..." --hypothesis "..."
```

**三条信条**：① 指标是必要条件不是目标（`metrics` 必须配 `invariants`）；② 信证据不信声明（反钻空子从 diff 取证，绝不问 Agent）；③ 失败有上限有出口（达 `max_retries` → `needs_human`）。

---

## 证据补全 Loop（可恢复 / 有停止条件）

把现有积木串成一个**具体场景的可恢复 loop**——不是抽象"loop engineering 模块"，也不是"让 Agent 干到完成"，而是在状态/证据/停止条件/人工边界下推进可自动化节点。

```bash
python scripts/evidence_loop.py change-requests/CR-001          # 扫描 + 推进一轮
python scripts/evidence_loop.py change-requests/CR-001 --json   # 机器可读
```

每轮：读 `state.yml` 恢复进度（无则 fail-closed，要求先 init_cr）→ 扫描缺哪些真实证据（acceptance-spec / traceability / changed-files / verification-manifest / test-plan）→ 缺则列出 **gaps + 明确 next_action**、写 evidence bundle、状态置 `needs_human`；齐则 `done`（进入 ReviewGate/QualityGate）。

**不新增 Agent**：复用 `cr_state`（状态/恢复）、ReviewGate 同款证据口径、`retry_guard`（重试纪律）、`write_gate_evidence`（留痕）。停止条件明确：齐全=done / 有缺口=needs-human / 无状态=fail-closed。

---

## Fail-Closed 原则

### 规则 1: 文档不完备 = 不开发

```bash
$ python scripts/pre_dev_gate.py CR-001 --lane standard
❌ BLOCKED
  1. 缺少 acceptance-spec.md
  2. acceptance-spec.md 包含 [待确认] 占位符

→ AI 必须拒绝开发，提醒人类工程师补全文档
```

### 规则 2: Gate 未通过 = 不进入下一阶段

```bash
$ python scripts/specgate.py acceptance-spec.md
❌ BLOCKED
  1. 包含模板变量 {{XXX}}
  2. 模糊点未全部解决

→ Spec Agent 必须修复后重新运行 SpecGate
```

### 规则 3: 保护路径不可擅改

`dir-graph.yaml` 中定义的 `protected_paths` 需要明确批准才能修改。

---

## 低噪路由建议器

`workflow_router.py` 是建议器，不是后台自动扫描器。用于在关键交付事件上给出下一步建议：

```bash
python scripts/workflow_router.py "准备写代码实现支付模块重构"
python scripts/workflow_router.py "做完了准备提交"
python scripts/workflow_router.py "处理 200 个 bug issue，帮我分类去重"
```

示例输出字段：

```json
{
  "deliverhq_required": true,
  "lane": "standard",
  "workflow_type": "linear",
  "adversarial_required": true,
  "permissiongate_required": false,
  "reason": "完成/提交前应提示 ReviewGate / QualityGate",
  "next_action": "run_review_quality_gates"
}
```

它只回答“是否建议启用 DeliverHQ、走哪个 lane、下一步是什么”，不会自动创建 CR、不会改文件、不会替代人工判断。

---

## 组织记忆

### rules.md

通用编码规则 + 项目沉淀的正式规则源，带成熟度标记：

- **draft**: 初始规则，仅作提示
- **verified**: 3+ 次引用，默认阻断违反
- **proven**: 5+ 次引用，经过实战验证

### rules-candidates.md

Writeback 阶段的候选规则区。AI 生成的新规则或规则修改建议先写入这里，后续再由人工或治理流程决定是否晋升到 `rules.md`。

### Promote A Candidate Rule

人工审核通过后，可用下面的命令把候选规则晋升到 canonical 规则表：

```bash
python scripts/promote_rule_candidate.py CR-EXAMPLE --gate P1 --detection manual
```

该命令会：
- 向 `docs/rules.md` 追加新的规则表行
- 在 `docs/rules-candidates.md` 对应条目下写入已晋升元数据

### Reject A Candidate Rule

人工审核认为候选规则不应进入 canonical 规则表时，可用下面的命令记录拒绝决定：

```bash
python scripts/reject_rule_candidate.py CR-REJECT-EXAMPLE --reason "与现有规则重复"
```

该命令会保留候选条目，并在 `docs/rules-candidates.md` 上追加拒绝原因和时间。

### List Candidate Rules

查看候选规则治理状态：

```bash
python scripts/list_rule_candidates.py
python scripts/list_rule_candidates.py --status pending
python scripts/list_rule_candidates.py --status rejected
python scripts/list_rule_candidates.py --cr CR-EXAMPLE
python scripts/list_rule_candidates.py --status promoted --cr CR-EXAMPLE
```

默认输出按 `pending / promoted / rejected` 分组，并显示每条候选的标题、来源 CR、推荐值和治理结果。

### rules-deprecated.md

废弃规则区，用于记录已经退出正式规则集的条目及原因。

### decisions.md

架构决策记录，记录为什么选择某个技术方案。

### mistake-book.md

错误案例库，QualityGate 失败时自动记录。

---

## 上下文滑动窗口

为避免 AI 上下文窗口爆炸，采用滑动窗口机制：

- **最多携带 2 个阶段全文**
- **更早阶段压缩为摘要**（`context-summary.md`）
- **阶段切换时必须更新摘要**

---

## 技术栈支持

DeliverHQ 是**技术栈无关**的治理框架，支持：

- **Python**: Django / Flask / FastAPI
- **Java**: Spring Boot / Quarkus
- **C# / .NET**: ASP.NET Core / ABP
- **TypeScript**: Next.js / Nest.js / Express
- **Go**: Gin / Echo / Fiber

---

## 迁移到其他平台

参考 `MIGRATION.md`，可迁移到 Cursor / Windsurf / Cline 等平台。

---

## 扩展阅读

- **`AGENTS.md`** — 9 个 Agent 的详细行为规则
- **`docs/FOUR-FUNCTION-MODE.md`** — 四职能最小模式，说明小团队如何不用机械启动 9 个 Agent
- **`docs/PROJECT-STRUCTURE-GOVERNANCE.md`** — 新老项目结构治理、StructureGate 与渐进迁移策略
- **`MIGRATION.md`** — 迁移到其他 AI 平台
- **`ROLLBACK.md`** — 回滚已交付 CR 的操作指南
- **`CAPABILITY-MATRIX.md`** — 单一能力状态源（stable/experimental/roadmap、是否默认启用）
- **`docs/OPTIMIZATION_2026-06-12.md`** — v4.5 优化记录

---

**本治理体系基于 DeliverHQ v5.17.0**
**模板版本**: 2026-06-12  
**适用**: 所有软件项目（技术栈无关）
