---
name: deliverhq
description: AI 交付防翻车治理框架。文档驱动开发 + 可执行门禁(SpecGate/QualityGate/ReviewGate 等，信证据不信声明) + 老项目逆向(代码→需求文档) + loop 可控性(目标契约/反钻空子/重试上限)。当需要正式多阶段交付、强制"文档不完备不开发"、把老项目转成需求驱动、或防止 AI 钻空子/无限重试时使用。需要 Python 3.6+ 与 PyYAML。
license: 见仓库
---

# SKILL.md — DeliverHQ 入口

> **目标**：通过结构化规格（SDD）、可执行门禁（Gate）、职责边界（Agent）、执行隔离（Workspace）和组织记忆（Writeback），实现 AI 全流程交付质量可控。

## 何时使用 DeliverHQ

✅ **应该使用**：
- 为项目启用"文档门禁式交付流程"
- 扫描老项目的技术债和代码健康度
- 创建需要多阶段协作的 Change Request
- 运行 SpecGate/DesignGate/QualityGate 门禁检查
- 强制执行"文档不完备不开发"规则
- 需要团队协作的正式功能开发

❌ **不应该使用**：
- 只读分析、简单解释、文档错别字修复
- 一次性临时脚本、不涉及项目源码的任务
- 紧急 hotfix（事后补文档）
- 用户明确说"不要启动 DeliverHQ 流程"

---

## 能力状态说明

> **单一事实源**：能力状态以 `CAPABILITY-MATRIX.md` 为准。入口文档只保留最小判断，避免把 roadmap/experimental 写成默认可用。

### 默认可用

- CR 初始化和状态机：`init_cr.py` / `cr_state.py`
- 核心 Gate：SpecGate、PreDevGate、ReviewGate、QualityGate、WritebackGate
- DevPhase Handoff：`dev_phase.py` 只做开发交接，不自动写代码
- Gate Contract / selftest：验证脚本存在、参数契约和默认 pipeline 契约

### 需要谨慎

- DesignGate / DeployGate / PermissionGate / Orchestrator：已接入但仍按 experimental 使用；PermissionGate 只是最小权限边界检查，不是深度自动化安全能力
- Worktree Manager：是工具，不是 Dev Agent；不要把它直接放进 pipeline 当开发阶段
- Failure Attribution / mistake-book dedup：已接入基础链路，但规则演进仍需人工复核

### 不进默认阻断链路

- Routing Eval JSON 化、Context schema、MaintenanceGate：后续优化
- Darwin Score / Quality Ratchet：只做报告观察，不硬阻断
- Dynamic Workflow / Tournament / Fan-out / Scout：roadmap，不承诺可用

---

## 四种核心模式

### 模式 1：初始化新项目

**场景**：为新项目启用 DeliverHQ 治理。

**步骤**：
1. 将 `DeliverHQ/` 目录复制到项目根目录
2. 运行骨架检查：`python DeliverHQ/scripts/check_skeleton.py DeliverHQ`
3. 填写 `DeliverHQ/docs/CONTEXT.md`（项目上下文）
4. 调整 `DeliverHQ/dir-graph.yaml`（权限路径）
5. 自检通过：`python DeliverHQ/scripts/selftest.py`

**产出**：开箱即用的治理框架。

---

### 模式 2：扫描老项目

**场景**：分析现有项目的代码健康度。

**步骤**：
1. 运行扫描 Agent：让 Scan Agent 分析项目源码、Git 历史、依赖
2. Scan Agent 生成 `DeliverHQ/docs/reports/code-health-report.md`
3. 生成 `DeliverHQ/docs/reports/legacy-scan-report.md`
4. 人工审核报告，决定是否启动改造 CR

**产出**：技术债清单 + 改进建议。

---

### 模式 3：创建/推进 CR

**场景**：新功能开发、Bug 修复、重构。

