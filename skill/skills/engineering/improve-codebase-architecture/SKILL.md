---
name: improve-codebase-architecture
description: 扫描代码库找深化机会，生成 HTML 可视化报告，然后用 grilling 循环逐个决策。适用：架构检查、模块重构规划、技术债优先级排序。调用 codebase-design 建立共享词汇。
disable-model-invocation: true
---

# Improve Codebase Architecture

扫描代码库找到深化机会（浅模块 → 深模块），目标是可测试性和 AI 可导航性。

## 词汇依赖

先调用 `codebase-design`：module / depth / seam / interface / adapter / leverage / locality / 删除测试 / 一个 adapter = 假设，两个 = 真实。

## 流程

### 1. 探索（Scope First）

YAGNI——深化有代价，先找值得深化的区域。

重点最近改动的区域：
```bash
git log --oneline -30
```

读 `docs/CONTEXT.md` 和 ADRs，然后派 sub-agent 有机探索：
- 理解一个概念需要跳转很多小模块的地方
- 浅模块（interface 几乎和 implementation 一样复杂）
- 纯函数抽出来了但 bug 藏在调用方式里（没有 locality）
- 没测试或按当前接口难以测试的区域

应用删除测试：删掉它，复杂度是否集中了？YES = 好信号。

### 2. 生成 HTML 报告

写自包含 HTML 到 OS 临时目录（每次运行新文件）：
- Linux: `$TMPDIR/improve-codebase-architecture.html`
- macOS: `$TMPDIR/improve-codebase-architecture.html`
- Windows: `%TEMP%\improve-codebase-architecture.html`

用 Tailwind CDN + Mermaid CDN。

每个候选卡片：
- **模块**：涉及哪些文件
- **问题**：为什么当前架构造成摩擦
- **解决方案**：用 locality 和 leverage 描述
- **Before/After 图**：手绘 SVG 或 Mermaid
- **推荐强度**：badge（`Strong` / `Worth exploring` / `Speculative`）

末尾加 **Top Recommendation**。

用 CONTEXT.md 词汇描述领域，用 codebase-design 词汇描述架构。
ADR 冲突时加警告 callout。

### 3. 决策循环

用户选定后，调用 `grill-the-user` 走决策树（约束/依赖/深化后形状/测试存活性）。

### 4. 并行更新

- 调用 `domain-modeling` 更新 `CONTEXT.md`（深化模块命名是否在 glossary 里？）
- 用户拒绝候选且有充分理由？→ 提议写 ADR

### 5. 替代接口

想讨论替代接口方案？调用 `codebase-design` 并行讨论两个方案。

## 与 DeliverHQ 的关系

- Scan Agent → code-health-report.md
- improve-codebase-architecture → HTML 可视化报告（Scan 后用）
