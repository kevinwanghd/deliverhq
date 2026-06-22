# RN / Figma 可选适配指南

> **可选适配层**。DeliverHQ 核心门禁（SpecGate / ArchitectureGate / DesignGate /
> direct-read-audit / visual-audit / QualityGate）是**技术栈与设计工具无关**的。
> 本指南只在做 React Native + Figma 时套用；其他技术栈（Flutter / 原生 / Web）
> 各自映射，不影响核心流程。

## 何时用本指南
- 技术栈 = React Native（含团队 ZRN UI 组件库）
- 设计源 = Figma（有 nodeId / 样式属性可直读）
- 其余情况：核心门禁照常，只是元素映射换成对应平台

## 一、Figma → RN 元素映射（实现蓝本适配）
| Figma / Web | RN / ZRN UI |
|---|---|
| div / frame | View |
| text | Text |
| img | Image |
| button-like frame | ZRN Button 或 Pressable |
| CSS flex | RN flexbox（flexDirection/justifyContent/alignItems） |
| box-shadow | 拆平台策略：iOS shadow* / Android elevation |
| CSS gap | RN gap 或手动 margin |

## 二、组件复用核查（ZRN UI）
复用 ZRN 组件前核查：
- props（参数）与默认状态
- Web / Harmony 可用性
- 样式覆盖方式（style / 主题 token）
- 是否已有等价组件，避免重复造

## 三、直读审计适配（direct-read-audit 的 RN 落法）
四元组「node_id → 属性 → raw_value → 代码映射」中，RN 映射示例：
| Figma 属性 | raw_value | RN 写法 |
|---|---|---|
| fill | #1A73E8 | `color: '#1A73E8'` |
| fontSize | 16 | `fontSize: 16` |
| cornerRadius | 8 | `borderRadius: 8` |
| itemSpacing | 12 | `gap: 12` |
| strokeWeight | 1 | `borderWidth: 1` |
| effect(shadow) | … | iOS: shadowColor/Offset/Opacity/Radius；Android: elevation |
| imageRef | asset | `<Image source={require(...)} />` |

> 截图只用于最终校准，不作首要编码来源；缺 Figma 产物时 blocked，不凭截图手写。

## 四、资源处理
按资源映射 asset mapping 分类：图标 / 位图 / 多倍图（@2x/@3x）/ 矢量。
导出后落到项目资源目录，代码引用 require 或 Image source，不用占位图。

## 五、实现顺序（稳定）
1. types.ts（类型）
2. api.ts（接口封装）
3. hooks/state（状态逻辑）
4. leaf components（子组件）
5. page container（页面容器）
6. route / web registration（native route + web route 注册）
7. tracking / logging（埋点 routeList + 日志）

## 六、路由与埋点
- native route：客户端路由注册
- web route：网页路由注册（如需 Web 复用）
- 埋点 routeList：页面埋点清单，新页面必须登记

## 与核心门禁的对应
| 核心环节（工具无关） | 本指南提供的 RN/Figma 适配 |
|---|---|
| ArchitectureDesign 的「设计分块到实现映射」 | block → RN 组件/文件 |
| direct-read-audit 四元组 | Figma 属性 → RN 写法（第三节） |
| Dev Agent 证据驱动实现 | 实现顺序（第五节）+ ZRN 复用核查 |
| visual-audit 偏差回流 | 对照 Figma 截图校准，回流修 RN 样式 |

> 本指南可整体替换为 Flutter / 原生 / Web 的对应映射，核心门禁不变。