**步骤**：
1. 创建 CR：`python scripts/init_cr.py CR-001 "需求名称" "提出人"`
2. 填写 `change-requests/CR-001/request.md`
3. Spec Agent 生成 `acceptance-spec.md`
4. 运行 SpecGate：`python scripts/specgate.py change-requests/CR-001/acceptance-spec.md`
5. 开发前运行：`python scripts/pre_dev_gate.py CR-001 --lane standard`
6. 开发交接：`python scripts/dev_phase.py change-requests/CR-001`
7. `dev_phase.py` 输出 worktree/上下文路径后停止；不会自动写代码或跳到 Review。

**产出**：可测试的验收规格 + 实施计划 + 可回写状态。

---

### 模式 4：运行 Gate 检查

**场景**：阶段切换前验证文档完备性。

**核心 Gates**：
```bash
# 验收规格完备性
python scripts/specgate.py change-requests/CR-001/acceptance-spec.md

# 设计产物完备性（C 端强制高保真）
python scripts/designgate.py change-requests/CR-001

# 开发前综合检查
python scripts/pre_dev_gate.py CR-001

# 上下文窗口纪律
python scripts/context_window_check.py change-requests/CR-001

# 代码审查门禁（对抗式验证）
python scripts/reviewgate.py change-requests/CR-001

# 质量门禁（默认 hybrid，必须执行 verification-manifest.yml）
python scripts/qualitygate.py change-requests/CR-001

# 部署就绪检查
python scripts/deploygate.py change-requests/CR-001

# 知识沉淀完整性
python scripts/writeback_gate.py change-requests/CR-001
```

**结果**：PASS（放行）/ BLOCKED（阻断，提示缺失项）

**重要**：ReviewGate 实现对抗式验证 - Dev Agent 实现代码，Review Agent 独立挑刺，确保"干活的人和验收的人不是同一个 agent"。

---

## 必读文件（按需加载）

| 文件 | 何时读 | 用途 |
|---|---|---|
| `AGENTS.md` | 开发前 | 9 个 Agent 职责边界 |
| `dir-graph.yaml` | 开发前 | 权限路径、protected_paths |
| `docs/CONTEXT.md` | 任何时候 | 项目上下文、技术栈 |
| `docs/rules.md` | 开发/Review | Canonical 编码规则（只读） |
| `docs/rules-candidates.md` | Writeback | 候选规则沉淀（AI 可写） |
| `docs/decisions.md` | 设计阶段 | 历史架构决策 |
| `docs/mistake-book.md` | QualityGate 失败后 | 错误案例库 |
| `references/gotchas.md` | 遇到问题时 | 真实踩坑经验 |

**原则**：不要一次性加载 47 个文件，只加载当前阶段必需文件。

---

## 常见坑（Gotchas）

### 1. 路径依赖问题
❌ **错误**：脚本依赖 `cwd`，从不同目录调用会失败。
✅ **正确**：所有脚本使用 `Path(__file__).parent.parent` 定位 DeliverHQ 根目录。

```python
# 所有脚本开头
from pathlib import Path
DELIVERHQ_ROOT = Path(__file__).parent.parent
```

### 2. Windows 兼容性
❌ **错误**：文档写 `python3 scripts/xxx.py`（Windows 没有 python3）
✅ **正确**：优先写 `python scripts/xxx.py`，或提示 Windows 用户配置 `python3` 别名。

### 3. SpecGate 误判
❌ **错误**：把说明文字里的"待确认"误判为未解决项。
✅ **正确**：只检查表格状态列 `| 待确认 |`，用正则 `r'\|\s*待确认\s*\|'`。

### 4. 模板变量误判
❌ **错误**：把合法代码示例里的 `{{}}` 误判为模板变量。
✅ **正确**：只检查 Markdown 文本区域，排除代码块。

### 5. 不要直接修改 CR-TEMPLATE
❌ **错误**：用户直接改 `CR-TEMPLATE/`，导致后续 CR 继承错误。
✅ **正确**：复制 `CR-TEMPLATE` → `CR-001`，再修改。

