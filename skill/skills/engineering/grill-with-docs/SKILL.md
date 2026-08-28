---
name: grill-with-docs
description: 用文档约束的规则烤问需求/设计。适用：验收规格（acceptance-spec）生成前、设计决策未定案时。用项目已有规则/CONTEXT.md/PRD.md 约束烤问方向，不用外部规则。
disable-model-invocation: true
argument-hint: "What do you want to grill? A spec, a design, a plan?"
---

# Grill with Docs — 文档约束式烤问

把"需求/设计澄清"从口头散漫变成显式可审计的工件。
用项目已有文档（PRD / acceptance-spec / CONTEXT.md）作为烤问边界，
不凭空问，不问偏离项目语境的假设问题。

## 与普通 grilling 的区别

- `grill-me`：通用、无约束，用户说什么就烤什么
- `grill-with-docs`：文档约束，从项目的 `docs/PRD.md` / `acceptance-spec.md` / `CONTEXT.md` 中提取上下文，烤问更精准

## 何时用

- 生成 `acceptance-spec.md` 之前，需求还有歧义
- 设计决策（`designgate`）未定案，需要逼出明确选择
- 实施计划（`implementation-plan.md`）有逻辑漏洞

## 流程

### 1. 收集上下文

读：
- `docs/PRD.md`（产品意图）
- 当前 CR 的 `acceptance-spec.md`（如已有）
- `docs/CONTEXT.md`（项目词汇）
- 当前 CR 的 `request.md`

### 2. 识别歧义点

从 request 和 spec 中提取：
- 模糊词：`可能`、`大概`、`优化`、`改进`
- 歧义边界：没有明确说「不做」的场景
- 未引用 PRD 锚点：功能没有 `[PRD-XXX]` 标签
- 缺少 AC：验收条件（Acceptance Criteria）不完整

### 3. 一次一问

**原则**：
- 不能一口气抛 5 个问题
- 每问给推荐答案（不能只问不给方向）
- 能查代码就不问人

**典型问题模板**（按阶段调整）：

```
Q1: 这个功能解决的核心问题是什么？
   → 推荐：参考 PRD.md 的「问题陈述」格式

Q2: 成功的可验证标准是什么？
   → 推荐：写成「当 [条件]，则 [结果]」格式（Given/When/Then）

Q3: 边界在哪里？哪些明确不做？
   → 推荐：列举至少 3 个「不做」场景

Q4: 失败时的降级方案是什么？
   → 推荐：引用现有代码模块，不要凭空设计

Q5: 谁来验证？（人/自动化？）
   → 推荐：对应到 QualityGate 的 test_command
```

### 4. 产出工件

写入 CR 的 `request-clarifications.md`：

```markdown
# Request Clarifications

此文件由 `grill.py` + grill-with-docs 生成。

## Q1: [问题]
**推荐答案**: [方向]
**来源**: [引用 PRD/spec 的哪段]

## Q2: ...
```

### 5. 与 SpecGate 对接

Grilling 结果供 Spec Agent 生成更精准的 acceptance-spec。
`request-clarifications.md` 的每条 Q&A 必须能回溯到 PRD 锚点。
