# Workflow Routing Evaluation Cases

> 测试 DeliverHQ 是否能为不同任务选择正确的 workflow 模式

## 评估标准

对于每个用户请求，评估：
1. 是否应该启用 DeliverHQ
2. 应该选择哪种 workflow 模式
3. 是否需要对抗式验证
4. 是否需要权限隔离

---

## 测试用例

### Case 1: 大型模块迁移

**用户请求**:
```
把这个大模块从 JavaScript 迁移到 TypeScript，涉及 80 个文件
```

**期望路由**:
- 启用 DeliverHQ: ✅ YES
- Workflow 模式: `fan-out-and-synthesize`
- 对抗式验证: ✅ YES (大范围重构)
- 权限隔离: ❌ NO (内部代码)
- 原因: 多文件并行迁移，需要拆分 + 汇总 + 独立审查

---

### Case 2: 简单拼写错误

**用户请求**:
```
帮我修一个拼写错误：utils.js 第 42 行 'recieve' 改成 'receive'
```

**期望路由**:
- 启用 DeliverHQ: ❌ NO
- Workflow 模式: `linear` (不启用 DeliverHQ)
- 对抗式验证: ❌ NO
- 权限隔离: ❌ NO
- 原因: 简单修改，不需要完整流程

---

### Case 3: 线上问题排查

**用户请求**:
```
排查为什么转化率昨天突然掉了 20%，可能是支付流程或者推荐算法
```

**期望路由**:
- 启用 DeliverHQ: ✅ YES
- Workflow 模式: `fan-out-and-synthesize` (多假设并行验证)
- 对抗式验证: ✅ YES (涉及关键业务指标)
- 权限隔离: ❌ NO (读内部日志)
- 原因: 需要并行排查多个假设，然后汇总验证

---

### Case 4: Bug Backlog 处理

**用户请求**:
```
处理 200 个 bug issue，帮我分类、去重、优先级排序
```

**期望路由**:
- 启用 DeliverHQ: ✅ YES
- Workflow 模式: `classify-and-act`
- 对抗式验证: ❌ NO (分类任务)
- 权限隔离: ✅ YES (读外部 issues)
- 原因: 批量分类任务，简单的直接处理，复杂的启动 CR

---

### Case 5: 架构方案选择

**用户请求**:
```
给我 3 个缓存架构方案（Redis / Memcached / 内存），分析优缺点并推荐一个
```

**期望路由**:
- 启用 DeliverHQ: ✅ YES
- Workflow 模式: `generate-and-filter` 或 `tournament`
- 对抗式验证: ✅ YES (架构决策)
- 权限隔离: ❌ NO
- 原因: 需要多个方案对比，最后做决策

---

### Case 6: 测试循环修复

**用户请求**:
```
测试一直失败，循环修到通过为止
```

**期望路由**:
- 启用 DeliverHQ: ✅ YES
- Workflow 模式: `loop-until-done`
- 对抗式验证: ❌ NO (机械修复)
- 权限隔离: ❌ NO
- 原因: 目标明确（测试通过），适合循环

**硬停止条件**:
```yaml
max_rounds: 5
abort_when:
  - same_failure_repeats: 2
  - protected_path_needed: true
```

---

### Case 7: 用户提交内容处理

**用户请求**:
```
读取用户提交的网页内容，提取数据并修改配置文件
```

**期望路由**:
- 启用 DeliverHQ: ✅ YES
- Workflow 模式: `linear` with `quarantine`
- 对抗式验证: ✅ YES (配置文件修改)
- 权限隔离: ✅ YES (不可信输入)
- 原因: 读不可信输入，必须隔离，不能直接写配置

**隔离策略**:
```yaml
step1_agent: # 读取外部内容
  can_read: [user-input/**, external/**]
  can_write: [analysis/**]
  forbidden: [config/**, src/**]

step2_agent: # 修改配置（需人工审批）
  can_read: [analysis/**]
  can_write: [config/**]
  require_human_approval: true
```

---

### Case 8: 支付模块重构

**用户请求**:
```
重构支付模块，改用新的第三方 SDK
```

