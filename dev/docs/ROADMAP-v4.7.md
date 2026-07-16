# DeliverHQ v4.7 开发计划

## 版本信息
- **版本**: v4.7
- **计划开始**: 2026-06-13
- **预计完成**: 2026-07
- **基于版本**: v4.6 (评分 9.2/10)

---

## 核心目标

从 v4.6 的"质量可控"升级到 v4.7 的"自动化执行"

### v4.6 → v4.7 的升级方向
- **v4.6**: AI 全流程交付质量可控（规格化 + 门禁 + 沉淀）
- **v4.7**: AI 自动化执行引擎（worktree 隔离 + Loop Mode + 外部记忆）

---

## 规划任务清单

### 1️⃣ worktree 隔离实现（P0 - 基础设施）

**目标**: 让多个 Agent 可以并行开发，互不干扰

**核心功能**:
- 每个 CR 自动创建独立 worktree
- Agent 在 worktree 中执行开发
- 完成后自动 merge 或 clean up
- 冲突检测和解决机制

**技术方案**:
```bash
# 创建 worktree
git worktree add .claude/worktrees/CR-002 -b feature/CR-002

# Agent 在 worktree 中工作
cd .claude/worktrees/CR-002
# ... 开发 ...

# 完成后 merge
git checkout master
git merge feature/CR-002
git worktree remove .claude/worktrees/CR-002
```

**验收标准**:
- [ ] 能自动创建 worktree
- [ ] 多个 CR 可并行开发
- [ ] 完成后能正确 merge
- [ ] 冲突能被检测和报告

**预计工作量**: 8-12 小时

---

### 2️⃣ Loop Mode 执行引擎（P0 - 自动化核心）

**目标**: AI 自动循环执行任务，直到完成或遇到阻塞

**核心功能**:
- 定义 Loop 任务（例如："实现所有 P0 功能"）
- 自动分解为子任务
- 循环执行：取任务 → 执行 → 验证 → 下一个
- 遇到阻塞自动暂停，记录原因

**Loop 流程**:
```
1. 读取 Loop 目标
2. 分解为 Task List
3. While 有未完成任务:
   a. 取下一个任务
   b. 执行任务
   c. 运行相关 Gate
   d. If Gate PASS: 标记完成
   e. If Gate BLOCKED: 记录阻塞，跳过
4. 生成执行报告
```

**验收标准**:
- [ ] 能定义 Loop 任务
- [ ] 能自动分解子任务
- [ ] 能循环执行直到完成
- [ ] 遇到阻塞能正确暂停
- [ ] 生成完整执行报告

**预计工作量**: 16-20 小时

---

### 3️⃣ 外部记忆库集成（P1 - 知识增强）

**目标**: 集成外部记忆系统，提升 AI 的上下文能力

**候选方案**:
- **Hindsight**: Claude 原生记忆系统
- **Mem0**: 开源记忆框架
- **自建**: 基于向量数据库

**核心功能**:
- 自动记录重要决策和经验
- 跨 CR 的知识检索
- 相似问题的解决方案推荐
- 自动更新 rules/decisions/mistake-book

**验收标准**:
- [ ] 能自动记录决策
- [ ] 能跨 CR 检索知识
- [ ] 能推荐相似解决方案
- [ ] 与现有 Writeback 集成

**预计工作量**: 12-16 小时

---

### 4️⃣ Skills 拆分（P2 - 架构优化）

**目标**: 将 DeliverHQ 拆分为 Thin Harness + Fat Skills

**当前问题**:
- SKILL.md 过大（7000+ 字节）
- Agent 职责混在一起
- 难以独立升级某个 Agent

**拆分方案**:
```
DeliverHQ/
├── core/                   # Thin Harness
│   ├── orchestrator.py     # 流程编排
│   ├── gate_runner.py      # Gate 执行器
│   └── memory_manager.py   # 记忆管理
└── skills/                 # Fat Skills
    ├── spec_agent/         # 规格 Agent
    ├── design_agent/       # 设计 Agent
    ├── dev_agent/          # 开发 Agent
    ├── review_agent/       # 审查 Agent
    ├── test_agent/         # 测试 Agent
    ├── quality_agent/      # 质量 Agent
    ├── deploy_agent/       # 部署 Agent
    └── writeback_agent/    # 回写 Agent
```

**验收标准**:
- [ ] 核心编排逻辑独立
- [ ] 每个 Skill 可独立升级
- [ ] SKILL.md 拆分为多个文件
- [ ] 保持向后兼容

**预计工作量**: 8-12 小时

---

## 优先级排序

| 任务 | 优先级 | 依赖 | 工作量 | 价值 |
|------|--------|------|--------|------|
| worktree 隔离 | P0 | 无 | 12h | 高（并行能力） |
| Loop Mode | P0 | worktree | 20h | 极高（自动化） |
| 外部记忆库 | P1 | 无 | 16h | 中（知识增强） |
| Skills 拆分 | P2 | 无 | 12h | 中（架构优化） |

**建议实施顺序**: worktree → Loop Mode → 外部记忆库 → Skills 拆分

---

## 实施计划

### Sprint 1: worktree 隔离（Week 1）
- 设计 worktree 管理机制
- 实现自动创建/清理
- 集成到 CR 流程
- 测试并发场景

### Sprint 2: Loop Mode（Week 2-3）
- 设计 Loop 任务定义格式
- 实现任务分解逻辑
- 实现循环执行引擎
- 集成 Gate 检查
- 测试各种场景

### Sprint 3: 外部记忆库（Week 4）
- 调研 Hindsight/Mem0
- 选择技术方案
- 实现基础集成
- 与 Writeback 联动

### Sprint 4: Skills 拆分（Week 5）
- 设计拆分架构
- 逐步迁移 Agent
- 更新文档
- 保证兼容性

---

## 技术决策

### 1. worktree vs 分支策略
**选择**: worktree
**原因**: 
- 物理隔离更彻底
- 避免频繁切换分支
- 适合并行开发

### 2. Loop 任务定义格式
**选择**: YAML
**原因**:
- 人类可读
- 支持层级结构
- 易于版本控制

### 3. 外部记忆库选型
**待定**: 需要调研对比
**候选**:
- Hindsight（Claude 原生）
- Mem0（开源）
- 自建（灵活）

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| worktree 冲突处理复杂 | 中 | 高 | 提前设计冲突检测机制 |
| Loop Mode 无限循环 | 中 | 高 | 设置最大迭代次数和超时 |
| 外部记忆库性能问题 | 低 | 中 | 本地缓存 + 异步处理 |
| Skills 拆分影响兼容性 | 低 | 中 | 渐进式迁移 + 双模式运行 |

---

## 成功标准

### 功能完整性
- [ ] worktree 隔离可用
- [ ] Loop Mode 能完成端到端任务
- [ ] 外部记忆库能检索和推荐
- [ ] Skills 拆分完成

### 质量指标
- [ ] selftest 继续 100% 通过
- [ ] 正反例验证通过
- [ ] 文档完整

### 性能指标
- [ ] worktree 创建 < 5s
- [ ] Loop 任务执行效率提升 50%
- [ ] 记忆检索 < 1s

---

## 下一步行动

### 立即可做
1. 创建 CR-002："实现 worktree 隔离机制"
2. 设计 worktree 管理接口
3. 开始编码实现

### 需要确认
1. 是否立即开始 v4.7？
2. 优先级顺序是否合理？
3. 外部记忆库倾向哪个方案？

---

**创建时间**: 2026-06-13 20:40  
**创建人**: Kiro AI  
**状态**: DRAFT（待确认后开始）
