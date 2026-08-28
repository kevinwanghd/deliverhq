---
name: grill-the-user
description: 对用户进行结构化烤问，一次一问，直到决策树所有分支被穷尽或用户选择停止。适用：设计决策、技术选型、需求澄清。调用 codebase-design 词汇。
disable-model-invocation: true
argument-hint: "What decision or plan do you want to grill?"
---

# Grill the User

一次一问烤问用户，直到决策树穷尽或用户停止。

## 原则

1. **一次一问**：不能一口气抛 5 个问题
2. **给推荐答案**：不能只问不给方向
3. **能查代码就不问人**：先读代码，再问用户
4. **产出留痕**：Q&A 存成工件
5. **条件启用**：如果决策已经很清晰，跳过 grilling

## 通用模式（无文档约束）

```
第一层：约束条件
  Q: 什么约束限制了这个选择？（性能/成本/时间/团队能力）
  Q: 这个决策的最大风险是什么？（具体风险 + 缓解方案）

第二层：依赖关系
  Q: 依赖哪些其他决策还没定？
  Q: 改动这个决策的代价有多大？（easy/medium/hard）

第三层：替代方案
  Q: 为什么选 A 而不是 B 或 C？（对比维度）
  Q: 如果 A 失败了，降级方案是什么？

第四层：验证条件
  Q: 怎么知道这个决策是对的？（可观测指标，失败信号）
  Q: 什么时候必须回滚？（触发条件）
```

## 架构模式（调用 codebase-design）

```
第一层：目的
  Q: 这个模块的核心目的是什么？（用 module/depth 词汇）
  Q: 为什么值得单独一个模块？（leverage）

第二层：接口
  Q: 最小接口是什么？（不能更少）
  Q: 是否有两个独立实现？如果没有，先等。

第三层：深度
  Q: 这个模块是深还是浅？（interface/complexity 比值）
  Q: 删掉它，复杂度是否集中了？（删除测试）

第四层：局部性
  Q: 理解这个模块需要跳几个文件？
  Q: bug 通常藏在哪里？（调用方式还是实现？）
```

## 交互格式

每次烤问：
```
[Round N]
Q: [具体问题，有上下文]
推荐: [Agent 建议方向]
你的答案: _
```

## 记录

Q&A 追加到 CR 目录的 `request-clarifications.md`。

## 停止条件

- 所有分支穷尽
- 用户说"够了"
- 超过 10 轮

## DeliverHQ 集成

- `to-spec` 前用这个烤问需求
- `improve-codebase-architecture` 选定后走决策树
- `domain-modeling` 发现矛盾时澄清术语
