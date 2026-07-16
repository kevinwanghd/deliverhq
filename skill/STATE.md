# DeliverHQ STATE（机器维护，每轮必读）

> 由 `handoff_state.py` 从各 CR 的 state.yml 汇总刷新。
> 统一不变式：**done = 建出来的 = 计划的 = 决定的**。声明完成但证据不闭合 → fail-closed。

| CR | lane | phase | state | 下一道门 | needs_human |
|---|---|---|---|---|---|

_（尚无活跃 CR。创建首个 CR 后由 `handoff_state.py` 自动刷新本表。）_
