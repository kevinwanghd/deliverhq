# 术语表（Glossary）

> 业务术语 → 代码命名的映射表。

## DeliverHQ 核心术语

| 业务术语 | 代码对应 | 说明 |
|----------|----------|------|
| CR | Change Request | 一个需求/改动单元 |
| Gate | 门禁检查点 | SpecGate/DesignGate/QualityGate 等 |
| Verb | 用户面动词 | spec/design/dev/verify/archive |
| Red Line | AI 行为红线 | 禁止的行为规范 |
| TECH_SPEC | 技术规格文档 | 跨会话知识传承载体 |
| Subtask | 子任务 | CR 的拆分单元 |
| Lane | 开发通道 | fast/standard/high-risk |

## Agent 相关术语

| 业务术语 | 代码对应 | 说明 |
|----------|----------|------|
| Spec Agent | spec | 需求澄清、验收规格生成 |
| Dev Agent | dev | 开发执行 |
| Review Agent | review | 对抗式代码审查 |
| Quality Agent | quality | 质量门禁检查 |
| Writeback Agent | writeback | 知识沉淀归档 |

## 文件命名约定

| 概念 | 命名模式 | 示例 |
|------|----------|------|
| Gate 报告 | `{gate}-report.md` | `specgate-report.md` |
| 人工决策 | `human-decisions.md` | CR 内的人工审批记录 |
| 可追溯性 | `traceability.yml` | 需求→代码映射 |
| 演进日志 | `evolution-log.md` | TECH_SPEC 的 §7 演进事件 |

## 状态流转

| 状态 | 说明 | 触发 |
|------|------|------|
| `request` | 需求提出 | init_cr.py |
| `spec` | 规格定义 | specgate PASS |
| `dev` | 开发中 | pre_dev PASS |
| `review` | 代码审查 | dev 完成 |
| `quality` | 质量检查 | review PASS |
| `writeback` | 知识沉淀 | quality PASS |
| `done` | 完成 | writeback PASS |
