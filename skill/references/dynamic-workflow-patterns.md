# Dynamic Workflow Patterns

> 基于 Claude Workflow 最新实践：根据任务现场动态拆分多个 subagent，隔离上下文，并行执行，对抗式验证。

## 核心理念

**从"线性阶段治理"升级到"任务级动态 workflow harness"**：

- 不是所有任务都走固定流水线
- 根据任务类型、复杂度、风险级别动态选择编排模式
- 每个 subagent 只拿自己需要的上下文
- 关键原则：**干活的人和验收的人不能是同一个 agent**

---

## 6 种 Workflow 模式

### 1. Fan-out and Synthesize（扇出合成）

**适用场景**：
- 大型重构（涉及多个模块）
- 多文件迁移
- 代码库扫描
- 需求拆分和并行实现

**流程**：
```
1. Orchestrator 读取 acceptance-spec + implementation-plan
2. 拆分 N 个独立子任务
3. 每个 Dev SubAgent 只获得自己的：
   - 文件范围
   - 验收标准切片
   - 上下文包（不是全量）
4. 并行执行，各自输出 branch-report.md
5. Synthesizer 汇总所有分支结果
6. Review Agent 对汇总结果做对抗式核查
7. ReviewGate PASS 后进入 Test
```

**关键点**：
- 每个 subagent 上下文隔离，减少目标漂移
- 并行执行加速
- 最后必须有独立 Review Agent 挑刺

**示例**：
```yaml
workflow_type: fan-out-and-synthesize
tasks:
  - id: auth-module
    files: [src/auth/**]
    acceptance_criteria: [AC-001, AC-002]
  - id: order-module
    files: [src/order/**]
    acceptance_criteria: [AC-003, AC-004]
  - id: payment-module
    files: [src/payment/**]
    acceptance_criteria: [AC-005]
```

---

### 2. Adversarial Verification（对抗式验证）

**适用场景**：
- 高风险交付（涉及认证、支付、数据迁移）
- 触碰 protected_paths
- P0 业务流程
- 外部用户可见功能

**流程**：
```
1. Dev Agent 实现代码
2. Review Agent 1: 尝试证明实现是错的
   - 寻找反例
   - 寻找边界漏洞
   - 寻找安全风险
3. Review Agent 2: 尝试证明验收条件未覆盖
   - 寻找需求缺口
   - 寻找隐含假设
4. Review Agent 3: 尝试证明测试是假的
   - 检查是否只测 happy path
   - 检查边界和失败路径
5. 三个 Review Agent 的发现汇总
6. 如有 P0 问题，BLOCKED
7. 如全部 PASS，才放行
```

**关键点**：
- Review Agent 独立于 Dev Agent
- 不是"看一遍代码"，而是**主动找茬**
- 多个角度挑刺（实现、需求、测试）

**触发条件**：
```yaml
adversarial_review_required: true
when:
  - touches_auth
  - touches_payment
  - touches_data_migration
  - touches_protected_paths
  - p0_business_flow
  - external_user_facing
```

---

### 3. Classify and Act（分类执行）

**适用场景**：
- Bug backlog 分拣
- Issue 批量处理
- 多个小任务分类
- 技术债分级

**流程**：
```
1. Classifier Agent 读取所有 issues
2. 分类：
   - P0 / P1 / P2
   - Bug / Feature / Refactor
   - 简单 / 中等 / 复杂
3. 针对每个类别分配不同 Actor Agent
4. 简单任务直接修复
5. 复杂任务启动完整 CR 流程
6. 输出分类报告和执行结果
```

**关键点**：
- 先分类再执行，避免无差别处理
- 简单任务不走完整 CR
- 复杂任务不跳过文档

**示例**：
```
输入: 200 个 issues
输出:
  - P0: 5 个 → 立即启动 CR
  - P1: 50 个 → 批量修复 + 测试
  - P2: 100 个 → 归档待排期
  - 重复: 45 个 → 关闭
```

---

### 4. Generate and Filter（生成过滤）

**适用场景**：
- 技术方案选择
- 架构设计对比
- 性能优化策略
- 需要多个候选方案

**流程**：
```
1. Generator Agent 生成 N 个候选方案（N=3-5）
2. 每个方案包含：
   - 实现思路
   - 优缺点
   - 成本估算
   - 风险评估
3. Filter Agent 按标准评分：
   - 可维护性
   - 性能
   - 复杂度
   - 与现有架构的契合度
4. 推荐 Top 1-2
5. 人工决策或自动选择
```

**关键点**：
- 生成阶段要多样性
- 过滤阶段要标准化
- 最终决策可人工介入

---

### 5. Tournament（锦标赛）

**适用场景**：
- 需要最优解（不只是可行解）
- 多种实现方式对比
- 性能敏感的算法选择

