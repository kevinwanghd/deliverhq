# DeliverHQ PRD 层设计说明

> 适用版本：v5.4.0+
> 本文记录「PRD 层」为什么这么设计，供后续维护者理解决策动因，而非重新推导。

## 设计动因

v5.3.0 之前，`acceptance-spec`（CR 级验收规格）是最上游的需求来源。这带来一个真实痛点：

- **CR 是变更视角，天然碎片化**。人要把握"产品现在长什么样"，得翻一堆 CR 自己拼，反人类。
- **缺一个稳定、完整、给人看的产品全貌层**用于规划和评审。

PRD 层就是补这个缺口：**给人一页纸看懂整个产品意图**。

## 核心设计原则

### 1. 两层分工：PRD 给人看意图，派生规格给机器验执行

```
docs/PRD.md（意图，给人看全貌，带稳定锚点和结构化字段，仅人工维护）
      │  Spec Agent 切片
      ▼
acceptance-spec.md（执行，厚，给机器验，带 ID/schema/负例/Do-Not-Touch）
```

- PRD 可以保留稳定的 `PRD-*` 锚点、`REQ-*` 功能 ID、范围、依赖、来源、业务不变式和粗粒度 `AC-*` 索引；这些是产品意图的结构化表达，不是实现代码契约。
- 字段 schema、接口契约、完整测试步骤、任务证据和禁改清单仍归 acceptance-spec；避免在两层重复维护实现细节。
- **AI 干活读的是派生规格，不是自由解释 PRD**。Spec Agent 必须从 PRD 生成 acceptance-spec/task-map，并记录 PRD 版本与锚点哈希。

### 1.1 派生物同步不变量

PRD 是唯一产品意图来源，派生物不得被人工当作第二份需求维护：

```text
PRD.md → acceptance-spec.md + task-map.yml + prd-manifest.yml → CR snapshot
```

- 每个派生物记录 `prd_id`、`prd_version` 和锚点哈希。
- PRD 锚点变化后，受影响派生物必须重新生成或标记 `STALE`。
- `STALE` 的 CR 不得继续进入开发门禁，除非人工确认差异。
- `prd_validate.py` 校验 PRD 结构；SpecGate 校验派生规格；DriftCheck 校验两者是否一致。

### 2. PRD 是「意图」的唯一来源，不是「实现真相」的唯一来源

真相有两个：意图（PRD）和现实（code + test）。PRD 只对前者负责。把它叫"single source of truth"会诱导它去描述"已经实现了什么"，从而和现实 drift。精确表述：**PRD = 产品意图唯一来源；门禁体系负责让意图↔实现持续对齐。**

### 3. CR 从 PRD 派生，用 derived_from 回指

每个 `acceptance-spec.md` 顶部声明：

```yaml
derived_from:
  prd_section: PRD-XXX    # 派生自哪个功能锚点
  prd_hash: <hash>        # 派生时该锚点的内容哈希
```

锚点 `[PRD-XXX]` 写在 PRD 标题里、**只增不改**（改 ID 等于换锚点，挂载的 CR 全部失联）；废弃标 `(已废弃)`，ID 保留。

### 4. 不一致 = 强制对账，不是静默硬 block

PRD 锚点被改后哈希失配，说明两者之一过期了——**但不预设是谁的错**：

- PRD 改了 CR 没跟上 → 改 CR
- 开发中发现 PRD 想错了 → 改 PRD
- 有意的临时偏离 → 记入 `docs/decisions.md`

所以 `drift_check.py` / `specgate.py` 把失配判为 **NEED_HUMAN_DECISION（三选一）**，而不是硬 block。硬 block 会逼死"开发中发现 PRD 错了"的正常情况，也会让人养成绕过 PRD 的习惯，PRD 反而更快烂掉。机器只做两件：发现不一致、挡住开发；决策权留给人。

### 5. 拆分是 Spec Agent 的职责，SpecGate 只检查

SpecGate 是只读门禁（判 PASS/BLOCKED），**不生产 CR**。把 PRD 切成 CR 是 Spec Agent 的活。让门禁兼任拆分 = 运动员兼裁判。

### 6. 单文件原则

始终只用 `docs/PRD.md` 单文件，**不拆 `docs/prd/` 目录**——两者并存会制造双源，与"唯一来源"自相矛盾。产品很大时靠锚点 ID 前缀分层（`[PRD-AUTH]` / `[PRD-AUTH-SSO]`），不拆文件。

### 7. 老项目渐进式放宽

老项目没有 PRD。scan/逆向流程可生成 `status: reverse-engineered` 的锚点骨架（现状快照，非确认意图）。这类锚点失配**仅警告不阻断**；人在后续 CR 中把它确认为 `confirmed` 后，才启用强制对账。**不要求开工前补全整个 PRD**——"碰到哪块、养哪块"。

## 哈希机制的关键边界

- **哈希范围 = 单个锚点章节**（`## [PRD-XXX]` 到下一个 `##`）。改第一部分叙事不触发任何对账。
- **排除「关联 CR」行**：该行由 writeback-agent 自动回填，计入哈希会自触发对账死循环。
- 因此：人写的「意图」参与哈希，机器回填的「索引」不参与哈希——人改意图才触发对账，机器回填不会自触发。

## 与现有逆向能力的关系

v5.3.0 已有的 `reverse_to_spec` / `reverse_spec_gate` / `confirm_reverse_spec`（从代码逆向到 spec + 真需求/bug 人工裁决）**保留不动**，它在执行严谨性上很考究。PRD 层是叠加在其**之上**的"给人看全貌 + 变更一致性追踪"层，两者互补，不替代。

## 落地清单（v5.4.0）

| 组件 | 文件 |
|---|---|
| PRD 模板 | `docs/PRD.md` |
| CR 回指 | `change-requests/CR-TEMPLATE/acceptance-spec.md` 的 `derived_from` |
| PRD↔CR 对账 | `scripts/drift_check.py` |
| 门禁集成 | `scripts/specgate.py` 检查 9（warning-first） |
