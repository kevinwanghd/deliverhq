# Acceptance Spec: 证据化 Bootstrap、轻路由与 Brownfield 护栏

## CR-ID
CR-006

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
| BootstrapReport | repo, documents, stack, commands, abstractions, warnings, evidence | 每个 confirmed finding 至少有 path 和 sha256 |
| RouteDecision | lane, reasons, required_gates, skipped_gates, estimated_cost, confidence | required 与 skipped 不相交 |
| PlanTask | read_files, write_files, reuse_checks, destructive_change | write_files 为硬边界 |
| ContextHandoff | current_phase, previous_phase, sources, input_hashes, excluded_approaches, next_action | input hash 必须对应当前文件 |

### State Transitions

```text
bootstrap scan → report-only → user-confirmed apply → candidate artifacts
context current → upstream changed → stale/BLOCKED → refreshed → current
```

### Data Invariants

- Bootstrap 默认不写文件。
- `--apply` 不覆盖已有人工文件，冲突目标写 `.candidate`。
- 不新增 Gate，不复制 Legacy Scan 的扫描实现。

## 2. Interface Spec（接口规格）

### CLI

| Interface | 输入 | 输出 |
|---|---|---|
| `deliverhq bootstrap` | `--path`, `--json`, `--apply` | BootstrapReport 与写入结果 |
| `deliverhq route` | request, `--json` | 向后兼容的 RouteDecision 扩展 |
| `plan_checker.py` | CR/plan path | PASS/BLOCK 与证据缺口 |
| `context_window_check.py` | CR path | PASS/BLOCK 与 stale sources |

### Error Modes

- 无效 repo path：退出码 2，输出 `invalid_repository_path`。
- confirmed finding 缺证据：Bootstrap 输出 warning，不写为 confirmed。
- input hash 不一致：ContextWindowGate 返回非零。
- Brownfield task 缺 reuse check，或破坏性变更缺 reference scan：PlanChecker 返回非零。

### Side Effects

- `bootstrap` 默认幂等且无副作用。
- `bootstrap --apply` 仅写 DeliverHQ 治理目录，采用 create-only/candidate 语义。

## 3. Behavior Spec（行为规格）

### AC-1：只读入场扫描
- **Given** 临时仓库含 package.json、AGENTS.md 和测试目录
- **When** 执行 `deliverhq bootstrap --path <repo> --json`
- **Then** 返回确定性报告，列出文档、技术栈、命令和证据，仓库文件集合及内容哈希不变
- **Measurable Success** 连续执行两次除时间字段外 JSON 相同

### AC-2：候选写入不覆盖人工文件
- **Given** 宿主 `DeliverHQ/CONTEXT.md` 已存在
- **When** 执行 bootstrap `--apply`
- **Then** 原文件字节不变，新结果写入候选文件并报告 conflict
- **Measurable Success** 原文件 SHA-256 前后相同

### AC-3：轻路由展示成本和 Gate 计划
- **Given** 小修复、标准功能和高风险迁移三类请求
- **When** 执行 route JSON
- **Then** 返回 lane、理由、required_gates、skipped_gates、token/time 区间和 confidence
- **Measurable Success** 三类 fixture 分别命中 fast、standard、high-risk，旧字段仍存在

### AC-4：计划读写范围与复用证据
- **Given** Brownfield task 声明 write_files
- **When** 缺 read_files 或 reuse_checks
- **Then** PlanChecker BLOCK；补齐可判定命令和结果后 PASS
- **Measurable Success** 正反例契约测试退出码分别为 0 和非 0

### AC-5：破坏性变更证据
- **Given** task 声明公共 Interface、Schema、文件删除或 protected path 变更
- **When** reference_scan 或人工决策缺失
- **Then** PlanChecker BLOCK
- **Measurable Success** 语义风险触发，不以固定删除行数作为唯一条件

### AC-6：Context 恢复与漂移检测
- **Given** context handoff 记录来源哈希、当前/上一阶段、已排除方案和 next_action
- **When** 上游文件改变或加载超过两个完整阶段
- **Then** ContextWindowGate BLOCK 并指出 stale source 或 phase overflow
- **Measurable Success** 正常、哈希漂移、阶段超窗三类 fixture 均有确定性结果

## 非功能验收

- Python 3.10+，Windows/macOS/Linux 路径兼容。
- 不增加第三方运行时依赖。
- `python skill/scripts/selftest.py skill`、Python tests、Node entrypoint tests 全部通过。
- 现有 route JSON fixture 保持兼容。

## 依赖项

- Python 标准库、Node 标准库、现有 PyYAML：已就绪。
- `scan_legacy.py`、`scan_legacy_structure.py`、routing module：已就绪。

## 模糊点与待确认项

### Facts

- F1：flow-kit 为纯 Markdown 约束，DeliverHQ 保留确定性 Gate。
- F2：Kevin 已在 2026-07-12 授权完成全部借鉴项并验收后提交 GitHub。

### Assumptions

- A1（P1，verified）：GitHub 提交指推送功能分支并创建 Draft PR，不自动合并。

### Open Questions

- 无阻断问题。

## 可测试性

- [x] 每个 AC 有正反例
- [x] 文件副作用可通过 SHA-256 验证
- [x] Gate 结果可通过退出码验证
- [x] 路由保持 JSON 契约兼容

**SpecGate 状态**：READY
