# DeliverHQ 分层架构

## 设计原则

组织 AI 编程提效的关键不是让 AI 更努力，而是**让 AI 不按流程做就过不了门**。

DeliverHQ 采用五层架构，从柔性指导到硬性门禁递进：

```
Rule（研发制度）
    ↓
Skill（标准步骤）
    ↓
Scripts（硬门禁）
    ↓
Workflow（阶段接力）
    ↓
Writeback（进化机制）
```

---

## 第 1 层：Rule（研发制度）

**定义**: 组织的研发规范和最佳实践

**位置**: `docs/rules/`

**特征**:
- 柔性指导
- 人类可读的自然语言
- 可以被 AI 解释和遵循
- 可以被违反（但会被记录）

**示例**:
```yaml
# docs/rules/code-review.md
1. 所有代码变更必须经过审查
2. P0 问题必须在合并前修复
3. 测试覆盖率不得低于 80%
4. 不允许直接修改 protected_paths
```

**执行方式**: Skill 参考 Rule，Scripts 验证 Rule

---

## 第 2 层：Skill（标准步骤）

**定义**: 可复用的标准操作流程

**位置**: `SKILL.md`、自定义 Skill 文件

**特征**:
- 结构化的步骤定义
- 定义"应该怎么做"
- 包含检查点和验证步骤
- 可以被 Agent 执行

**示例**:
```markdown
## Skill: deliver-cr

1. 验证 CR 目录结构
2. 运行 SpecGate 检查规格
3. 开发实现
4. 运行 QualityGate 验证
5. 运行 ReviewGate 审查
6. 部署就绪检查
7. Writeback 知识沉淀
```

**执行方式**: Agent 遵循 Skill 步骤，调用 Scripts 验证

---

## 第 3 层：Scripts（硬门禁）

**定义**: 可执行的验证脚本

**位置**: `scripts/`

**特征**:
- **硬约束**：不通过就 BLOCKED
- 真实执行（build、test、lint）
- 返回明确的 PASS/BLOCKED
- 不能被绕过（除非显式 --skip）

**示例**:
```python
# scripts/specgate.py
def main():
    # 检查 SDD 三段式
    if not has_data_spec(spec):
        print("❌ BLOCKED - 缺少 Data Spec")
        sys.exit(1)
    
    # 检查待确认项
    if has_pending_questions(spec):
        print("❌ BLOCKED - 包含待确认问题")
        sys.exit(1)
    
    print("✅ PASS")
    sys.exit(0)
```

**执行方式**: Workflow 在关键节点调用 Scripts

---

## 第 4 层：Workflow（阶段接力）

**定义**: 多阶段的编排流程

**位置**: `scripts/skill_orchestrator.py`、Workflow 定义

**特征**:
- 定义阶段顺序
- 管理 Agent 切换
- 执行 Gate 检查
- 处理阻塞和回退

**示例**:
```yaml
# CR Workflow
phases:
  - name: spec
    agent: spec-agent
    gates: [specgate]
    
  - name: dev
    agent: dev-agent
    baseline: before  # 开发前建立基线
    
  - name: quality
    agent: quality-agent
    gates: [qualitygate]
    baseline: after   # 开发后对比基线
    
  - name: review
    agent: review-agent
    gates: [reviewgate]
```

**执行方式**: Orchestrator 驱动整个流程

---

## 第 5 层：Writeback（进化机制）

**定义**: 从执行中学习，沉淀可复用知识

**位置**: `delivery/`、`docs/decisions/`、`docs/mistake-book/`

**特征**:
- 记录技术决策
- 记录失败案例
- 更新 Rule（候选 → 验证 → 正式）
- 闭环进化

**示例**:
```markdown
# docs/decisions/DECISION-001.md
## 决策：使用 PostgreSQL 存储日志

**背景**: 需要可查询的日志存储

**决策**: 使用 PostgreSQL 而非 NoSQL

**原因**:
- 已有基础设施
- 支持复杂查询
- 事务保证

**影响**: 写入性能较 NoSQL 略低，但可接受
```

