# Context Summary: CR-001

> 由 Context Agent 产出。滑动窗口机制：最多携带 2 个阶段全文，阶段切换时必须更新本摘要。

## Current Phase
{{当前阶段，如 implementation / test / quality}}

## Completed Phases

### Spec (已完成)
- 核心功能：{{3 句话概括}}
- 关键验收条件：{{最重要的 2-3 条}}
- 已解决的模糊点：{{简要列举}}

### Design (已完成，如有)
- 设计方案：{{架构/UI 设计要点}}
- 关键决策：{{技术选型、权衡}}

## Key Decisions

| # | 决策 | 原因 | 影响范围 |
|---|---|---|---|
| 1 | {{技术选型/架构决策}} | {{rationale}} | {{哪些模块}} |
| 2 | {{边界划定}} | {{rationale}} | {{范围}} |

## Open Issues

| # | 问题 | 阻断级别 | 负责人 | 状态 |
|---|---|---|---|---|
| 1 | {{待解决问题}} | P0/P1/P2 | {{name}} | open / resolved |

## Risks

| # | 风险 | 影响 | 缓解措施 |
|---|---|---|---|
| 1 | {{潜在风险}} | {{后果}} | {{如何应对}} |

## Loaded Context

当前阶段全文加载：
- {{当前阶段文档列表，如 implementation-plan.md / test-plan.md}}

上一阶段全文加载：
- {{上一阶段文档列表}}

## Compressed Context

更早阶段（仅保留摘要）：
- Spec 阶段：见上方"Completed Phases > Spec"
- Design 阶段：见上方"Completed Phases > Design"

## Next Phase Input

进入下一阶段需要的关键信息：
- {{传递给下游的核心上下文}}
- {{未完成项/待办事项}}

---

**ContextWindowGate 检查**：
- [ ] 当前 + 上一阶段全文已加载
- [ ] 更早阶段已压缩为摘要
- [ ] 关键决策已记录
- [ ] Open Issues 已跟踪

**更新频率**：每次阶段切换（Spec → Dev / Dev → Test / Test → Quality）时必须更新。
