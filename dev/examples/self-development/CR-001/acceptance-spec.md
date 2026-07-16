# Acceptance Spec: 升级项目使用 DeliverHQ v4.6 框架

> 由 Spec Agent 产出。将 `request.md` 转化为可测试的验收规格（SDD 三段式）。

## CR-ID
CR-001

## 1. Data Spec（数据规格）

### Entities（实体）
| 实体名 | 说明 | 关键字段 |
|--------|------|----------|
| CR (Change Request) | 变更请求 | id, title, status, phase |
| Gate | 质量门禁 | name, type, status, blockers |
| Document | 文档 | path, type, template_vars, content |
| Memory | 组织记忆 | type, date, content, linked_cr |

### Fields & Constraints（字段与约束）
| 实体.字段 | 类型 | 约束 | 默认值 | 说明 |
|-----------|------|------|--------|------|
| CR.id | string | NOT NULL, UNIQUE | - | CR-{序号} 格式 |
| CR.status | enum | NOT NULL | DRAFT | DRAFT/IN_PROGRESS/DONE |
| CR.phase | enum | NOT NULL | SPEC | SPEC/DESIGN/DEV/TEST/QUALITY/DEPLOY/WRITEBACK |
| Gate.status | enum | NOT NULL | PENDING | PASS/BLOCKED/WARNING |
| Document.template_vars | list | - | [] | 待替换的模板变量 |
| Memory.type | enum | NOT NULL | - | decision/mistake/rule/state |

### State Transitions（状态转换）
| 实体 | 初始状态 | 允许转换 | 触发条件 | 终态 |
|------|----------|----------|----------|------|
| CR | DRAFT | DRAFT→IN_PROGRESS | pre_dev_gate PASS | IN_PROGRESS |
| CR | IN_PROGRESS | IN_PROGRESS→DONE | all Gates PASS | DONE |
| Gate | PENDING | PENDING→PASS | 检查通过 | PASS |
| Gate | PENDING | PENDING→BLOCKED | 发现阻断项 | BLOCKED |
| Document | HAS_VARS | HAS_VARS→READY | 替换所有模板变量 | READY |

### Data Invariants（数据不变式）
- CR.phase 必须按顺序推进：SPEC → DESIGN → DEV → TEST → QUALITY → DEPLOY → WRITEBACK
- Gate.status = BLOCKED 时，CR 不能进入下一阶段
- Document 包含模板变量时，pre_dev_gate 必须 BLOCKED
- Memory.linked_cr 必须是有效的 CR.id

---

## 2. Interface Spec（接口规格）

### CLI Commands

| 命令 | 参数 | 功能 | 返回 |
|------|------|------|------|
| init_cr.py | CR_ID, TITLE, AUTHOR | 创建新 CR | 退出码 0/1 |
| pre_dev_gate.py | CR_ID | 开发前检查 | PASS/BLOCKED + 阻断项列表 |
| specgate.py | SPEC_PATH | 验收规格检查 | PASS/BLOCKED + 问题列表 |
| qualitygate.py | CR_PATH | 质量门禁检查 | PASS/BLOCKED + 覆盖率 |
| deploygate.py | CR_PATH | 部署就绪检查 | PASS/BLOCKED + 缺失项 |
| selftest.py | [--routing-eval] | 框架健康检查 | 通过数/总数 |

### Input Schema

**init_cr.py**
```bash
python scripts/init_cr.py <CR_ID> "<TITLE>" "<AUTHOR>"
# CR_ID: 格式 CR-\d{3}
# TITLE: string, 非空
# AUTHOR: string, 非空
```

**specgate.py**
```bash
python scripts/specgate.py <SPEC_PATH>
# SPEC_PATH: acceptance-spec.md 路径
# 环境变量: DELIVERHQ_STRICT_MODE=0|1
```

### Output Schema

**成功输出**
```
✅ PASS - {描述}
退出码: 0
```

**阻断输出**
```
❌ BLOCKED
  1. {阻断原因1}
  2. {阻断原因2}
⛔ {下一步建议}
退出码: 1
```