**执行方式**: WritebackGate 验证知识沉淀完整性

---

## 分层交互

### 自上而下（设计时）

```
Rule（制定规范）
  → Skill（定义步骤）
    → Scripts（实现验证）
      → Workflow（编排执行）
```

### 自下而上（运行时）

```
Workflow（执行流程）
  → Scripts（验证约束）
    → Skill（遵循步骤）
      → Rule（参考规范）
        → Writeback（更新规范）
```

---

## 关键原则

### 1. 柔性到硬性的递进

- **Rule**: 可以违反，但会被记录
- **Skill**: 应该遵循，偏离会有警告
- **Scripts**: 必须通过，否则 BLOCKED

### 2. Scripts 不应该只检查报告格式

❌ **错误做法**:
```python
# 只检查 quality-report.md 是否存在
if not report_file.exists():
    return BLOCKED
```

✅ **正确做法**:
```python
# 执行真实验证
result = subprocess.run(["npm", "test"])
if result.returncode != 0:
    return BLOCKED
```

### 3. 基线对比是关键

开发前后对比，确保不引入新问题：

```python
# 开发前
baseline_before = run_verification()

# 开发...

# 开发后
baseline_after = run_verification()

# 对比
if baseline_after.errors > baseline_before.errors:
    return BLOCKED  # 新增错误，必须修复
```

---

## 实现优先级

### v4.9.2（当前）
- ✅ Scripts 层基本完整（Gate 脚本）
- ✅ Workflow 层部分实现（Orchestrator）
- ⚠️ Rule 层分散在文档中
- ⚠️ Skill 层与 Scripts 混合
- ⚠️ Writeback 层缺少防污染机制

### v5.0（目标）
- ✅ Rule 层统一到 `docs/rules/`
- ✅ Skill 层清晰定义
- ✅ Scripts 层全部执行真实验证
- ✅ Workflow 层支持基线对比
- ✅ Writeback 层三级管控（candidate → verified → proven）

---

## 示例：完整的五层协作

**场景**: 添加用户登录日志功能

### 1. Rule 层
```markdown
# docs/rules/data-storage.md
- 日志数据必须持久化存储
- 敏感信息不得记录明文
- 数据保留期需明确定义
```

### 2. Skill 层
```markdown
## Skill: implement-feature

1. 编写 acceptance-spec.md（SDD 三段式）
2. 运行 SpecGate 验证规格
3. 设计数据模型和接口
4. 开发前建立基线（baseline_comparison.py before）
5. 实现功能
6. 开发后对比基线（baseline_comparison.py after）
7. 运行 QualityGate 验证
```

### 3. Scripts 层
```bash
# SpecGate 检查规格
python scripts/specgate.py CR-001/acceptance-spec.md

# 开发前基线
python scripts/baseline_comparison.py CR-001 before

# 开发后基线对比
python scripts/baseline_comparison.py CR-001 after

# QualityGate 验证
python scripts/qualitygate.py CR-001
```

### 4. Workflow 层
```yaml
phases:
  - spec:
      gates: [specgate]
  - dev:
      baseline: before
  - quality:
      baseline: after
      gates: [qualitygate]
```

### 5. Writeback 层
```markdown
# docs/decisions/DECISION-002.md
决策：异步记录日志，不阻塞登录流程

# docs/rules/async-tasks.md（新增规则）
所有异步任务必须有失败率监控
```

---

## 总结

**核心理念**: 组织 AI 编程提效的关键不是让 AI 更努力，而是**让 AI 不按流程做就过不了门**。

**实现路径**:
- Rule：告诉 AI 应该怎么做
- Skill：教 AI 标准流程
- Scripts：确保 AI 做对了
- Workflow：编排 AI 的工作
- Writeback：让 AI 从经验中学习

**v5.0 目标**: 五层架构完全落地，Gate 全部执行真实验证，基线对比成为标准流程。
