# Acceptance Spec: 统一入口、验证闭环与记忆生命周期基础

## CR-ID
CR-007

## 来源锚点（derived_from）

```yaml
derived_from:
  prd_section: PRD-BOOTSTRAP
  prd_hash: 4474ae554a8a
```

## 1. Data Spec（数据规格）

### Entities

| Entity | 关键字段 | 不变式 |
|---|---|---|
| GoDecision | prompt, engagement_mode, risk_lane, current_cr, target_phase, artifact_preflight, recommended_command | 默认只读；缺工件时 can_proceed=false |
| ArtifactPreflight | required, present, missing, recovery_action, can_proceed | missing 与 present 不重叠 |
| LessonEntry | id, fingerprint, type, content, root_cause, status, occurrences, timestamps, tags, evidence | fingerprint 稳定；occurrences >= 1；状态枚举有效 |
| WorktreeRequest | cr_id, base_branch | CR-ID 符合统一格式；未传分支时自动探测 |

### State Transitions

```text
natural-language request → route → state discovery → artifact preflight → proceed | recover
lesson active → superseded | deprecated
repeated lesson fingerprint → occurrences + 1, last_seen 更新
```

### Data Invariants

- `go` 不带显式写入选项时不修改 CR、STATE 或源码。
- `artifact_preflight.can_proceed` 当且仅当 `missing` 为空。
- 旧 MemoryEntry 缺少新增字段时以安全默认值加载。

## 2. Interface Spec（接口规格）

### CLI Signature

| 接口 | 输入 | 输出 |
|---|---|---|
| `npx deliverhq go <request> [--path <repo>] [--json]` | 自然语言与项目路径 | GoDecision |
| `MemoryStore.add(...)` | 记忆内容、类型、根因、状态、证据 | LessonEntry |
| `WorktreeManager.create(...)` | CR-ID、可选基准分支 | WorktreeInfo 或明确异常 |

### Error Contract

- 找不到项目内 DeliverHQ 核心时返回非零退出码和候选修复路径。
- 多个活跃 CR 且请求未能消歧时返回 `needs_human=true`，不得猜测。
- 非法 CR-ID 在执行任何 Git 命令之前抛出 ValueError。

### Idempotency & Side Effects

- `go --json` 幂等且只读。
- 相同 lesson 指纹重复添加只更新计数和时间，不新增条目。
- 本 CR 不引入网络调用或新的第三方依赖。

### Permission Requirements

- CLI 只读取用户指定仓库及其 DeliverHQ 状态。
- 记忆默认写入显式 DeliverHQ home 下的 `memory/`；不默认写入 `.claude/`。

## 3. Behavior Spec（行为规格）

### AC-1：统一入口路由并预检工件
- **Given** 项目存在 DeliverHQ 核心和一个可识别的活跃 CR
- **When** 用户执行 `deliverhq go "继续" --json`
- **Then** 输出当前 CR、目标阶段、required/present/missing、can_proceed 和下一条具体命令
- **Measurable Success** JSON schema 测试通过且命令中无 `<CR>` 占位符

### AC-2：缺失工件时安全回退
- **Given** 目标阶段需要的工件缺失
- **When** 执行 `go`
- **Then** 返回 `can_proceed=false`、缺失列表和补齐工件的 recovery_action，不执行 Gate
- **Measurable Success** 文件系统快照前后无变化

### AC-3：测试与跨平台可靠性闭环
- **Given** 仓库默认分支不是 master 且测试生成 `__pycache__`
- **When** 执行 pytest 和 selftest
- **Then** worktree 使用探测到的分支，缓存不造成发布卫生误报，全部测试通过
- **Measurable Success** pytest 0 failures；selftest 37/37 或更新后的完整计数全部通过

### AC-4：结构化 lesson 去重和生命周期
- **Given** 两条内容措辞不同但根因指纹相同的 lesson
- **When** 重复写入 MemoryStore
- **Then** 只保留一个条目，occurrences 增加，支持 superseded/deprecated，旧索引仍可读取
- **Measurable Success** 单元测试覆盖新增、重复、迁移和非法状态四条路径

### AC-5：兼容现有入口
- **Given** 已有 route/bootstrap/doctor/selftest 使用方式
- **When** 完成升级
- **Then** 既有入口测试不回归，5 动词和 Gate 冻结集合不变化
- **Measurable Success** `tests/` 与 selftest 契约全部通过

## 非功能验收

| 维度 | 验收标准 |
|---|---|
| 兼容性 | Python 3.10+、Node.js 14+；旧 memory index 可加载 |
| 可观测性 | `go --json` 输出确定性字段；错误返回非零状态 |
| 安全性 | 默认只读；不自动创建或推进 CR |
| 维护性 | 新逻辑落入可导入模块，CLI 保持薄包装 |

## 依赖项

| 依赖 | 类型 | 状态 | 责任人 |
|---|---|---|---|
| Python 标准库、PyYAML | 内部既有 | 已就绪 | Dev Agent |
| Node.js CLI 包装 | 内部既有 | 已就绪 | Dev Agent |

## 模糊点与已确认事实

### Facts

| # | 事实 | 来源 | 确认人 | 日期 |
|---|---|---|---|---|
| F1 | 不新增 Gate，优先优化入口和证据闭环 | 用户指令与分析结论 | 用户 | 2026-07-13 |
| F2 | 当前 pytest 存在 1 个失败，自检存在缓存卫生误报 | 本地真实执行 | Codex | 2026-07-13 |

### Assumptions

| # | 假设 | 风险 | 验证方式 | 状态 |
|---|---|---|---|---|
| A1 | 第一批覆盖三个 P0 基础切片符合“开始优化”的范围 | P1 | 以独立 CR 和兼容测试控制范围 | verified |

### Open Questions

无阻断问题。

## 可测试性

- [x] 每个验收条件可自动化测试
- [x] 边界条件可重现
- [x] 数据约束可验证
- [x] 接口契约可验证

**SpecGate 状态**：READY
