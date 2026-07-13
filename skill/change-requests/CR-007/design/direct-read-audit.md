# 直读审计 (direct-read-audit): 统一入口、验证闭环与记忆生命周期基础

> UI 编码前产出。每个关键视觉常量必须可追溯到设计源原始值，杜绝"凭截图臆测样式"。
> 设计源可为 Figma / Sketch / XD / 任意设计工具；下方以通用四元组记录。
> 截图只用于最终校准，不作为首要编码来源。缺设计源产物时 blocked，禁止凭截图手写 UI。

## CR-ID
CR-007

## 设计源
> 工具与文件：{{Figma 文件 / Sketch / 其他}}；产物清单是否齐全（metadata / raw node / 资源映射）。

## 四元组追溯表（设计节点 → 属性 → 原始值 → 代码映射）
> 每个视觉常量一行。raw_value 必须来自设计源直读，不是截图取色/估算。

| 视觉项 | node_id（设计节点） | 属性名 | 原始值 raw_value | 代码映射（RN/CSS/其他） |
|---|---|---|---|---|
| 颜色-主色 | {{node_id}} | fill | {{#RRGGBB}} | {{color: '#RRGGBB'}} |
| 字号 | {{node_id}} | fontSize | {{16}} | {{fontSize: 16}} |
| 圆角 | {{node_id}} | cornerRadius | {{8}} | {{borderRadius: 8}} |
| 间距 | {{node_id}} | itemSpacing | {{12}} | {{gap: 12}} |
| 边框 | {{node_id}} | strokeWeight | {{1}} | {{borderWidth: 1}} |
| 阴影 | {{node_id}} | effect | {{...}} | {{平台策略}} |
| 图片资源 | {{node_id}} | imageRef | {{asset 路径}} | {{require/Image source}} |

## 必查视觉常量清单（缺则补齐或标 blocked）
- [ ] 颜色（fill / 文本色 / 背景色）
- [ ] 字号 / 字重 / 行高
- [ ] 圆角
- [ ] 间距（内外边距 / 元素间距）
- [ ] 边框
- [ ] 阴影（按平台策略拆分）
- [ ] 图片 / 图标资源（按资源映射处理，非占位图）

## 审计判定
- 所有关键视觉常量四元组齐全 → 可进入 UI 编码
- 缺设计源原始值 → blocked，回推需求/设计补齐，禁止凭截图手写

**直读审计状态**：DRAFT / READY / BLOCKED
