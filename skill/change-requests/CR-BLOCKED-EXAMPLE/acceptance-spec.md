# Acceptance Spec: 故意包含错误的规格

> **警告**：这是反例文档，包含多种错误用于测试 SpecGate

## CR-ID
{{CR_BLOCKED_EXAMPLE}}

## 1. Data Spec（数据规格）

### Entities（实体）
| 实体名 | 说明 | 关键字段 |
|--------|------|----------|
| {{Entity}} | {{说明}} | {{字段列表}} |

### Fields & Constraints（字段与约束）
[待确认] 字段约束尚未定义

---

## 2. Interface Spec（接口规格）

### API Signature
需要尽快设计接口，保证高性能和良好体验。

---

## 3. Behavior Spec（行为规格）

### 场景 1：正常流程
- **Given** 用户已登录
- **When** 用户点击按钮
- **Then** 系统响应合理快
- **Measurable Success** 体验良好

---

## 模糊点与待确认项

### Facts（已确认事实）
| # | 事实 | 来源 | 确认人 | 日期 |
|---|------|------|--------|------|
| F1 | {{未填充}} | - | - | - |

### Assumptions（假设前提）
| # | 假设 | 风险级别 | 验证方式 | 验证期限 | 状态 |
|---|------|----------|----------|----------|------|
| A1 | 假设系统能自动优化性能 | P0 | [待确认] | 2026-06-20 | pending |

### Open Questions（待确认问题）
| # | 问题 | 阻断级别 | 负责人 | 截止日期 | 状态 |
|---|------|----------|--------|----------|------|
| Q1 | 是否支持并发访问？ | P0 | Kevin | 2026-06-15 | open |
| Q2 | 性能目标是多少？ | P0 | Sarah | 2026-06-15 | open |

---

## SpecGate 检查点

预期此文档会被 SpecGate 阻断，因为：
- ✗ 包含模板变量 `{{CR_BLOCKED_EXAMPLE}}`
- ✗ 包含 `[待确认]` 占位符
- ✗ 存在 P0 Open Questions (status=open)
- ✗ 存在 P0 Assumptions (status=pending)
- ✗ 包含模糊词（尽快/合理/高性能/良好体验/自动优化）但无量化指标

**SpecGate 状态**：应该 BLOCKED
