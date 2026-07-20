# Acceptance Spec: {{CR_NAME}}

> 由 Spec Agent 产出。将 `request.md` 转化为可测试的验收规格（SDD 三段式）。

## CR-ID
{{CR_ID}}

## Spec Manifest

```yaml
schema: deliverhq-acceptance-spec
schema_version: 2
cr_id: {{CR_ID}}
status: draft
prd_id: {{PRD-ID}}
prd_version: {{PRD-VERSION}}
derived_from: [{{PRD-XXX}}]
owner: {{研发负责人}}
target_platforms: [{{platform}}]
business_logic_authority: backend
client_role: pure_ui_and_result_rendering
unresolved_questions_block_dev: true
```

## Scope Contract

### In Scope

- {{本 CR 必须实现的范围}}

### Out of Scope

- {{本 CR 明确不实现的范围}}

### Do Not Touch

- {{不可修改的模块、接口、数据或行为}}

### Source Evidence

| Evidence ID | 来源 | 定位 | 说明 |
|---|---|---|---|
| SRC-001 | {{PRD/原型/截图/代码}} | {{链接、页面或路径}} | {{支持的需求结论}} |

## Requirement Traceability

| REQ ID | PRD Anchor | AC IDs | DEV Task | QA Task | Status |
|---|---|---|---|---|---|
| REQ-XXX | PRD-XXX | AC-XXX-01, AC-XXX-02 | DEV-XXX | QA-XXX | planned |

## 来源锚点（derived_from）

> 本 CR 派生自 `docs/PRD.md` 的哪个功能锚点。PRD 是产品意图唯一来源,本 spec 是它的可执行切片。
> 全新能力若无对应锚点,先在 PRD 新增锚点再回填。`prd_hash` 由 drift_check.py 用于 PRD↔CR 对账。

```yaml
derived_from:
  prd_section: {{PRD-XXX}}   # 派生自的 PRD 锚点 ID
  prd_hash: {{hash}}         # 派生时该锚点的内容哈希(不含「关联 CR」行)
```

## 1. Data Spec（数据规格）

### Entities（实体）
| 实体名 | 说明 | 关键字段 |
|--------|------|----------|
| {{Entity}} | {{说明}} | {{字段列表}} |

### Fields & Constraints（字段与约束）
| 实体.字段 | 类型 | 约束 | 默认值 | 说明 |
|-----------|------|------|--------|------|
| {{Entity.field}} | {{type}} | {{NOT NULL / UNIQUE / FK}} | {{value}} | {{说明}} |

### State Transitions（状态转换）
| 实体 | 初始状态 | 允许转换 | 触发条件 | 终态 |
|------|----------|----------|----------|------|
| {{Entity}} | {{state}} | {{state1→state2}} | {{条件}} | {{state}} |

### Data Invariants（数据不变式）
- {{必须始终为真的条件，例如：订单金额 = sum(订单项金额)}}
- {{例如：用户余额 ≥ 0}}

---

## 2. Interface Spec（接口规格）

### API Signature
| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| {{API名}} | {{GET/POST/PUT/DELETE}} | {{/api/v1/resource}} | {{功能说明}} |

### Input Schema
```json
{
  "field1": "type (required/optional)",
  "field2": "type (required/optional)"
}
```

### Output Schema
```json
{
  "success": true,
  "data": {},
  "error": null
}
```

### Error Codes
| 错误码 | HTTP状态 | 说明 | 客户端处理 |
|--------|----------|------|------------|
| {{ERR_001}} | {{400}} | {{参数错误}} | {{提示用户}} |

### Idempotency & Side Effects
- **幂等性**：{{是否幂等，如何实现}}
- **副作用**：{{是否有副作用，例如：发送邮件、扣款}}

### Permission Requirements
| 接口 | 需要权限 | 验证方式 |
|------|----------|----------|
| {{API}} | {{role/permission}} | {{JWT/Session}} |

---

## 3. Behavior Spec（行为规格）

### 场景 1：{{正常流程}}
- **Given** {{可量化的前置条件，例如：用户余额 100 元}}
- **When** {{操作，例如：购买 50 元商品}}
- **Then** {{可测试的结果，例如：余额变为 50 元，订单状态为 pending}}
- **Measurable Success** {{具体指标，例如：API 响应时间 < 200ms，成功率 > 99%}}

### 场景 2：{{异常流程}}
- **Given** {{前置条件，例如：用户余额 30 元}}
- **When** {{操作，例如：购买 50 元商品}}
- **Then** {{预期结果，例如：返回错误码 ERR_INSUFFICIENT_BALANCE，余额不变}}
- **Measurable Success** {{错误提示清晰，用户可理解}}

