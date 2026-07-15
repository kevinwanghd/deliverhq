# Human Decisions: CR-007

| # | Issue | Decision | Decision By | Date |
|---|---|---|---|---|
| 1 | 是否开始按分析建议优化 | 开始实施，优先 P0 | 用户 | 2026-07-13 |
| 2 | 是否新增 Gate | 不新增 Gate，优化现有入口与证据链 | 用户授权范围内的既定建议 | 2026-07-13 |
| 3 | 默认是否自动推进 CR | 默认只读，未来写操作必须显式 opt-in | Codex，基于安全边界 | 2026-07-13 |
| 4 | 本次实现文件权限 | 用户已明确要求优化 DeliverHQ 项目，授权修改非 protected 的框架源码与测试；不据此修改 package.json、AGENTS.md、dir-graph.yaml 等 protected 文件 | 用户 | 2026-07-13 |
| 5 | 自检/反钻空子脚本可靠性 | 用户要求按建议开始优化验证闭环；允许修复发布清单取证与 Git UTF-8 解码，但不得降低阈值、跳过检查或改变冻结 Gate 集合 | 用户授权范围内 | 2026-07-13 |
| 6 | 框架 self-development CR 证据 | ReviewGate 仅忽略 `skill/change-requests/` 治理产物，仍逐项核对实际源码与测试；与已支持的 `DeliverHQ/`、`change-requests/` 规则一致 | Codex，基于同类路径契约 | 2026-07-13 |

> “开始优化”是实施授权，不冒充对具体架构的独立人工确认；ArchitectureGate 可保留相应 warning。

## 待决策项

无。
