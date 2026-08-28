# Skills — In Progress

These skills are scaffolded but not production-ready. Do not load them in critical paths.

## evidence-loop

Evidence collection loop integrated with DeliverHQ's state machine.
Source: `DeliverHQ/scripts/evidence_loop.py`

Status: experimental — the loop structure is defined but the agent-driven flow is not yet stable.

## mistake-book闭环

闭环：QualityGate 失败 → mistake-book 记录 → rules-candidate 晋升。
Source: `DeliverHQ/scripts/update_mistake_book.py` + `DeliverHQ/scripts/promote_rule_candidate.py`

Status: TODO — 同类错误重复 3 次后自动创建 rules-candidate 条目的逻辑尚未实现。

## reverse-spec-gate

Legacy scan human adjudication with SLA escalation.
Source: `DeliverHQ/scripts/confirm_reverse_spec.py`

Status: experimental — timeout and escalation mechanism is defined but not fully integrated with cr_state.
