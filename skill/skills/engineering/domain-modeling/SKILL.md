---
name: domain-modeling
description: 构建和精炼项目领域模型。适用：讨论代码术语、写/编辑 CONTEXT.md、记录/编辑 ADR。用项目的领域词汇，不用技术术语。
---

# Domain Modeling — 领域模型构建

**主动**构建和精炼项目的领域模型。
这是活跃实践——质疑术语、发明边缘场景、在术语澄清的瞬间写入 glossary。
（只是读 `CONTEXT.md` 查词汇不是这个 skill 的工作——那是一个一句话的习惯。）

## 文件结构

```
<项目根>/
├── docs/
│   ├── CONTEXT.md          # 词汇表（glossary）
│   └── adr/
│       ├── 0001-xxx.md    # 架构决策记录
│       └── 0002-xxx.md
└── DeliverHQ/
    └── docs/
        └── CONTEXT.md     # 项目词汇（DeliverHQ 治理空间）
```

如果存在 `docs/CONTEXT-MAP.md`，说明有多个 bounded context：
```
docs/
├── adr/                    # 系统级决策
└── <context-name>/
    ├── CONTEXT.md
    └── adr/               # context 专用决策
```

文件按需创建——第一次有术语要写时再建 `CONTEXT.md`。

## 会话中的工作

### 质疑 glossary

当用户用的术语和 `CONTEXT.md` 的定义冲突时，立刻指出：
> "你的 glossary 把 'cancellation' 定义为 X，但你好像在用 Y——到底是哪个？"

### 精炼模糊语言

当用户用模糊或重载的词时，提出精确的规范术语：
> "你在说 'account' ——是 Customer 还是 User？这两者是不同概念。"

### 讨论具体场景

当讨论领域关系时，用具体场景压测。
列举边缘案例，逼迫用户在概念边界上做明确选择。

### 对照代码

当用户说某功能怎么工作时，检查代码是否同意。
发现矛盾时公开说出来：
> "你的代码取消了整个 Order，但你刚才说可以部分取消——哪个是对的？"

### 立即更新 CONTEXT.md

术语一澄清，立刻写 `CONTEXT.md`。
不要攒着——趁热记录。

**CONTEXT.md 格式**：
```markdown
# 项目词汇表

## [术语]（规范形式）
定义：一句话精确描述这个概念的含义。

## [术语]
定义：...
```

**CONTEXT.md 中禁止**：
- 实现细节
- 文件路径
- 代码片段
- 算法描述

### 谨慎提议 ADR

只有当以下三条**同时**成立才提议：
1. **难以逆转**——以后改变代价很大
2. **没有上下文会很意外**——未来读者会奇怪为什么要这样做
3. **是真实权衡的结果**——有真正的替代方案但选了一个

缺少任何一条就不写 ADR。

**ADR 格式**：
```markdown
# ADR-XXX: [决策标题]

## 状态
Accepted | Deprecated | Superseded

## 背景
[导致这个决策的情况]

## 决策
[选择的内容 + 理由]

## 后果
[正向后果]
[负向后果]
```
