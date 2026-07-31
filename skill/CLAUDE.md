# CLAUDE.md — Thin Tool Entry

This workspace uses `AGENTS.md` as the unified Agent behavior source.

**Lazy-loading entry (do NOT bulk-read at startup):**
- Every turn, read only `STATE.md` (~100 tokens) to know where you are in the chain.
- Read `AGENTS.md` behavior rules once when entering the skill (usually already in context).
- Everything else — `dir-graph.yaml`, `docs/CONTEXT.md`, CR artifacts, `references/agent-roles.md`,
  `CAPABILITY-MATRIX.md` — is loaded **on demand per phase**, per `AGENTS.md` › 《按阶段加载文档》.

Do not duplicate or override `AGENTS.md` rules here.

> 范围说明：本 `DeliverHQ/` 目录是项目的 DeliverHQ 治理空间（组织记忆 + 质检门禁 + 扫描报告）。
> 项目本身的权威工程约定（如有）位于仓库根目录，本目录与其互补，不覆盖。
