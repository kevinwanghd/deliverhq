# Changelog

本文件记录 **npm 包 `deliverhq`（安装器）** 的版本变化。
DeliverHQ 框架本身的版本见 `skill/VERSION.yml`（与安装器版本独立）。

版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## [5.6.0] - 2026-06-21

### 新增
- **Gate JSON evidence schema**：`gate_json_output.py` 成为最小 Gate evidence schema helper，并通过 `runtime_support.write_gate_evidence()` 集成。
- **ReviewGate 对抗式检查清单**：review 报告必须覆盖删测试、降阈值、绕 Gate、happy path only、边界遗漏等最小对抗检查。
- **dir-graph lint**：新增 `scripts/dir_graph_lint.py` 并接入 selftest，开始验证 `dir-graph.yaml` 机器契约。
- **四职能最小模式文档**：新增 `docs/FOUR-FUNCTION-MODE.md`，降低小团队理解多 Agent 流程的复杂度。
- **CLI 版本输出**：新增 `deliverhq --version` / `deliverhq version`，便于 GitHub npm 安装后确认版本。

### 变更
- **Workflow Router 规则去重**：新增 `routing_rules.py`，`workflow_router.py` 与 `eval_routing.py` 共用路由规则，降低评估与生产路径漂移。
- **Traceability 闭环增强**：ReviewGate 校验 AC → implementation/tests → changed files 的闭环，并支持 migration 文件映射。
- **错题本治理说明增强**：明确 `mistake-book.md` 中重复失败如何进入 `rules-candidates.md`，再由人工 promote/reject。

### 修复
- plan-only / no-modification 请求不再误触发完整 DeliverHQ 流程。
- DevPhase / worktree 子进程在 Windows 下的 UTF-8 输出处理更稳。
- selftest / gate contract 运行后不再污染示例 CR 的 evidence/state。

## [5.5.0] - 2026-06-18

### 新增（DeliverHQ Home 目录治理 / agent 无关，防产物散落）
- **Home 目录强制规则**：经 DeliverHQ 分析/治理的项目，所有产物强制收进 `<项目根>/DeliverHQ/`，严禁散落到根目录、根 docs、根 change-requests 或 skill 安装目录。
- **agent 无关的确定性落点**：新增 `scripts/deliverhq_home.py`，自动定位 DeliverHQ home（优先级：`--home` > 环境变量 `DELIVERHQ_HOME` > 向上找已有 `DeliverHQ/` > 项目根标志 `.git`/`package.json` 等 > 兜底 `cwd/DeliverHQ`）。不论 Hermes / Claude / Codex / Gemini 谁调、读不读文档、传不传参，产物都落进项目的 `DeliverHQ/`。
- `init_cr.py` 新增 `--home`；`scan_legacy.py` 的 `--out` 省略时自动定位落点（新增 `--home` / `--cr`）。修复全局安装（如 `~/.hermes/skills/deliverhq/`）时 CR/扫描产物散落到 skill 目录或当前目录的问题。
- `cr_state.py` 公共漏斗新增 warning-first 校验：8 个 Gate 经此漏斗，CR 不在 `DeliverHQ/` 内时告警并提示归位（不阻断 skill 自检）。
- 规则写入多处入口：SKILL.md（Hermes 唯一入口）顶部、AGENTS.md、dir-graph.yaml（`deliverhq_home` 契约），消除"相对谁"的路径歧义；SKILL.md 模式 3/4 命令显式 `DeliverHQ/` 前缀。
- selftest 仍 **22/22**；Python 3.6 兼容。

## [5.4.0] - 2026-06-18