### Error Codes
| 错误码 | 退出码 | 说明 | 处理方式 |
|--------|--------|------|----------|
| MISSING_FILE | 1 | 必需文件不存在 | 补充缺失文件 |
| HAS_TEMPLATE_VARS | 1 | 包含未替换模板变量 | 填充所有模板占位符 |
| P0_UNRESOLVED | 1 | P0 问题未解决 | 解决 P0 Open Questions |
| COVERAGE_LOW | 1 | 测试覆盖率 < 80% | 补充测试用例 |

### Idempotency & Side Effects
- **幂等性**：所有 Gate 脚本是幂等的，多次运行结果一致
- **副作用**：
  - init_cr.py：创建目录和文件
  - qualitygate.py（失败时）：自动追加到 mistake-book.md
  - 其他 Gate：只读检查，无副作用

### Permission Requirements
| 操作 | 需要权限 | 验证方式 |
|------|----------|----------|
| init_cr | 文件系统写权限 | 操作系统权限 |
| Gate 脚本 | 文件系统读权限 | 操作系统权限 |
| writeback | Git 提交权限 | Git 配置 |

---

## 3. Behavior Spec（行为规格）

### 场景 1：成功创建并完成 CR（正常流程）
- **Given** DeliverHQ v4.6 已解压到项目根目录，selftest 9/9 通过
- **When** 执行 `python scripts/init_cr.py CR-001 "升级框架" "Kiro"`，填写 request.md 和 acceptance-spec.md，依次通过所有 Gate
- **Then** CR-001 目录包含所有必需文件，所有模板变量已替换，所有 Gate 返回 PASS，docs/MEMORY.md 记录 CR 状态
- **Measurable Success** init_cr 执行时间 < 5秒，pre_dev_gate 检查时间 < 3秒，CR 完整流程可在 3小时内完成

### 场景 2：Gate 正确阻断不合格文档（异常流程）
- **Given** CR-001 的 acceptance-spec.md 包含未替换的模板占位符（双花括号格式）
- **When** 执行 `python scripts/pre_dev_gate.py CR-001`
- **Then** 返回退出码 1，输出 "❌ BLOCKED"，明确列出阻断原因 "acceptance-spec.md 包含未解决的占位符"
- **Measurable Success** 100% 的模板变量被检测到，阻断信息清晰可操作

### 场景 3：反例验证机制生效（边界情况）
- **Given** CR-BLOCKED-EXAMPLE 存在，包含故意的错误（模板变量、P0 未解决、模糊词）
- **When** 执行 `python scripts/specgate.py change-requests/CR-BLOCKED-EXAMPLE/acceptance-spec.md`
- **Then** 返回退出码 1，输出 "❌ BLOCKED"，检测到所有故意的错误
- **Measurable Success** selftest 中 `cr_blocked_blocked` 测试通过，反例拦截率 100%

### 场景 4：SDD 三段式规格验证（正常流程）
- **Given** acceptance-spec.md 使用 SDD 三段式结构（Data + Interface + Behavior）
- **When** 执行 `DELIVERHQ_STRICT_MODE=1 python scripts/specgate.py CR-001/acceptance-spec.md`
- **Then** SpecGate 检查 Data Spec、Interface Spec、Behavior Spec 完整性，检测模糊词和 P0 问题
- **Measurable Success** 缺少任一 Spec → BLOCKED，包含模糊词无量化 → BLOCKED

### 场景 5：动态状态记录（正常流程）
- **Given** CR-001 正在进行中
- **When** 通过一个 Gate 或遇到阻塞
- **Then** docs/MEMORY.md 更新"当前活跃 CR"、"最后通过的 Gate"、"当前阻塞"
- **Measurable Success** MEMORY.md 记录准确，可追溯 CR 当前状态

---

## 非功能验收

