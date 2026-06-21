# DeliverHQ 四职能最小模式

> DeliverHQ 文档中列出多个 Agent，是为了说明职责边界；实际落地时不要求同时启动 9/10 个 Agent。
> 最小可按四类职能理解：Research / Context、Design / Spec、Build / Dev、Review / Verify。

## 为什么需要四职能视角

多 Agent 的关键不是角色数量，而是闭环是否完整。DeliverHQ 的核心目标是确保每次交付都有：

1. 明确事实来源
2. 可测试规格
3. 有边界的实现
4. 独立验证和证据

因此，小团队或个人使用时，可以把多个 Agent 合并为四类职能，而不是机械模拟完整组织架构。

## 四职能映射

| 四职能 | 对应 DeliverHQ 角色 | 核心产物 | Gate / 证据 |
|---|---|---|---|
| Research / Context | Context Agent、Scan Agent | `context-summary.md`、扫描报告 | ContextWindowGate、legacy scan evidence |
| Design / Spec | Spec Agent、Design Agent | `acceptance-spec.md`、`design/*` | SpecGate、DesignGate |
| Build / Dev | Dev Agent、Test Agent | 代码、`implementation-plan.md`、`test-plan.md`、`traceability.yml` | PreDevGate、DevPhase handoff |
| Review / Verify | Review Agent、Quality Agent、Writeback Agent、Memory Agent | `review-report.md`、`quality-report.md`、`writeback-report.md` | ReviewGate、QualityGate、WritebackGate |

## 最小落地方式

### 1. 先保证 Design / Spec

没有 `acceptance-spec.md` 不进入开发。SpecGate 是最小硬门禁。

### 2. Build / Dev 不自动越过人工开发点

`dev_phase.py` 只做交接，不自动写代码、不自动进入 Review。实现完成后再显式运行 ReviewGate / QualityGate。

### 3. Review / Verify 必须独立

实现者不能自己验收自己。ReviewGate 至少要检查：

- 验收条件是否逐项审查
- traceability 是否覆盖 changed files
- test-plan 和 verification-manifest 是否存在
- Adversarial Checks 是否覆盖删测试、降阈值、绕 Gate、happy path only、边界遗漏

### 4. Writeback 是交付结束条件

如果交付产生新规则或踩坑，先写入 `docs/rules-candidates.md` 或 `docs/mistake-book.md`，再由人工决定是否晋升到 `docs/rules.md`。

## 不建议做什么

- 不要为了“像公司”而新增更多 Agent。
- 不要把 workflow_router 接成自动拦截器或自动创建 CR 的后台服务。
- 不要让 loop 自动发布、自动合并或无限重试。
- 不要在没有 evidence schema 和 Gate 契约前做 Dashboard。

## 判断标准

一个 DeliverHQ 流程是否够用，不看 Agent 数量，而看四个问题：

1. 事实来源是否清楚？
2. 规格是否可测试？
3. 实现是否有边界和 traceability？
4. 验证是否独立且有证据？

四个问题都能回答，才进入下一阶段。