### 6. DeliverHQ vs 项目根 docs
❌ **错误**：DeliverHQ 覆盖项目根目录的 `docs/` 约定。
✅ **正确**：`DeliverHQ/docs` 是治理记忆，项目根 `docs/` 是权威工程约定，互补不覆盖。

### 7. 纯后端项目不强制 DesignGate
❌ **错误**：后端 API 项目也要求高保真设计稿。
✅ **正确**：DesignGate 检查 `metadata.yml` 的 `ui_type: none`，纯后端可跳过。

### 8. QualityGate 自动写入副作用
❌ **错误**：QualityGate 失败自动写 `mistake-book.md`，用户未预期。
✅ **正确**：通过环境变量 `DELIVERHQ_AUTO_MISTAKE_BOOK=0` 可禁用。

### 9. 过度治理问题
❌ **错误**：改一个 README 错别字也启动完整 CR 流程。
✅ **正确**：轻量任务不强制进 DeliverHQ，保持灵活性。

### 10. workflow_router 是建议器，不是自动拦截器
❌ **错误**：把 `workflow_router.py` 接成后台扫描或自动创建 CR。
✅ **正确**：只在不确定是否启用 DeliverHQ、准备写代码、准备提交等关键事件上手动运行，读取 JSON 建议后再决定。

---

## 验证 Checklist

### 初始化后验证
- [ ] `python scripts/check_skeleton.py DeliverHQ` 输出 `47/47`
- [ ] `docs/CONTEXT.md` 已填写项目信息
- [ ] `dir-graph.yaml` 的 `protected_paths` 已配置
- [ ] 无模板变量残留（`grep -r "{{.*}}" DeliverHQ/docs/`）

### 创建 CR 后验证
- [ ] `change-requests/CR-001/request.md` 已填写
- [ ] 运行 `pre_dev_gate.py CR-001` 不报错
- [ ] `acceptance-spec.md` 无 `[待确认]` 占位符

### 开发前验证
- [ ] SpecGate PASS
- [ ] DesignGate PASS（如有 UI）
- [ ] ContextWindowGate PASS

### 交付前验证
- [ ] QualityGate PASS（默认 hybrid；执行 verification-manifest.yml 里的真实命令）
- [ ] WritebackGate PASS（规则/决策已沉淀）
- [ ] 运行 `python scripts/selftest.py` 全部通过

---

## 最小使用路径（你只需要记住三件事）

1. **所有开发先建 CR**
2. **CR 没有验收规格，不准写代码**
3. **每次交付后，把规则先写入 `docs/rules-candidates.md`，其他经验写回 mistake-book / decisions**

### 最常用三条命令

```bash
# 0. 可选：不确定是否启用 DeliverHQ 时，先看低噪路由建议
python scripts/workflow_router.py "用户请求"

# 1. 创建 CR
python scripts/init_cr.py CR-001 "需求名称" "提出人"

# 2. 开发前检查
python scripts/pre_dev_gate.py CR-001

# 3. 验收规格检查
python scripts/specgate.py change-requests/CR-001/acceptance-spec.md
```

---

## 一键自检

```bash
python scripts/selftest.py
```

输出：
- ✅ 骨架完整（47/47）
- ✅ 示例 CR 可通过
- ✅ 所有 Gate 行为正常
- ✅ 脚本可从任意 cwd 调用
- ✅ 无模板变量残留

---

## 深入阅读

需要了解更多时，按需阅读：

- `references/modes.md` — 四种模式详解
- `references/gates.md` — 5 个 Gate 详解
- `references/gotchas.md` — 完整踩坑经验
- `references/file-structure.md` — 47 个文件说明
- `references/examples.md` — Before/After 案例

---

**版本**：v5.0.0  
**更新日期**：2026-06-14  
**一句话**：文档门禁 + 动态多 Agent 工作流编排 + 对抗式验证。
