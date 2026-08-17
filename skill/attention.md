# DeliverHQ Attention

Lightweight lane/risk control file. Read it **when routing a request or unsure which
lane applies** — not every turn (the only per-turn file is `STATE.md`). Keep it short;
durable implementation details belong in `docs/`, `references/`, or the relevant script.

## Governance Lanes

| Lane | Use When | Default Evidence |
|---|---|---|
| quick | small single-surface change, no protected path, no production risk | direct change + relevant command output |
| standard | normal feature, bug fix, or refactor | lightweight CR + SpecGate/ReviewGate/QualityGate as needed |
| strict | auth, payment, security, data migration, production, protected paths | full fail-closed CR chain |
| legacy | existing code must be scanned before requirements are trusted | legacy scan + human confirmation |

Default lane: `standard`

## Load On Demand (not upfront)

- `REPO_MAP.md` — when you need the module map
- `COMMANDS.yml` — when you need the authoritative command
- Current CR under `change-requests/` — when advancing that CR

## Risk Triggers

Escalate to `strict` when the change touches authentication, authorization,
payment, security, data migration, production configuration, or protected paths.

## Quick Knowledge Sinks

- Confirmed reusable lessons: `notes/`
- Untriaged ideas and possible rules: `inbox/`
- Day-level progress and handoff notes: `journal/`
- Formal durable rules and decisions: `docs/`
