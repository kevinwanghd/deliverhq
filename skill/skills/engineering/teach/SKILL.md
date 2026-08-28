---
name: teach
description: 跨会话教用户一个新技能或概念。工作区持久化，记录学习进度。适用：需要多会话渐进学习的复杂主题。
disable-model-invocation: true
argument-hint: "What would you like to learn about?"
---

# Teach — 持久化教学

用户想学一个主题，需要跨多个会话持续。
把当前目录作为**教学区**，会话间持久化学习状态。

## 教学区结构

```
<当前目录>/
├── MISSION.md              # 学习动机：为什么想学这个
├── reference/             # 参考材料（每次课压缩提炼的知识点）
│   └── *.html
├── RESOURCES.md            # 资源列表（高质量来源）
├── learning-records/       # 学习记录（每次会话的收获）
│   └── 0001-.md
├── lessons/                # 课时（每个课时一个 HTML）
│   └── 0001-.html
├── assets/                 # 共享组件（样式表、测验、模拟器）
└── NOTES.md                # 笔记（用户偏好、工作笔记）
```

## 哲学

深度学习需要三样东西：
- **知识**：从高质量资源获取
- **技能**：通过针对性练习获得
- **智慧**：与同行交流实践获得

在 `RESOURCES.md` 充实之前，重点是找高质量资源。

### 流利度 vs 存储强度

区分两种学习：
- **流利度**：即时提取知识
- **存储强度**：长期保留知识

流利度可能带来虚假掌握感，存储强度才是真正目标。
设计课时时要构建长期保留：检索练习、间隔复习、交叉练习。

## 课时设计

每课时：
- 独立 HTML 文件，保存到 `lessons/`，编号递增（0001、0002...）
- **精美**：用 Tufte 风格排版，用户以后会反复回看
- **简短**：一个课时聚焦一件事，一个可完成的小目标
- **链接**：课时内链接其他课时和参考文档
- **推荐资源**：每课时推荐一个最高质量来源

写完后用命令打开文件：
- Linux: `xdg-open <path>`
- macOS: `open <path>`
- Windows: `start <path>`

## MISSION.md 格式

```markdown
# Mission

## 为什么想学这个
[用户的原始动机]

## 目标
- ...
```

第一课时之前先写 MISSION.md。
如果用户说不清楚，先问清楚再开始教。

## 邻近发展区（Zone of Proximal Development）

每次会话结束时评估用户当前水平：
- 已掌握
- 正在学
- 还没到

下一个课时要在用户"正在学"的边界上，
太简单会无聊，太难会放弃。

## 与 DeliverHQ 的关系

DeliverHQ 本身就是一个教学对象。
教用户 DeliverHQ 时：
- MISSION.md = 学 DeliverHQ 的动机
- lessons/ = 每个 DeliverHQ 概念
- reference/ = SKILL.md / AGENTS.md 的提炼版本
