---
name: deliverhq
description: AI 交付防翻车治理框架。文档驱动开发 + 可执行门禁(SpecGate/QualityGate/ReviewGate 等，信证据不信声明) + 老项目逆向(代码→需求文档) + loop 可控性(目标契约/反钻空子/重试上限)。当需要正式多阶段交付、强制"文档不完备不开发"、把老项目转成需求驱动、或防止 AI 钻空子/无限重试时使用。需要 Python 3.10+ 与 PyYAML。
license: 见仓库
---

# SKILL.md — DeliverHQ 入口

> **目标**：通过结构化规格（SDD）、可执行门禁（Gate）、职责边界（Agent）、执行隔离（Workspace）和组织记忆（Writeback），实现 AI 全流程交付质量可控。
>
> **统一不变式**：**done = 建出来的 = 计划的 = 决定的**。所有 Gate 都是这条总判据在某一环的可执行投影；声明完成但证据不闭合即 fail-closed。详见 `AGENTS.md`。

## ⛔ 最高优先级：DeliverHQ Home 目录规则（强制，适用所有 Agent）

> 本规则对所有宿主 Agent（Claude / Hermes / Codex / Gemini / 任意）一律生效。
> Hermes 等仅读本 SKILL.md 的 Agent，必须在此处获知本规则。

1. **凡经 DeliverHQ 分析/治理的项目，必须在该项目主目录创建并使用 `DeliverHQ/` 目录**，作为唯一治理空间。
2. **所有 DeliverHQ 产物强制写入 `<项目根>/DeliverHQ/` 内**：`docs/`、`change-requests/`、`delivery/`、`_archived/`、各类 Gate 报告、PRD、acceptance-spec、扫描报告等。
3. **严禁散落**到项目根目录、项目根 `docs/`、项目根 `change-requests/`，或散落到 skill 自身的安装目录（如 `~/.hermes/skills/deliverhq/`）。
4. **调用写产物的脚本时必须显式指定落点到 `DeliverHQ/`**：
   - `init_cr.py` 必须传 `--home <项目根>/DeliverHQ`
   - `scan_legacy.py` 的 `--out` / `--report` 必须指向 `<项目根>/DeliverHQ/...`
   - 不显式指定落点的脚本会 **fail-closed 报错**，不会默默写到错误位置。
5. 项目自身工程文件（源码、根 README、根 docs）不属于 DeliverHQ，保持原位；两者互补、不覆盖、不混放。
6. 违反即视为路径不清，按 fail-closed：停止并要求归位到 `DeliverHQ/`。

---

## 何时使用 DeliverHQ

✅ **应该使用**：
- 为项目启用"文档门禁式交付流程"
- 扫描老项目的技术债和代码健康度
- 创建需要多阶段协作的 Change Request
- 运行 SpecGate/DesignGate/QualityGate 门禁检查
- 强制执行"文档不完备不开发"规则
- 需要团队协作的正式功能开发
- 初始化新项目时，希望生成 AI 友好、人类易复查的目录结构契约
- 分析老项目目录结构是否混乱，并生成渐进迁移建议

❌ **不应该使用**：
- 只读分析、简单解释、文档错别字修复
- 一次性临时脚本、不涉及项目源码的任务
- 紧急 hotfix（事后补文档）
- 用户明确说"不要启动 DeliverHQ 流程"

---

## 能力状态说明

> **单一事实源**：能力状态以 `CAPABILITY-MATRIX.md` 为准。入口文档只保留最小判断，避免把 roadmap/experimental 写成默认可用。

### 默认可用

- CR 初始化和状态机、核心 Gate（Spec/Design/Architecture/PreDev/Review/Quality/Writeback）
- **用户面动词**（5.10.0+）：spec/design/dev/verify/archive + route 路由器
- **Gate 缓存**（5.12.0+）：`gate_wrapper.py`，依赖未变时跳过 Gate，token -50~73%
- **子 CR 拆解**（5.13.0+）：`create_sub_cr.py` + `decompose`，解决 CR 太大上下文爆掉
- DevPhase Handoff（交接，不自动写码）、Gate Contract / selftest
- Loop 可控性（5.11.0+）：已集成进 verify 动词（goal_contract*/anti_gaming/retry_guard）

### 需要谨慎

