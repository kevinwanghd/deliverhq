# CR-EXAMPLE: 实现待办事项 CRUD 接口

> 本目录是一个完整的 CR 示例，展示 DeliverHQ 工作流从需求到交付的全过程。

## 示例背景

- **项目**：TodoApp（待办事项管理系统）
- **技术栈**：Python 3.11 + FastAPI + PostgreSQL
- **需求**：实现待办事项的增删改查接口

## 文件说明

| 文件 | 说明 |
|---|---|
| request.md | 需求输入 |
| acceptance-spec.md | 验收规格 |
| context-summary.md | 上下文摘要 |
| implementation-plan.md | 实施计划 |
| test-plan.md | 测试计划 |
| design/ | 设计产物 |
| traceability.yml | 可追溯性映射 |
| human-decisions.md | 人工决策记录 |
| exceptions.yml | 规则豁免 |
| quality-report.md | 质量报告 |
| writeback-report.md | 归档报告 |
| *gate-report.md | 各门禁检查结果 |

## 如何参考

1. 阅读 request.md 了解需求格式
2. 阅读 acceptance-spec.md 了解验收规格写法
3. 阅读各 gate 报告了解门禁检查产出格式
4. 创建自己的 CR 时使用 `init_cr.py` 从 CR-TEMPLATE 初始化