| 维度 | 指标 | 验收标准 |
|---|---|---|
| 性能 | selftest 执行时间 | < 30 秒 |
| 性能 | init_cr 执行时间 | < 5 秒 |
| 性能 | Gate 检查时间 | < 3 秒/Gate |
| 易用性 | 首次创建 CR | < 5 分钟（含学习） |
| 可靠性 | Gate 反例拦截率 | 100% |
| 可靠性 | selftest 通过率 | 9/9 = 100% |
| 兼容性 | Git 工作流 | 不破坏现有流程 |
| 可维护性 | 文档完整性 | 所有 Gate 有 SKILL.md 说明 |

---

## 依赖项

| 依赖 | 类型 | 状态 | 责任人 |
|---|---|---|---|
| Python 3.6+ | 运行时 | 已就绪 | 系统管理员 |
| deliverhq-v4.6.tar.gz | 软件包 | 已准备 | Kiro AI |
| Git | 版本控制 | 已就绪 | 系统管理员 |
| 文件系统读写权限 | 权限 | 已就绪 | 开发者 |

---

## 模糊点与待确认项

> Spec Agent 识别出的需求不明确之处，需人工澄清。

### Facts（已确认事实）
> 从需求文档、现有系统、架构文档中确认的客观事实

| # | 事实 | 来源 | 确认人 | 日期 |
|---|------|------|--------|------|
| F1 | DeliverHQ v4.6 包大小 145 KB | deliverhq-v4.6.tar.gz | Kiro AI | 2026-06-13 |
| F2 | selftest 包含 9 项检查 | scripts/selftest.py | Kiro AI | 2026-06-13 |
| F3 | SDD 三段式为 Data/Interface/Behavior | CR-TEMPLATE/acceptance-spec.md | Kiro AI | 2026-06-13 |
| F4 | 严格模式通过环境变量 DELIVERHQ_STRICT_MODE 控制 | scripts/specgate.py | Kiro AI | 2026-06-13 |

### Assumptions（假设前提）
> AI 为推进实现而做出的合理假设，需标注为假设而非事实

| # | 假设 | 风险级别 | 验证方式 | 验证期限 | 状态 |
|---|------|----------|----------|----------|------|
| A1 | 项目根目录有足够空间（> 1 MB）存放 DeliverHQ | P2 | 解压前检查磁盘空间 | 2026-06-13 | verified |
| A2 | Python 3.6+ 已安装且在 PATH 中 | P1 | python --version | 2026-06-13 | verified |
| A3 | 开发者熟悉 Git 和 Markdown | P2 | 培训或文档 | 2026-06-14 | pending |

### Open Questions（待确认问题）
> 需求不明确之处，阻碍实现或影响决策的问题

| # | 问题 | 阻断级别 | 负责人 | 截止日期 | 状态 |
|---|------|----------|--------|----------|------|
| Q1 | 是否需要为团队提供 SDD 三段式培训？ | P2 | Kiro AI | 2026-06-14 | resolved（暂不需要，先试点） |
| Q2 | 是否启用严格模式作为默认？ | P2 | Kiro AI | 2026-06-14 | resolved（先用 WARNING 模式） |

---

## 可测试性

- [x] 每个验收条件可自动化测试（selftest 覆盖）
- [x] 边界条件可重现（CR-BLOCKED-EXAMPLE）
- [x] 性能指标可量化验证（执行时间可测量）
- [x] 数据约束可验证（Gate 脚本检查）
- [x] 接口契约可验证（CLI 返回码和输出格式）

---

## SpecGate 检查点

- [x] Data Spec 完整（实体、字段、约束、状态转换）
- [x] Interface Spec 完整（CLI、Input/Output、错误码、权限）
- [x] Behavior Spec 完整（5 个场景：正常/异常/边界/SDD验证/状态记录）
- [x] 验收条件明确，无待确认占位符
- [x] P0 Open Questions 已解决（status = resolved）
- [x] P0 Assumptions 已验证（status = verified）
- [x] 无模糊词或已量化（所有指标明确：< 30秒、< 5秒、100%）
- [x] 依赖项状态已确认（所有依赖已就绪）
- [x] 非功能需求已量化（性能/易用性/可靠性均有具体指标）

**SpecGate 状态**：READY
