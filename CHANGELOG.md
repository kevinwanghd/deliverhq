# Changelog

本文件记录 **npm 包 `deliverhq`（安装器）** 的版本变化。
DeliverHQ 框架本身的版本见 `skill/VERSION.yml`（与安装器版本独立）。

版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

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