### 场景 3：{{边界情况}}
- **Given** {{边界条件，例如：用户余额恰好 50 元}}
- **When** {{操作，例如：购买 50 元商品}}
- **Then** {{预期结果，例如：成功购买，余额变为 0}}
- **Measurable Success** {{边界值处理正确}}

### Client/Server Responsibility

| 行为 | 服务端责任 | Flutter/客户端责任 | 禁止客户端自行判断 |
|---|---|---|---|
| {{奖励/任务/状态行为}} | {{规则、状态、结果、错误码}} | {{纯 UI、交互、结果渲染}} | {{奖励、次数、CD、跨日、资格等}} |

### Observable Events

| Event ID | 事件名 | 触发条件 | 必填字段 | 责任方 |
|---|---|---|---|---|
| EVT-001 | {{event_name}} | {{明确条件}} | {{字段}} | backend / flutter |

---

## 非功能验收

| 维度 | 指标 | 验收标准 |
|---|---|---|
| 性能 | 响应时间 | P95 < {{X}} ms |
| 性能 | 吞吐量 | > {{Y}} QPS |
| 可用性 | SLA | {{Z}}% |
| 安全 | 鉴权 | 所有接口需 token 验证 |
| 数据 | 完整性 | 关键链路事务保护 |

---

## 依赖项

| 依赖 | 类型 | 状态 | 责任人 |
|---|---|---|---|
| {{外部系统/API}} | 外部 | {{已就绪/待确认}} | {{负责人}} |
| {{基础设施}} | 内部 | {{已就绪/待确认}} | {{负责人}} |

## 任务拆分与交付顺序

| Task ID | 角色 | 目标 | Covers | Depends On | Done Evidence |
|---|---|---|---|---|---|
| DEV-XXX | backend / flutter / qa | {{任务目标}} | {{REQ/AC}} | {{任务 ID}} | {{接口、截图、测试报告等}} |

---

## 模糊点与待确认项

> Spec Agent 识别出的需求不明确之处，需人工澄清。
>
> **起草期标记约定**（借 Spec-Kit）：仍未澄清的点，可临时用 `[NEEDS CLARIFICATION: 问题]`
> 或 `[待确认]` 行内标注。**SpecGate 放行前这些标记必须全部清零**——它们与 `[TODO]` 同级阻断。
> 正文叙述里提到"待确认"三个字不阻断（只检查显式占位符标记）。

### Facts（已确认事实）
> 从需求文档、现有系统、架构文档中确认的客观事实

| # | 事实 | 来源 | 确认人 | 日期 |
|---|------|------|--------|------|
| F1 | {{已确认的客观事实}} | {{来源：需求文档/架构文档/现有系统}} | {{确认人}} | {{日期}} |

### Assumptions（假设前提）
> AI 为推进实现而做出的合理假设，需标注为假设而非事实

| # | 假设 | 风险级别 | 验证方式 | 验证期限 | 状态 |
|---|------|----------|----------|----------|------|
| A1 | {{假设的前提条件}} | {{P0/P1/P2}} | {{如何验证}} | {{日期}} | {{pending/verified/rejected}} |

### Open Questions（待确认问题）
> 需求不明确之处，阻碍实现或影响决策的问题

| # | 问题 | 阻断级别 | 负责人 | 截止日期 | 状态 |
|---|------|----------|--------|----------|------|
| Q1 | {{不明确的需求点}} | {{P0/P1/P2}} | {{负责人}} | {{日期}} | {{open/resolved}} |
| Q2 | {{边界条件未定义}} | {{P0/P1/P2}} | {{负责人}} | {{日期}} | {{open/resolved}} |

---

## 可测试性

- [ ] 每个验收条件可自动化测试
- [ ] 边界条件可重现
- [ ] 性能指标可量化验证
- [ ] 数据约束可验证
- [ ] 接口契约可验证

---

## SpecGate 检查点

- [ ] Data Spec 完整（实体、字段、约束、状态转换）
- [ ] Interface Spec 完整（API、Input/Output、错误码、权限）
- [ ] Behavior Spec 完整（至少 3 个场景：正常/异常/边界）
- [ ] 验收条件明确，无 `[待确认]` 占位符
- [ ] P0 Open Questions 已解决（status = resolved）
- [ ] P0 Assumptions 已验证（status = verified）
- [ ] 无模糊词（尽快/合理/优化/良好体验/高性能/稳定/友好/智能/自动/适当）或已量化
- [ ] 依赖项状态已确认
- [ ] 非功能需求已量化

**SpecGate 状态**：DRAFT / READY / BLOCKED
