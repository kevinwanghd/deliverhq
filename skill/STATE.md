# DeliverHQ STATE（机器维护，每轮必读）

> 由 `handoff_state.py` 从各 CR 的 state.yml 汇总刷新。
> 统一不变式：**done = 建出来的 = 计划的 = 决定的**。声明完成但证据不闭合 → fail-closed。

| CR | lane | phase | state | 下一道门 | needs_human |
|---|---|---|---|---|---|
| CR-004 | standard | writeback | archived | - | 否 |
| CR-005 | standard | writeback | archived | - | 否 |
| CR-006 | high-risk | writeback | archived | - | ⚠ 是 |
| CR-007 | high-risk | writeback | archived | - | ⚠ 是 |
| CR-BLOCKED-EXAMPLE | standard | dev | blocked | writeback | 否 |
| CR-EXAMPLE | standard | writeback | archived | - | 否 |

**阻塞原因**：
- CR-BLOCKED-EXAMPLE：缺少 writeback-report.md，Writeback Agent 未执行