- DeployGate / PermissionGate（experimental）、Worktree Manager（工具，非 Agent）
- Failure Attribution / mistake-book dedup（规则演进需人工复核）

### Roadmap / 已退役

- Roadmap: Routing Eval JSON 化、Context schema、MaintenanceGate、Dynamic Workflow
- 已退役: Darwin Score / Quality Ratchet / Loop Mode（违反核心哲学，见 `_archived/`）

---

## 四种核心模式

> **PRD 层**:`docs/PRD.md` 是产品**意图唯一来源**——薄、叙事、给人看,仅人工维护,Agent 只读。功能锚点 `[PRD-XXX]` 是 CR 挂载点。
> 每个 CR 的 `acceptance-spec.md` 是该锚点**可执行切片**,顶部用 `derived_from{prd_section, prd_hash}` 回指。
> 锚点改后哈希失配 → `drift_check.py` 提示对账(改CR/改PRD/记差异);confirmed 强制,reverse-engineered 仅警告。PRD 不写 ID/schema/Do-Not-Touch(那是 spec 的职责)。

### 模式 1 & 2：初始化新项目 / 扫描老项目（按需，详见 `references/modes.md`）

- **模式 1 初始化**：复制 `DeliverHQ/` 到项目根 → `check_skeleton.py DeliverHQ` → 填 `docs/CONTEXT.md` → 调 `dir-graph.yaml` → `selftest.py`。
- **模式 2 扫描老项目**：Scan Agent 分析源码/Git/依赖 → 生成 `docs/reports/code-health-report.md` 与 `legacy-scan-report.md` → 人工审核决定是否起改造 CR。

> 这两种是一次性/低频操作，完整步骤与产出在 `references/modes.md`。下面 模式 3/4 是日常主路径。

---

### 模式 3：创建/推进 CR

**场景**：新功能开发、Bug 修复、重构。

> **首选入口：5 个动词**（收口 54 脚本）：`spec`/`design`/`dev`(停在写码前)/`verify`/`archive`。默认入口非唯一入口，脚本仍可单独调用；任一步 BLOCK 即停并透传原始报告。链路与纪律见 `references/verbs.md`，用法 `skill_orchestrator.py verb <动词> <CR目录>`。

**完整步骤**（命令在**项目根**执行，产物落 `DeliverHQ/` 内）：
1. 建 CR：`python DeliverHQ/scripts/init_cr.py CR-001 "需求名称" "提出人" --home DeliverHQ`，填 `request.md`
2. Spec Agent 从 `docs/PRD.md` 锚点派生 `acceptance-spec.md`，顶部填 `derived_from{prd_section, prd_hash}`
3. **`verb spec`**（specgate+drift_check）；完成后 `prd_writeback.py CR-001` 回填关联 CR 行
4. 选 lane（`pre_dev_gate.py CR-001 --suggest-lane` 看客观建议）：小改动 fast、敏感域 high-risk、超阈值（>8 文件/>10 AC）建议拆 CR
5. **`verb dev`**（pre_dev+context+dev_phase）；输出 worktree/上下文路径后**停止**，不自动写码或跳 Review

**产出**：可测试的验收规格 + 实施计划 + 可回写状态。

---

### 模式 4：运行 Gate 检查

**场景**：阶段切换前验证文档完备性。

**首选**：用动词跑成组门禁（`verb verify` = 审查+质量+反钻空子；`verb archive` = 沉淀+成熟度）。
也可单独调用底层脚本（调试 / CI / 按需），例如 `qualitygate.py <CR>`（真实构建/测试）、`anti_gaming_check.py <CR>`（从 diff 取证）。
> 全部门禁脚本路径、按需单独调用的门禁（permissiongate/deploygate/structuregate/reverse_spec_gate）见 `references/verbs.md` 与 `references/gates.md`。

**结果**：PASS（放行）/ BLOCKED（阻断，提示缺失项）

**重要**：ReviewGate 实现对抗式验证 - Dev Agent 实现代码，Review Agent 独立挑刺，确保"干活的人和验收的人不是同一个 agent"。

---

## 必读文件（按需加载）