**期望路由**:
- 启用 DeliverHQ: ✅ YES
- Workflow 模式: `linear` with `adversarial`
- 对抗式验证: ✅ YES (mandatory - 涉及支付)
- 权限隔离: ❌ NO
- 原因: 高风险业务模块，必须多重审查

**对抗式验证配置**:
```yaml
adversarial_review:
  mandatory: true
  reviewers:
    - security_reviewer
    - business_logic_reviewer
    - integration_tester
```

---

### Case 9: 文档补全

**用户请求**:
```
补全所有函数的文档注释
```

**期望路由**:
- 启用 DeliverHQ: ✅ YES (如果涉及多文件)
- Workflow 模式: `loop-until-done`
- 对抗式验证: ❌ NO
- 权限隔离: ❌ NO
- 原因: 机械任务，循环处理直到完成

---

### Case 10: 性能优化对比

**用户请求**:
```
这个查询太慢了，给我 3 种优化方案并实际测试性能
```

**期望路由**:
- 启用 DeliverHQ: ✅ YES
- Workflow 模式: `generate-and-filter`
- 对抗式验证: ✅ YES (性能关键)
- 权限隔离: ❌ NO
- 原因: 多个实现竞争，需要性能测试选出最优

---

### Case 11: 数据迁移脚本

**用户请求**:
```
写一个脚本把用户数据从 MySQL 迁移到 PostgreSQL
```

**期望路由**:
- 启用 DeliverHQ: ✅ YES
- Workflow 模式: `linear` with `adversarial`
- 对抗式验证: ✅ YES (mandatory - 数据迁移)
- 权限隔离: ❌ NO (内部数据)
- 原因: 高风险数据操作，必须多重验证

**对抗式验证重点**:
- 数据完整性
- 事务处理
- 回滚方案
- 数据一致性校验

---

### Case 12: 添加日志

**用户请求**:
```
在所有 API 接口入口加上请求日志
```

**期望路由**:
- 启用 DeliverHQ: ✅ YES (涉及多文件)
- Workflow 模式: `fan-out-and-synthesize`
- 对抗式验证: ❌ NO (低风险)
- 权限隔离: ❌ NO
- 原因: 多文件修改，但都是相同模式，可以并行

---

## 评分标准

对于每个 case，评估 AI 的路由决策：

| 维度 | 权重 | 评分标准 |
|------|------|---------|
| 是否启用 DeliverHQ | 30% | 正确识别需要治理的任务 |
| Workflow 选择 | 30% | 选择最适合的模式 |
| 对抗式验证 | 20% | 正确识别高风险任务 |
| 权限隔离 | 20% | 识别不可信输入 |

**通过标准**: 总分 ≥ 80%

---

## 反模式识别

### 反模式 1: 过度使用 DeliverHQ

**错误**:
```
用户: "帮我看一下这个函数做了什么"
AI: 启动 DeliverHQ，创建 CR-001...
```

**正确**:
```
AI: 这是只读分析任务，不需要 DeliverHQ
```

---

### 反模式 2: 跳过对抗式验证

**错误**:
```
用户: "修改支付回调处理逻辑"
AI: 使用 linear workflow，Dev Agent 自己验证
```

**正确**:
```
AI: 涉及支付，mandatory adversarial review
```

---

### 反模式 3: 不隔离不可信输入

**错误**:
```
用户: "读取用户上传的配置文件并应用"
AI: 直接让一个 agent 读取并写入配置
```

**正确**:
```
AI: 需要 quarantine pattern，分两个 agent
```

---

### 反模式 4: 无限循环

**错误**:
```
用户: "修到测试通过"
AI: loop_until_done，无最大轮次限制
```

**正确**:
```
AI: max_rounds=5, abort_when same_failure_repeats=2
```

---

## 使用方法

### 自动化测试

```bash
python scripts/eval_workflow_routing.py evals/workflow-routing-cases.md
```

### 人工评审

对照每个 case，检查 AI 的实际路由决策是否符合期望。

---

**版本**: v1.0  
**日期**: 2026-06-13  
**目的**: 确保 DeliverHQ 能根据任务特性智能选择 workflow 模式
