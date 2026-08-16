# L2 模块级 — skill/scripts 脚本分类索引

> 文件粒度的"街道地图"。每个脚本的元数据：module_id / root_dirs / desc。

## 脚本分类

### 门禁类（Gate）

| 脚本 | 职责 | 输入 | 输出 |
|------|------|------|------|
| `specgate.py` | 验收规格完备性 | acceptance-spec.md | specgate-report.md |
| `designgate.py` | UI 设计产物完备 | design/ | designgate-report.md |
| `pre_dev_gate.py` | 开发前文档完备 | CR/ | state.yml |
| `qualitygate.py` | 代码质量门禁 | quality-report.md | qualitygate-report.md |
| `writeback_gate.py` | 知识沉淀完整性 | writeback-report.md | writeback-gate-report.md |
| `reviewgate.py` | 对抗式代码审查 | CR/ | review-report.md |

### 编排类（Orchestration）

| 脚本 | 职责 | 说明 |
|------|------|------|
| `skill_orchestrator.py` | 动词执行器 | 5 个动词的入口 |
| `deliver.py` | 智能路由器 | 根据上下文建议下一步 |
| `workflow_router.py` | 工作流路由 | 建议下一步操作 |

### 状态管理类

| 脚本 | 职责 | 说明 |
|------|------|------|
| `init_cr.py` | 初始化 CR | 创建 CR 目录和模板 |
| `cr_state.py` | CR 状态机 | 管理 CR 生命周期 |
| `handoff_state.py` | 交接状态 | Agent 间交接 |

### 验证类

| 脚本 | 职责 | 说明 |
|------|------|------|
| `evidence_gate.py` | sentinel 文件验证 | Evidence = 唯一判据 |
| `red_lines_check.py` | 红线检查 | Critical/Standard 红线 |
| `anti_gaming_check.py` | 反钻空子检查 | diff 取证 |
| `baseline_comparison.py` | 基线对比 | before/after 对比 |

### 辅助类

| 脚本 | 职责 | 说明 |
|------|------|------|
| `five_step_locator.py` | 五步定位法 | 300× Token 压缩 |
| `human_checkpoint.py` | 人工硬关卡 | HK-0/1/2/3 |
| `tech_spec_manager.py` | TECH_SPEC 管理 | 跨会话传承 |
| `scan_legacy.py` | 老项目扫描 | 生成 health report |
| `drift_check.py` | PRD↔CR 对账 | 漂移检测 |

### 知识管理类

| 脚本 | 职责 | 说明 |
|------|------|------|
| `update_mistake_book.py` | 错误案例库 | 记录错误 |
| `update_rule_maturity.py` | 规则成熟度 | 规则迭代 |
| `list_rule_candidates.py` | 候选规则 | 规则沉淀 |

---

*本文件是 L2 模块索引，用于快速定位脚本。*
