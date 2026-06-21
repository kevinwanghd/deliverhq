# DeliverHQ Rules Candidates

> AI-generated or CR-proposed rule changes land here first. `docs/rules.md` remains the canonical rules source until a human promotes approved entries.

## How To Use
- Add one entry per proposed rule or rule change.
- Keep the source CR and trigger problem explicit.
- Do not edit `docs/rules.md` directly from Writeback Agent output.
- Repeated failures in `docs/mistake-book.md` with `rules_candidate=true` should be reviewed here before promotion.
- Human review must choose one path: promote with `promote_rule_candidate.py`, reject with `reject_rule_candidate.py`, or leave pending with rationale.

## Candidate Rule Template
## Candidate Rule: <short title>
- Source CR: CR-XXX
- Trigger: <review finding, repeated bug, or quality failure>
- Proposed Rule: <rule text>
- Scope: <where this applies>
- Promotion Recommendation: yes/no

---

## Active Candidates

<!-- Add candidate entries below this line -->

## Candidate Rule: 规则沉淀必须先写候选区
- Source CR: CR-EXAMPLE
- Trigger: Writeback 阶段需要沉淀新规则，但不能让 AI 直接修改 canonical rules
- Proposed Rule: 所有 AI 生成的新规则或规则修改建议必须先写入 `docs/rules-candidates.md`，不得直接写入 `docs/rules.md`
- Scope: Writeback / Memory 治理流程
- Promotion Recommendation: yes
- Promotion Status: promoted
- Promoted To: rules.md #7
- Promoted On: 2026-06-15

## Candidate Rule: 重复规则应被拒绝
- Source CR: CR-REJECT-EXAMPLE
- Trigger: 人工治理阶段发现该规则与现有规则重复
- Proposed Rule: 所有重复规则候选必须在治理阶段明确拒绝
- Scope: Rule governance
- Promotion Recommendation: no
- Rejection Status: rejected
- Rejected Reason: 与现有规则重复
- Rejected On: 2026-06-15
