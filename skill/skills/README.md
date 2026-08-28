# Skills — DeliverHQ × Matt Pocock 对齐

> 这是 DeliverHQ 吸收 mattpocock/skills 格式后的 skill 库。
> 入口在 `<项目根>/DeliverHQ/skill/SKILL.md`（主 deliverhq skill）。
> 这里的 skills/ 目录是 mattpocock 格式的对齐层，供 Skill tool 发现和路由。

---

## Engineering

### handoff

Compact the current DeliverHQ conversation into a handoff document so another agent or session can continue the work. Uses `handoff_state.py` + `state.yml` for state recovery.

**Trigger**: `handoff`, `交接`, `handoff.md`, 切换会话, 委托子任务

### code-review

Two-axis code review (Standards + Spec) with parallel sub-agents. Core of DeliverHQ's ReviewGate — Dev and Review must be separate agents.

**Trigger**: `review`, `reviewgate`, `代码审查`, `review report`

### tdd

Test-driven development with red-green-refactor loop. Integrated with DeliverHQ's QualityGate and verification-manifest.

**Trigger**: `tdd`, `test-driven`, `红绿重构`, `写测试`, `verification manifest`

### grill-with-docs

Grill requirements/design using project docs as constraints. Produces `request-clarifications.md` for Spec Agent. Pre-spec gate.

**Trigger**: `grill-with-docs`, `需求拷问`, `clarifications`

### to-spec

Synthesize conversation into acceptance-spec without interviewing. Feeds DeliverHQ's Spec Agent. Runs SpecGate validation.

**Trigger**: `to-spec`, `写规格`, `acceptance spec`, `生成 spec`

### domain-modeling

Build and sharpen project's domain model. Use when discussing terminology, writing CONTEXT.md, or recording ADRs.

**Trigger**: `domain-modeling`, `领域模型`, `CONTEXT.md`, `ADR`, `术语`

### codebase-design

Shared design vocabulary (module/depth/seam/interface/adapter/leverage/locality). Consult-only before architecture discussions.

**Trigger**: `codebase-design`, `codebase design`, `架构词汇`, `module depth`

### improve-codebase-architecture

Scan codebase for deepening opportunities, generate HTML report, then grill through chosen candidate. Calls codebase-design and grill-the-user.

**Trigger**: `improve-architecture`, `架构改进`, `深化模块`, `architecture report`

### teach

Teach the user a new skill or concept over multiple sessions with persistent workspace. Stateful across sessions.

**Trigger**: `teach`, `teaching`, `教学`, `学`, `learn`

### grill-the-user

Relentless structured interview of the user. One question at a time until decision tree is exhausted. Pattern behind grill-with-docs and improve-codebase-architecture.

**Trigger**: `grill`, `grilling`, `烤问`, `追问`, `decision tree`

---

## In Progress

These skills are scaffolded but not yet production-ready:

- `evidence-loop` — Evidence collection loop (DeliverHQ experimental)
- `mistake-book闭环` — Mistake book → rules candidate promotion (DeliverHQ P2-2)

---

## Skill References

Skills reference each other by name (lower-case, no spaces). Call the Skill tool with the skill name to chain:

- `to-spec` → `grill-with-docs` (pre-spec)
- `to-spec` → `domain-modeling` (glossary alignment)
- `improve-codebase-architecture` → `codebase-design` (vocabulary)
- `improve-codebase-architecture` → `grill-the-user` (decision loop)
- `domain-modeling` → `codebase-design` (design vocabulary)
- `handoff` → `handoff_state.py` (DeliverHQ state recovery)
