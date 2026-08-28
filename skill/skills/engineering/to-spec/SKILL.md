---
name: to-spec
description: 把对话合成验收规格。不做访谈，只综合已有信息。适用：PRD 锚点 [PRD-XXX] 需要生成 acceptance-spec.md，或 CR 的 request.md 已清晰时直接派生 spec。调用 specgate 验证格式完备性。
disable-model-invocation: true
argument-hint: "What feature or change should become a spec?"
---

# To Spec — 从对话合成 acceptance-spec

从当前对话和代码库理解中生成 `acceptance-spec.md`。
**不做访谈**——只综合已有的信息（request.md / PRD.md / 上下文）。

## 何时用

- CR 的 `request.md` 已填写，需要派生规格
- PRD 锚点 `[PRD-XXX]` 需要落地为可执行规格
- 用户说"帮我写个规格"

## 流程

### 1. 探索代码库

读：
- `docs/CONTEXT.md`（项目词汇）
- `docs/PRD.md`（产品意图锚点）
- `docs/architecture.md`（架构约束）
- 当前 CR 的 `request.md`
- 当前 CR 的 `request-clarifications.md`（如有 grilling 结果）

用项目的领域词汇，不用自己的术语。

### 2. 识别测试 seam

探索现有代码后，确定：
- 哪些公共接口会被影响
- 优先已有 seam，不要新建
- 如果需要新 seam，在最高点建立（越少越好）

和用户确认 seam 是否正确。

### 3. 写 acceptance-spec

格式（DeliverHQ Spec Agent 标准格式）：

```markdown
# acceptance-spec.md — [功能名称]

derived_from{prd_section, prd_hash}

## Problem Statement（问题陈述）
[用户视角的核心问题]

## Solution（解决方案）
[用户视角的解决方案]

## User Stories
1. As an [角色]，I want [功能]，so that [价值]
（详尽枚举，覆盖所有场景）

## Acceptance Criteria（验收条件）
- AC-1: Given [前提]，When [操作]，Then [结果]
- AC-2: ...
（每个 User Story 至少 1 条 AC）

## Implementation Decisions
- 将修改的模块
- 接口变更
- 技术约束
- 架构决策
（不含文件路径，只写决策内容）

## Testing Decisions
- 测哪些模块
- 测什么行为（公共接口，不是私有方法）
- 已有测试先例

## Out of Scope
[明确不做的]

## Further Notes
```

### 4. 运行 SpecGate 验证

```bash
python DeliverHQ/scripts/specgate.py change-requests/CR-XXX/acceptance-spec.md
```

SpecGate 检查：
- 无占位符（`[待确认]` / `{{}}` / `[NEEDS CLARIFICATION]`）
- 所有 AC 可验证（Given/When/Then）
- 有 `derived_from` 引用
- 无模板变量残留

### 5. 写 traceability.yml

```yaml
acceptance-criteria:
  AC-1:
    prd-anchor: PRD-XXX
    test-seams: [module-a, module-b]
    implementation-notes: ...
```

## DeliverHQ 集成

```
request.md → to-spec → acceptance-spec.md → SpecGate → implementation-plan.md → Dev
```

to-spec 的输出是 Spec Agent 的职责，不是 Dev Agent 的职责。
to-spec 完成后，调用 `specgate` 验证格式，然后 Spec Agent 才能进入实施计划阶段。
