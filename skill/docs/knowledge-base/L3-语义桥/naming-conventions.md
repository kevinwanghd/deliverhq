# 命名规范（Naming Conventions）

> 设计 token → 代码实现的规范。

## 脚本命名

| 类型 | 命名模式 | 示例 |
|------|----------|------|
| Gate 脚本 | `{name}gate.py` | `specgate.py`, `qualitygate.py` |
| 编排脚本 | `{name}.py` | `deliver.py`, `orchestrator.py` |
| 检查脚本 | `check_{name}.py` | `check_skeleton.py` |
| 更新脚本 | `update_{name}.py` | `update_mistake_book.py` |

## 文档命名

| 类型 | 命名模式 | 示例 |
|------|----------|------|
| Gate 报告 | `{gate}-report.md` | `specgate-report.md` |
| 阶段报告 | `{phase}-report.md` | `context-window-report.md` |
| 配置文档 | `{name}.md` | `AGENTS.md`, `CONTEXT.md` |

## 目录命名

| 类型 | 命名模式 | 示例 |
|------|----------|------|
| CR 目录 | `CR-XXX/` | `CR-001/`, `CR-042/` |
| 设计稿 | `design/` | CR 内的设计稿目录 |
| 证据 | `evidence/` | CR 内的证据目录 |
| 知识库 | `knowledge-base/` | 三级知识库根目录 |

## YAML 配置

| 类型 | 命名模式 | 示例 |
|------|----------|------|
| 治理配置 | `governance.config.yml` | 红线、Human Checkpoint |
| 目录图 | `dir-graph.yaml` | 权限路径配置 |
| 状态文件 | `state.yml` | CR 生命周期状态 |
| 目标契约 | `goal-contract.yml` | 循环治理目标 |

## 红线 ID 命名

| 类型 | 命名模式 | 示例 |
|------|----------|------|
| Critical | `RL-C{XX}` | `RL-C01`, `RL-C06` |
| Standard | `RL-S{XX}` | `RL-S01`, `RL-S08` |

## 硬关卡 ID 命名

| 类型 | 命名模式 | 示例 |
|------|----------|------|
| Human Checkpoint | `HK-{X}` | `HK-0`, `HK-1`, `HK-2`, `HK-3` |
