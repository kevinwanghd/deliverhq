# DeliverHQ Quality Gates 详解

## 概览

| Gate | 检查对象 | 阻断条件 | 脚本 |
|---|---|---|---|
| SpecGate | acceptance-spec.md | 模板变量/模糊点未解决 | `specgate.py` |
| DesignGate | design/ 目录 | C端缺高保真/缺原型 | `designgate.py` |
| ContextWindowGate | context-summary.md | 携带超过2阶段全文 | `context_window_check.py` |
| pre_dev_gate | CR 文档完备性 | 缺少必要文档 | `pre_dev_gate.py` |
| QualityGate | quality-report.md | P0未通过/覆盖率不足 | `qualitygate.py` |
| WritebackGate | writeback-report.md | 知识未沉淀 | `writeback_gate.py` |

---

## SpecGate

**目的**：确保验收规格可测试、无歧义

**检查项**：
1. 无模板变量 `{{}}`
2. 无未解决模糊点（表格中无 `pending` / `待确认` 状态）
3. 至少 3 个验收场景（主流程 + 异常 + 边界）
4. 非功能需求有量化指标

**通过条件**：所有检查项 PASS

**失败处理**：Spec Agent 修复后重新运行

---

## DesignGate

**目的**：确保 UI 设计产物完备

**检查项**：
1. `metadata.yml` 存在且 `ui_type` 字段有效
2. 根据 ui_type 检查必要文件：
   - `c-end`：必须有 hi-fi-spec.md + prototype.html
   - `b-end`：必须有 lo-fi-spec.md
   - `api-only`：自动 PASS（跳过设计检查）
   - `hybrid`：lo-fi + hi-fi 均需要
3. 设计稿无模板变量

**通过条件**：ui_type 对应的文件齐全

**失败处理**：Design Agent 补全设计产物

---

## ContextWindowGate

**目的**：控制上下文滑动窗口，防止上下文爆炸

**检查项**：
1. `context-summary.md` 存在
2. 包含必要章节（中文或英文标题均可）：
   - Current Phase / 当前阶段
   - Completed Phases / 已完成阶段
   - Key Decisions / 关键决策
3. 已完成阶段压缩为摘要（非全文）

**通过条件**：结构完整，摘要长度合理

**失败处理**：Context Agent 更新摘要

---

## pre_dev_gate

**目的**：开发前的文档完备性检查

**检查项**：
1. `acceptance-spec.md` 存在且非空
2. `context-summary.md` 存在
3. 无模板变量残留
4. 如有 UI（metadata.yml ui_type ≠ api-only）：设计文件存在

**通过条件**：所有必要文档齐全

**失败处理**：Dev Agent 拒绝开发，提醒人类补全文档

---

## QualityGate

**目的**：代码质量门禁

**检查项**：
1. `quality-report.md` 存在
2. P0 测试通过率 = 100%
3. 整体测试覆盖率 ≥ 80%
4. 无 Critical 级别告警

**通过条件**：P0 全通过 + 覆盖率达标

**失败处理**：
- 自动记录失败原因到 `docs/mistake-book.md`（可通过环境变量 `DELIVERHQ_AUTO_MISTAKE_BOOK=0` 禁用）
- Quality Agent 标记需修复项

---

## WritebackGate

**目的**：确保知识沉淀完整

**检查项**：
1. `writeback-report.md` 存在且非空
2. `traceability.yml` 已更新（需求→代码映射）
3. 架构决策已记录到 `docs/decisions.md`（如有）
4. 新规则已沉淀到 `docs/rules.md`（如有）

**通过条件**：知识沉淀完整

**失败处理**：Writeback Agent 补全归档

---

## Gate 执行时机

```
Spec Agent 产出 acceptance-spec.md
  → 运行 SpecGate
    → PASS → Design Agent（如有 UI）/ Context Agent

Design Agent 产出 design/*
  → 运行 DesignGate
    → PASS → Context Agent

Context Agent 产出 context-summary.md
  → 运行 ContextWindowGate
    → PASS → Dev Agent

Dev Agent 准备开发
  → 运行 pre_dev_gate
    → PASS → 开始编码

Quality Agent 产出 quality-report.md
  → 运行 QualityGate
    → PASS → Writeback Agent

Writeback Agent 产出 writeback-report.md
  → 运行 WritebackGate
    → PASS → Memory Agent 归档
```

---

## 环境变量控制

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DELIVERHQ_AUTO_MISTAKE_BOOK` | `1` | QualityGate 失败时是否自动写入错题本 |
| `DELIVERHQ_STRICT_MODE` | `0` | 严格模式：所有 Gate 必须 PASS 才能继续 |