### 新增（PRD 层 / 产品意图唯一来源）
- **PRD 层**：`docs/PRD.md`(产品意图唯一来源,薄、叙事、给人看全貌,仅人工维护,Agent 只读)。功能锚点 `[PRD-XXX]` 是 CR 的挂载点;单文件原则,大产品用锚点 ID 前缀分层。
- **PRD↔CR 派生链接**：`change-requests/CR-TEMPLATE/acceptance-spec.md` 顶部新增 `derived_from{prd_section, prd_hash}`,CR 是 PRD 的可执行切片。
- **PRD↔CR 对账**：`scripts/drift_check.py`。重算 PRD 锚点章节哈希(排除「关联 CR」行)与 CR 记录比对;confirmed 锚点不一致 → NEED_HUMAN_DECISION(改CR/改PRD/记差异),reverse-engineered 锚点仅警告(老项目放宽)。
- `scripts/specgate.py` 新增检查 9：PRD 链接与对账(warning-first,不破坏现有 8 项检查与 cr_state 联动)。
- selftest 仍 **22/22**;Python 3.6 兼容。

### 设计原则
- PRD 给人看意图(不写 ID/schema/Do-Not-Touch),acceptance-spec 给机器验;拆分是 Spec Agent 职责,SpecGate 只检查;不一致逼人对账而非静默阻断。

## [5.3.0] - 2026-06-16

### 新增（执行层 / Loop Engineering 场景化落地，去重不照搬）
- **证据补全 Loop**：`scripts/evidence_loop.py`。可恢复 loop——读 state.yml 恢复进度（无则 fail-closed），扫描 CR 缺哪些真实证据(spec/traceability/changed-files/manifest/test-plan)，列 gaps+next_action，写回 needs_human，写 evidence bundle。
- selftest 新增 `evidence_loop_contract`（无state→fail_closed / 缺证据→needs_human / 齐全→done），现 **22/22**。
- README 加"证据补全 Loop"小节；CAPABILITY-MATRIX 加 evidence_loop 行。

### 去重原则（审核第 4 份建议后）
- 第 4 份建议 90% 是已实现项（状态机/state.yml/证据门禁/fail-closed/retry/worktree/writeback 均已具备）。唯一真增量是"把抽象能力落成具体场景 loop"。
- 复用 cr_state / ReviewGate 证据口径 / retry_guard / write_gate_evidence，**不新增 Agent，不重命名现有状态机**（避免破坏 22 项 selftest 契约）。

## [5.2.0] - 2026-06-16

### 新增（执行层 / 借鉴 GSD，去重不照搬）
- **结构化 Plan + PlanChecker**：`plan.yml` 模板 + `scripts/plan_checker.py`。机检 task 粒度/verify/done/依赖/文件冲突/AC 覆盖，fail-closed；`--emit-waves` 派生 wave plan。
- **三层定位**写入 README：规范层(OpenSpec)/纪律层(Superpowers)/执行层(GSD)。
- `state.yml` 补 `goal` / `current_plan` / `completed_steps` 字段（向后兼容）。
- selftest 新增 `plan_checker_contract`（6 项正反例），现 **21/21**。
- 新增 `PLAN-GUIDE.md`。

### 去重原则
- Worker = 现有 Dev Agent；Verifier = 现有 ReviewGate/QualityGate。**不新增平行角色**，只补 PlanChecker 这一真缺口。

## [5.1.2] - 2026-06-16

### 新增
- 补齐 GitHub 发布所需元数据：`LICENSE`(MIT)、`.gitignore`、`package.json` 的 `repository` / `homepage` / `bugs` / `author` 字段。
- 新增本 `CHANGELOG.md`。

### 说明
- 纯打包/分发层改动，DeliverHQ 框架门禁脚本未变（`skill/VERSION.yml` 维持 5.0.0）。
- skill selftest 仍为 20/20。

## [5.1.0] - 2026-06-16

### 新增
- **多 Agent 安装支持**：`init --target claude|hermes|codex|gemini|generic`。
  - 文件夹型（claude/hermes）：整套复制到对应 skills 目录，靠 SKILL.md frontmatter 发现。
  - 扁平型（codex/gemini/generic）：核心放 `.deliverhq/`，向 `AGENTS.md`/`GEMINI.md`/`DELIVERHQ.md` 注入幂等指针段。
- `doctor` 自动探测多种安装位置。

## [5.0.0] - 2026-06-16

### 新增
- 首个可 `npx deliverhq init` 安装的版本（Claude Code）。
- SKILL.md 补 YAML frontmatter；空目录加 `.gitkeep` 修复 npm 打包丢目录。
