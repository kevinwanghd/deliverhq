# High-Fidelity Spec: 实现 worktree 隔离机制

> C 端 UI 高保真设计规格。由 Design Agent 产出。**C 端 UI 必须有高保真设计稿，否则 DesignGate 阻断。**

## 设计稿

> 📁 **设计稿存储位置**：将所有设计图片放在 `design/assets/` 目录下，推荐命名：`screen-main.png`、`screen-interaction.png`、`icon-*.svg` 等。

### 主界面
![主界面](./assets/screen-main.png)

### 关键交互状态
![交互状态](./assets/screen-interaction.png)

### 响应式布局（如适用）
- 桌面端：![Desktop](./assets/screen-desktop.png)
- 移动端：![Mobile](./assets/screen-mobile.png)

## 视觉规范

### 色彩
| 用途 | 色值 | 示例 |
|---|---|---|
| 品牌主色 | {{#HEX}} | {{色块}} |
| 文字主色 | {{#HEX}} | {{色块}} |
| 背景色 | {{#HEX}} | {{色块}} |
| 按钮主色 | {{#HEX}} | {{色块}} |
| 错误提示 | {{#HEX}} | {{色块}} |

### 字体
| 用途 | 字体 | 大小 | 粗细 |
|---|---|---|---|
| 标题 | {{Font Family}} | {{size}}px | {{weight}} |
| 正文 | {{Font Family}} | {{size}}px | {{weight}} |
| 辅助文字 | {{Font Family}} | {{size}}px | {{weight}} |

### 间距
- 内边距（组件内）：{{8px / 16px / 24px}}
- 外边距（组件间）：{{16px / 24px / 32px}}
- 栅格列间距：{{16px}}

### 圆角
- 按钮：{{4px}}
- 卡片：{{8px}}
- 输入框：{{4px}}

## 交互细节

### 按钮状态
| 状态 | 样式 | 说明 |
|---|---|---|
| Normal | {{描述}} | 默认 |
| Hover | {{描述}} | 鼠标悬停 |
| Active | {{描述}} | 点击中 |
| Disabled | {{描述}} | 禁用 |

### 动画
| 元素 | 动画效果 | 时长 | 缓动 |
|---|---|---|---|
| 页面切换 | {{fade / slide}} | {{300}}ms | ease-in-out |
| 弹窗 | {{scale + fade}} | {{200}}ms | ease-out |
| 按钮点击 | {{scale}} | {{100}}ms | ease-out |

### 响应式断点（如适用）
- 移动端：< 768px
- 平板：768px - 1024px
- 桌面端：> 1024px

## 页面流程

### 用户旅程
```
启动 → 登录 → 首页 → {{功能页 A}} → {{功能页 B}} → 完成
```

### 关键路径交互
1. {{步骤 1}}：用户操作 → 界面反馈
2. {{步骤 2}}：用户操作 → 界面反馈
3. {{步骤 3}}：用户操作 → 界面反馈

## 可交互原型

见 `prototype.html`（可在浏览器直接打开的可点击原型）。

## 设计资源交付

- [ ] Figma / Sketch 源文件链接：{{URL}}
- [ ] 切图资源（SVG / PNG）：`design/assets/`
- [ ] 图标库：{{link}}
- [ ] 设计规范文档：{{link}}

## 开发注意事项

- 使用设计系统组件库（如有）
- 严格遵循视觉规范（色彩、字体、间距）
- 响应式布局适配移动端
- 动画性能优化（CSS transform > position）
- 可访问性（语义化标签、键盘导航、ARIA）

## DesignGate 检查点（C 端）

- [ ] 高保真设计稿完整（主界面 + 关键状态）
- [ ] 视觉规范明确（色彩/字体/间距）
- [ ] 交互细节定义（状态/动画）
- [ ] 可交互原型或等效产物
- [ ] 设计资源已交付

**DesignGate 状态**：READY / BLOCKED

**说明**：C 端 UI 必须高保真，blocking: true 不可 override。
