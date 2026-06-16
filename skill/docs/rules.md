# DeliverHQ Rules

> 通用门禁规则 + 项目扫描沉淀的规则。`verified` 默认阻断，`proven` 硬阻断。

## 通用规则
| # | Rule | Gate | Maturity | Detection | Source |
|---|---|---|---|---|---|
| 1 | 文档不完备不开发 | P0 | verified | specgate | DeliverHQ v4.5 |
| 2 | 所有用户输入必须验证 | P0 | draft | static | OWASP |
| 3 | 敏感信息不硬编码 | P0 | draft | static | OWASP |
| 4 | C 端 UI 必须有高保真设计稿 | P0 | verified | designgate | DeliverHQ v4.5 |
| 5 | B 端 UI 必须有低保真设计稿 | P1 | verified | designgate | DeliverHQ v4.5 |
| 6 | 阶段切换必须更新 context-summary.md | P1 | verified | context-window-gate | DeliverHQ v4.5 |
| 7 | 所有 AI 生成的新规则或规则修改建议必须先写入 `docs/rules-candidates.md`，不得直接写入 `docs/rules.md` | P1 | draft | manual | Promoted from CR-EXAMPLE |