| 文件 | 何时读 | 用途 |
|---|---|---|
| `AGENTS.md` | 开发前 | 9 个 Agent 职责边界 |
| `dir-graph.yaml` | 开发前 | 权限路径、protected_paths |
| `docs/CONTEXT.md` | 任何时候 | 项目上下文、技术栈 |
| `docs/rules.md` | 开发/Review | Canonical 编码规则（只读） |
| `docs/rules-candidates.md` | Writeback | 候选规则沉淀（AI 可写） |
| `docs/decisions.md` | 设计阶段 | 历史架构决策 |
| `docs/mistake-book.md` | QualityGate 失败后 | 错误案例库 |
| `references/gotchas.md` | 遇到问题时 | 真实踩坑经验 |

**原则**：不要一次性加载 47 个文件，只加载当前阶段必需文件。

---

## 常见坑（Gotchas）

> 完整 10 条踩坑（含代码示例）见 `references/gotchas.md`。这里只留最常踩的 3 条。

- **过度治理**：改个 README 错别字不必启动完整 CR 流程；轻量任务保持灵活（判据见 lane_advisor `--suggest-lane`）。
- **SpecGate 占位符**：`[NEEDS CLARIFICATION:…]`（借 Spec-Kit）/`[待确认]`/`[TODO]` 放行前必须清零；正文叙述里的"待确认"三字不阻断。
- **workflow_router 是建议器**：只在关键事件手动运行读 JSON 建议，不要接成后台扫描或自动创建 CR。

其余（脚本路径依赖 cwd、Windows `python` vs `python3`、模板变量误判、勿改 CR-TEMPLATE、DeliverHQ vs 项目根 docs、纯后端跳过 DesignGate、QualityGate 自动写 mistake-book）→ `references/gotchas.md`。

---

## 验证 Checklist

### 初始化后验证
- [ ] `python scripts/check_skeleton.py DeliverHQ` 输出 `47/47`
- [ ] `docs/CONTEXT.md` 已填写项目信息
- [ ] `dir-graph.yaml` 的 `protected_paths` 已配置
- [ ] 无模板变量残留（`grep -r "{{.*}}" DeliverHQ/docs/`）

### 创建 CR 后验证
- [ ] `change-requests/CR-001/request.md` 已填写
- [ ] 运行 `pre_dev_gate.py CR-001` 不报错
- [ ] `acceptance-spec.md` 无 `[待确认]` 占位符

### 开发前验证
- [ ] SpecGate PASS
- [ ] DesignGate PASS（如有 UI）
- [ ] ContextWindowGate PASS

### 交付前验证
- [ ] QualityGate PASS（默认 hybrid；执行 verification-manifest.yml 里的真实命令）
- [ ] WritebackGate PASS（规则/决策已沉淀）
- [ ] 运行 `python scripts/selftest.py` 全部通过

---

## 最小使用路径（你只需要记住三件事）

1. **所有开发先建 CR**
2. **CR 没有验收规格，不准写代码**
3. **每次交付后，把规则先写入 `docs/rules-candidates.md`，其他经验写回 mistake-book / decisions**

### 最常用命令（动词收口，记 5 个动词即可）

```bash
python scripts/workflow_router.py "用户请求"                 # 0. 可选：低噪路由建议
python scripts/init_cr.py CR-001 "需求名称" "提出人"         # 1. 建 CR（动词未覆盖的前置步骤）
python scripts/skill_orchestrator.py verb <动词> change-requests/CR-001  # 2. 推进：spec/design/dev/verify/archive
python scripts/specgate.py change-requests/CR-001/acceptance-spec.md     # 3. 也可单独跑某个底层门禁（调试/CI）
```
> 动词→链路与纪律见 `references/verbs.md`；`skill_orchestrator.py verbs` 列出全部链路。

---

## 深入阅读

需要了解更多时，按需阅读：

- `references/modes.md` — 四种模式详解
- `references/verbs.md` — 5 个用户面动词（链路 / 纪律 / 单独调用）
- `references/gates.md` — Gate 详解
- `references/gotchas.md` — 完整踩坑经验
- `references/file-structure.md` — 文件结构说明
- `references/examples.md` — Before/After 案例

一键自检：`python scripts/selftest.py`（骨架完整 / 示例 CR 通过 / Gate 行为正常 / 无模板残留）。

---

**版本**：v5.15.3 ｜ **一句话**：文档门禁 + 证据驱动 + 对抗式验证（信证据不信声明）；日常 CR 用 5 个动词收口。
