# DeliverHQ v4.8 → v4.9 规划

> ⚠️ **重要：这是规划文档，不是当前能力**
> 
> 本文档描述从 v4.8 到 v4.9 的演进路线，列出的功能**尚未实现**。
> 
> **当前已实现能力请查看 SKILL.md 的"✅ 稳定能力"章节。**

---

## 版本定位

**从 v4.8 到 v4.9**: 从"文档门禁 + 对抗式验证"升级到"完整的动态 Workflow 编排系统"

**当前状态（v4.8.1）**:
- ✅ 基础门禁系统稳定
- ✅ selftest 9/9 全通过
- ✅ Gate 契约正确
- ⏸️ 动态 workflow 为规划能力

---

## P1 任务清单（5 个任务）

> 注意：这些是 v4.9 的规划任务，非 v4.8 当前能力

### Task 1: Workflow Type 选择器

**目标**: 让每个 CR 能根据任务类型选择不同的执行策略

**实现内容**:
1. 在 CR metadata 中新增字段：
```yaml
workflow_type: linear | fan-out | adversarial | classify-act | generate-filter | tournament | loop-until-done
workflow_budget:
  max_agents: 5
  max_rounds: 3
  token_budget: 100k
  require_human_approval: true
```

2. 创建 `scripts/workflow_router.py`：
   - 根据任务特征自动推荐 workflow
   - 支持手动选择覆盖

3. 任务类型映射表（参考 dynamic-workflow-patterns.md）

**验收标准**:
- [ ] CR 可以指定 workflow_type
- [ ] workflow_router.py 能给出合理推荐
- [ ] 推荐准确率 ≥ 80%（基于 workflow-routing-cases.md）

---

### Task 2: 6 种 Workflow 模板实现

**目标**: 将 references/dynamic-workflow-patterns.md 中的模式落地为可执行模板

**实现内容**:
1. 创建目录结构：
```
references/workflows/
  fan-out-and-synthesize.md
  adversarial-verification.md
  classify-and-act.md
  generate-and-filter.md
  tournament.md
  loop-until-done.md
```

2. 每个模板包含：
   - 适用场景
   - 输入/输出
   - 子 Agent 拆分方式
   - 读写权限定义
   - 合并规则
   - Gate 检查点
   - Token/轮次上限
   - 失败停止条件

3. 实现 `scripts/workflow_executor.py`：
   - 加载模板
   - 编排 subagent
   - 上下文隔离
   - 结果合成

**验收标准**:
- [ ] 6 个模板文档完整
- [ ] workflow_executor.py 能执行至少 3 种模式
- [ ] 实际运行测试通过

---

### Task 3: PermissionGate 和 Quarantine Pattern

**目标**: 实现权限隔离，防止不可信输入污染高权限操作

**实现内容**:
1. 扩展 `dir-graph.yaml`：
```yaml
trust_zones:
  untrusted-input:
    can_read: [../issues/**, ../external-docs/**]
    can_write: [change-requests/*/analysis/*]
    forbidden: [../src/**, ../config/**, protected_paths]
  
  trusted-write:
    can_read: [change-requests/*/analysis/*]
    can_write: [../src/**, ../tests/**]
```

2. 创建 `scripts/permissiongate.py`：
   - 检查 Agent 是否在允许路径内
   - 检查是否读取不可信输入后写高权限路径
   - 检查是否修改 protected_paths
   - 检查是否缺少人工审批

3. 集成到 CR 流程：
   - 在关键阶段自动运行 PermissionGate
   - 违反权限规则时 BLOCKED

**验收标准**:
- [ ] trust_zones 定义完整
- [ ] permissiongate.py 能检测权限违规
- [ ] 集成到主流程
- [ ] 通过 Quarantine 测试用例

---

### Task 4: Branch Context Packs

**目标**: 为每个 subagent 生成专属上下文包，减少目标漂移

**实现内容**:
1. 创建目录结构：
```
change-requests/CR-XXX/context-packs/
  dev-auth-module.md
  dev-order-module.md
  reviewer-security.md
  reviewer-business.md
  test-regression.md
```

2. Context Pack 模板：
```markdown
Context Pack: reviewer-security

Role: Security Review Agent

Goal: 只检查认证、权限、敏感信息、注入风险

Must Read:
- acceptance-spec.md
- src/auth/**
- docs/rules.md#security

Must Not Touch:
- src/payment/**
- config/**

Acceptance Criteria Slice:
- AC-003, AC-007
```

3. 创建 `scripts/context_pack_generator.py`：
   - 根据任务拆分生成 context packs
   - 每个 pack 只包含必需内容
   - 支持手动调整

