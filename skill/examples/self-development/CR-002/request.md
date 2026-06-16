# Request: 实现 worktree 隔离机制

> Change Request 需求输入文档。由需求方/产品经理填写。

## CR-ID
CR-002

## 提出人
Kiro AI

## 提出日期
2026-06-13

## 需求背景

DeliverHQ v4.6 已实现质量可控的 AI 交付流程，但多个 CR 并行开发时会遇到代码冲突问题。需要实现 worktree 隔离机制，让每个 CR 在独立的工作空间中开发，互不干扰。

**当前痛点**：
- 多个 CR 无法并行开发
- 频繁切换分支影响效率
- 代码冲突难以避免
- Agent 可能误改其他 CR 的代码

## 业务目标

**解决的问题**：
1. 支持多个 CR 并行开发
2. 物理隔离避免代码冲突
3. 提升开发效率（无需频繁切换分支）
4. 为 Loop Mode（v4.7 Task 2）打基础

**预期收益**：
1. 并行开发能力：支持 3-5 个 CR 同时进行
2. 冲突减少：物理隔离降低冲突概率 90%
3. 效率提升：减少分支切换时间 80%
4. 安全性提升：Agent 无法访问其他 CR 的工作空间

## 功能描述

### 用户故事 1：自动创建 worktree
**作为** Dev Agent  
**我想要** 自动为新 CR 创建独立的 worktree  
**以便于** 在隔离环境中开发，不影响其他 CR

**验收条件**：
- 运行 `python scripts/init_cr.py CR-003` 自动创建 worktree
- worktree 位于 `.claude/worktrees/CR-003/`
- 基于最新的 master 分支
- 自动创建新分支 `feature/CR-003`

### 用户故事 2：在 worktree 中开发
**作为** Dev Agent  
**我想要** 在 worktree 中进行所有开发操作  
**以便于** 与其他 CR 物理隔离

**验收条件**：
- Agent 自动切换到 worktree 目录
- 所有文件修改发生在 worktree 中
- worktree 有独立的 .git 目录
- 不影响主仓库和其他 worktree

### 用户故事 3：完成后自动 merge
**作为** Dev Agent  
**我想要** CR 完成后自动 merge 到 master  
**以便于** 代码快速集成

**验收条件**：
- 通过所有 Gate 后触发 merge
- 自动切换回 master
- 自动 merge feature 分支
- 自动删除 worktree 目录

### 用户故事 4：冲突检测和处理
**作为** Dev Agent  
**我想要** merge 前自动检测冲突  
**以便于** 及时发现和解决问题

**验收条件**：
- merge 前检测冲突
- 有冲突时阻断 merge
- 明确列出冲突文件
- 提供解决建议

## 非功能需求
- 性能要求：worktree 创建时间 < 5 秒
- 可靠性要求：worktree 创建成功率 > 99%
- 易用性要求：对用户透明，自动管理
- 兼容性要求：支持 Git 2.15+

## 约束条件

**技术约束**：
- Git 2.15+ 支持 worktree
- 需要足够磁盘空间（每个 worktree 约 100-500 MB）

**时间约束**：
- 开发时间：12 小时
- 测试时间：4 小时
- 总计：16 小时（2 个工作日）

**依赖项**：
- Git worktree 命令
- Python 3.6+
- DeliverHQ v4.6 框架

## 优先级
P0（v4.7 基础设施，阻塞 Loop Mode）

## 验收标准（高层）

1. 能自动创建 worktree
2. 多个 CR 可并行开发
3. 完成后能正确 merge
4. 冲突能被检测和报告
5. worktree 自动清理
6. 文档完整（使用说明 + 故障排除）

## 附件

- v4.7 规划文档：`docs/ROADMAP-v4.7.md`
- Git worktree 文档：https://git-scm.com/docs/git-worktree
- 参考实现：Claude Code 的 worktree 机制
