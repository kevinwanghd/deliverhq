# DeliverHQ 项目总览

> AI 入场的"大堂导览"。告诉 AI 项目有哪些模块、各自负责什么。

## 模块地图

| 模块 | 职责 | 详细文档 |
|------|------|----------|
| `skill/scripts/` | 核心脚本集（80+ 脚本） | 分类索引见 L2-模块级 |
| `skill/references/` | 流程细则引用 | references/*.md |
| `skill/references/red_lines/` | 红线体系 | red_lines/red_lines.yaml |
| `skill/references/red_lines_by_stage/` | 分阶段红线 | breakdown/implement/verify/... |
| `skill/change-requests/` | CR 模板和实例 | CR-TEMPLATE/ |
| `skill/context-packs/` | Agent context packs | dev-agent.md 等 |

## 关键概念

| 概念 | 说明 |
|------|------|
| **CR** | Change Request，一个需求/改动 |
| **Gate** | 门禁，检查点 |
| **Verb** | 5 个用户面动词：spec/design/dev/verify/archive |
| **Red Line** | AI 行为红线，违反即 fail_closed |

## 入口文件

| 文件 | 用途 |
|------|------|
| `SKILL.md` | 主入口，所有能力索引 |
| `AGENTS.md` | 9 个 Agent 职责边界 |
| `dir-graph.yaml` | 权限路径配置 |
| `governance.config.yml` | 红线配置（6 Critical + 8 Standard） |

## 快速命令

```bash
# 初始化新 CR
python skill/scripts/init_cr.py CR-001 "需求名称" "提出人"

# 执行动词链
python skill/scripts/skill_orchestrator.py verb dev change-requests/CR-001

# 检查红线
python skill/scripts/red_lines_check.py list

# 五步定位
python skill/scripts/five_step_locator.py "用户需求" --project-root .
```

---

*本文件是 L1 总览，用于 AI 快速定位入口模块。详细内容见 L2-模块级。*