**流程**：
```
1. 启动 N 个 Dev Agent 独立实现
2. 每个 Agent 不知道其他 Agent 的方案
3. 对所有实现运行相同测试
4. 按标准评分：
   - 正确性
   - 性能
   - 代码质量
   - 可读性
5. 选出最优实现
6. 其他实现归档作为参考
```

**关键点**：
- Agent 之间隔离，避免互相影响
- 必须有客观评分标准
- 成本高，只用于关键模块

---

### 6. Loop Until Done（循环直到完成）

**适用场景**：
- 修测试失败
- 消除 lint 错误
- 补文档缺口
- 修 ReviewGate P0 问题

**流程**：
```
1. 运行检查（测试 / lint / Gate）
2. 如果失败，分析失败原因
3. 修复
4. 重新检查
5. 循环直到通过或达到上限
```

**关键点**：
- **必须有硬停止条件**，避免无限循环
- 适合目标明确的脏活累活
- 不适合需求不明确的任务

**安全版本**：
```yaml
loop_until_done:
  max_rounds: 5
  stop_when:
    - tests_pass
    - no_new_lint_errors
    - no_new_review_findings
  abort_when:
    - same_failure_repeats: 2
    - protected_path_needed: true
    - human_decision_needed: true
```

**不适合**：
- 需求不明确
- 架构选择
- 大范围重构没有边界
- 涉及生产配置

---

## 如何选择 Workflow 模式

| 任务类型 | 推荐 Workflow |
|---------|--------------|
| 普通小 bug | linear（不启用 DeliverHQ）|
| 大型重构 | fan-out + adversarial |
| Bug backlog 分拣 | classify-and-act |
| 技术方案选择 | generate-and-filter / tournament |
| 线上问题排查 | fan-out hypothesis + adversarial |
| 测试失败修复 | loop-until-done |
| 高风险交付 | adversarial mandatory |
| 多模块迁移 | fan-out + adversarial |
| 性能优化 | tournament |
| 文档补全 | loop-until-done |

---

## 上下文隔离：Context Packs

每个 subagent 不拿全量上下文，而是专属 context pack：

```markdown
Context Pack: reviewer-security

Role: Security Review Agent

Goal: 只检查认证、权限、敏感信息、注入风险

Must Read:
- acceptance-spec.md
- implementation-plan.md
- traceability.yml
- src/auth/**
- docs/rules.md#security

Must Not Touch:
- src/payment/**
- config/**
- protected_paths

Acceptance Criteria Slice:
- AC-003: 认证失败处理
- AC-007: 权限校验
```

**优势**：
- 减少目标漂移
- 减少 token 浪费
- 提升专注度

---

## 权限隔离：Quarantine Pattern

**原则**：让那些读不可信输入的 agent，不准碰高权限操作。

```yaml
trust_zones:
  untrusted-input:
    can_read:
      - ../issues/**
      - ../external-docs/**
      - ../logs/**
    can_write:
      - change-requests/*/analysis/*
    forbidden:
      - ../src/**
      - ../config/**
      - protected_paths

  trusted-write:
    can_read:
      - change-requests/*/analysis/*
      - change-requests/*/acceptance-spec.md
    can_write:
      - ../src/**
      - ../tests/**
```

**检查点**：
- 当前 Agent 是否在允许写入路径内
- 是否读取过不可信输入后又写高权限路径
- 是否修改 protected_paths
- 是否缺少人工审批

---

## 最佳实践

### 1. 先判断值不值得

不是所有任务都开 workflow，先判断：
- 任务复杂度
- 风险级别
- 影响范围
- 时间紧迫度

### 2. 对抗式验证是默认

高风险任务必须有独立 Review Agent：
- Dev Agent 实现
- Review Agent 挑刺
- 不能自己验自己

### 3. 上下文切片

每个 subagent 只拿需要的：
- 文件范围
- 验收条件切片
- 必需文档

### 4. 硬停止条件

Loop 类型 workflow 必须有：
- 最大轮次
- 停止条件
- 中止条件

### 5. 权限最小化

读不可信输入的 agent 不能写高权限路径。

---

## DeliverHQ 集成

### CR 元数据扩展

在 `change-requests/CR-XXX/metadata.yml` 加入：

```yaml
workflow_type: fan-out-and-synthesize
workflow_budget:
  max_agents: 5
  max_rounds: 3
  token_budget: 100k
  require_human_approval: true

adversarial_review: true
quarantine_required: false
```

### 新增脚本

- `scripts/permissiongate.py` - 权限隔离检查
- `scripts/workflow_router.py` - 根据任务选择 workflow

### 新增目录

```
DeliverHQ/references/workflows/
  fan-out-and-synthesize.md
  adversarial-verification.md
  classify-and-act.md
  generate-and-filter.md
  tournament.md
  loop-until-done.md
```

---

## 参考

- Claude Workflow 最新实践
- Anthropic Model Context Protocol
- Multi-Agent System Design Patterns

---

**版本**: v1.0  
**日期**: 2026-06-13  
**一句话**: 给手头任务现写一套配得上它的 harness。
