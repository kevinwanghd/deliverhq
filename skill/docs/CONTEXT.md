# Project Context

> 项目背景和技术栈概要

## Overview
**项目名称**：SelfAutomaticAd（自动化广告投放系统）
**业务领域**：广告投放 / MarTech
**核心目标**：通过 AI 辅助实现广告投放全流程自动化，提升投放效率和 ROI

## Tech Stack
- **语言**：Python 3.9+, TypeScript
- **框架**：后端未明确（待识别），前端可能包含 React/Vue
- **数据库**：待识别（可能包含 MongoDB/MySQL/Redis）
- **部署**：待识别（Docker/K8s）
- **测试框架**：待建立（计划使用 pytest）
- **AI 框架**：Claude Code, DeliverHQ v4.6

## Architecture Pattern
待完整识别，当前已知：
- **DeliverHQ/**: AI 交付质量控制框架（已集成 v4.6）
- **核心业务模块**: 待识别和文档化

**已知模块**：
- DeliverHQ: AI 全流程交付质量控制（规格化、门禁、知识沉淀）
- 广告投放核心: 待文档化
- 数据分析: 待文档化

## Key Documents
| Document | Purpose | Location |
|---|---|---|
| AGENTS.md | DeliverHQ 行为规则 | `DeliverHQ/AGENTS.md` |
| dir-graph.yaml | 权限与路径配置 | `DeliverHQ/dir-graph.yaml` |
| rules / decisions / mistake-book | 组织记忆 | `DeliverHQ/docs/` |
| MEMORY.md | 动态状态记录 | `DeliverHQ/docs/MEMORY.md` |
| CR-001 | 框架升级 CR | `DeliverHQ/change-requests/CR-001/` |

## Key Constraints
- **性能要求**：待明确（目标：API P95 < 500ms）
- **安全要求**：广告投放数据安全、API Token 管理
- **可用性**：待明确（目标：核心服务 SLA 99%）
- **AI 质量**：通过 DeliverHQ Gate 机制确保 AI 交付质量可控

## Quality Gates
- **SpecGate**: 验收规格完备性检查（SDD 三段式）
- **DesignGate**: 设计产物完备性检查
- **ContextWindowGate**: 上下文窗口纪律检查
- **ReviewGate**: 代码审查门禁
- **QualityGate**: 质量门禁（P0 通过率 100%，覆盖率 ≥ 80%）
- **DeployGate**: 部署就绪性检查
- **WritebackGate**: 知识沉淀完整性检查

## Maturity Model
- **draft**: 初始规则，仅作提示
- **verified**: 3+ 次引用，默认阻断违反
- **proven**: 5+ 次引用，经过实战验证

## Current Focus
- **CR-001**: 升级项目使用 DeliverHQ v4.6 框架（进行中）
- **下一步**: 完善项目架构文档，建立测试框架

---

**最后更新**: 2026-06-13 20:25  
**更新人**: Kiro AI (CR-001)
