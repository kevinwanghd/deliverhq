# 架构对齐报告 (ArchitectureAlignmentReport): {{CR_NAME}}

> 由 code-generator 在实现后输出，证明代码实现与 architecture-design.md 一致。
> 证据驱动：实现必须追溯到需求/接口/设计证据；缺证据的分块标 blocked，不得硬写。

## CR-ID
{{CR_ID}}

## 实现类型
> ListPage / DetailPage / FormPage / Popup / APIOnly / TrackingOnly / Utility / Model（按实际，可多选）

## 1. 文件覆盖
| 架构设计文件落点 | 实际实现文件 | 状态 |
|---|---|---|
| {{path}} | {{path}} | pass / missing / deviated |

## 2. 设计分块对齐（block → 实现）
| block | 目标组件 | 实现状态 | 证据（node_id / 接口字段 / 需求项） |
|---|---|---|---|
| {{block}} | {{Component}} | pass / blocked | {{evidence}} |

## 3. 接口字段对齐
| 接口 | 字段 | 是否按规格实现 | 偏差说明 |
|---|---|---|---|
| {{api}} | {{field}} | yes / no | {{}} |

## 4. 路由与平台（如涉及）
> native route / web route / 埋点 routeList 是否注册；多端差异是否处理。N/A 可写。

## 5. UI 与样式对齐（如涉及）
> 视觉常量是否来自 direct-read-audit（node_id→属性→原始值→代码映射），非截图臆测。

## 6. 埋点 / 日志（如涉及）

## 7. 偏差与待验证项
| 项 | 类型 | 说明 | 处理 |
|---|---|---|---|
| {{}} | deviation / pending | {{}} | 修复 / 待人工决策 |

## 对齐判定
- 关键项全部 pass → 可进入编译验证（build-verifier）
- 存在 missing → 最多回流补全 5 轮；仍无法补齐则 blocked（禁止硬写绕过）
- 存在需人工决策的 deviation → NEED_HUMAN_DECISION

**回流轮次**：{{0}} / 5
**对齐状态**：PASS / BLOCKED / NEED_HUMAN_DECISION