**验收标准**:
- [ ] Context Pack 模板定义清晰
- [ ] context_pack_generator.py 能生成合理的 packs
- [ ] Subagent 使用 context pack 后目标漂移减少 ≥ 50%

---

### Task 5: Loop Until Done 硬停止条件

**目标**: 为循环类 workflow 添加安全防护，避免无限循环

**实现内容**:
1. 在 CR metadata 中定义停止策略：
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

2. 更新 `scripts/loop_mode.py`：
   - 实现硬停止条件检查
   - 记录每轮状态
   - 检测重复失败
   - 自动中止并报告

3. 添加监控和日志：
   - 每轮执行时间
   - 失败原因
   - 停止原因

**验收标准**:
- [ ] 停止条件配置化
- [ ] 能正确检测并停止
- [ ] 不会无限循环
- [ ] 日志完整

---

## P2 任务清单（增强项）

### Task 6: Workflow Routing Eval 自动化

**目标**: 自动化测试 workflow 路由准确性

**实现内容**:
- 创建 `scripts/eval_workflow_routing.py`
- 读取 `evals/workflow-routing-cases.md`
- 自动评估路由准确率
- 生成评估报告

---

### Task 7: Benchmark 和 Eval Viewer

**目标**: 可视化评估结果

**实现内容**:
- 真实任务 benchmark
- 新旧 skill 输出对比
- 性能和质量指标对比

---

### Task 8: 文档完善

**目标**: 补充 v4.8 使用文档

**实现内容**:
- 更新 SKILL.md
- 更新 README.md
- 更新 AGENTS.md
- 补充示例和最佳实践

---

## 验收标准（v4.8 整体）

### 功能完整性
- [ ] 5/5 P1 任务完成
- [ ] Workflow router 推荐准确率 ≥ 80%
- [ ] 至少 3 种 workflow 模式可执行
- [ ] PermissionGate 能检测权限违规
- [ ] Context packs 减少目标漂移 ≥ 50%
- [ ] Loop 有硬停止条件

### 质量标准
- [ ] Selftest 通过率 ≥ 85%
- [ ] 文档完整性 100%
- [ ] 向后兼容 v4.7
- [x] Python 3.10+ 兼容

### 性能标准
- [ ] Workflow routing < 1s
- [ ] Context pack 生成 < 5s
- [ ] Permission check < 100ms
- [ ] 无内存泄漏

---

## 时间估算

| 任务 | 预估时间 | 优先级 |
|------|---------|--------|
| Task 1: Workflow Type 选择器 | 2-3 小时 | P1 |
| Task 2: 6 种 Workflow 模板 | 4-6 小时 | P1 |
| Task 3: PermissionGate | 3-4 小时 | P1 |
| Task 4: Context Packs | 2-3 小时 | P1 |
| Task 5: Loop 硬停止 | 1-2 小时 | P1 |
| **P1 总计** | **12-18 小时** | - |
| Task 6-8 (P2) | 4-6 小时 | P2 |
| **总计** | **16-24 小时** | - |

---

## 成功标准

### v4.8 应该能做到：

1. **智能路由**: 根据任务自动选择 workflow 模式
2. **动态编排**: 至少支持 3 种 workflow 模式执行
3. **权限隔离**: 不可信输入不能污染高权限操作
4. **上下文切片**: Subagent 只拿需要的上下文
5. **安全循环**: Loop 有硬停止条件，不会无限循环

### v4.8 不需要做到：

1. ❌ 所有 6 种模式都完整实现（先做 3 种核心模式）
2. ❌ 完美的 AI 路由（80% 准确率即可，可人工覆盖）
3. ❌ 复杂的可视化界面（命令行优先）
4. ❌ 分布式执行（单机优先）

---

## 风险和缓解

### 风险 1: Workflow 执行复杂度高
**缓解**: 先实现 3 种核心模式（fan-out, adversarial, loop）

### 风险 2: Context pack 生成质量不稳定
**缓解**: 提供手动调整接口，支持模板定制

### 风险 3: 权限检查性能影响
**缓解**: 只在关键阶段运行，缓存检查结果

---

## 下一步

1. 用户确认 v4.8 规划
2. 开始执行 Task 1: Workflow Type 选择器
3. 逐个完成 P1 任务
4. 每个任务完成后运行 selftest 验证
5. 所有 P1 完成后发布 v4.8

---

**规划版本**: v4.8-ROADMAP  
**规划日期**: 2026-06-13  
**预期完成**: P1 任务 12-18 小时  
**评分目标**: 9.7/10 (+0.2 相比 v4.7)
