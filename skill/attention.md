# DeliverHQ Attention

This is the lightweight, always-read control file for this project's DeliverHQ
governance space. Keep it short; durable implementation details belong in
`docs/`, `references/`, or the relevant script.

## Governance Lanes

| Lane | Use When | Default Evidence |
|---|---|---|
| quick | small single-surface change, no protected path, no production risk | direct change + relevant command output |
| standard | normal feature, bug fix, or refactor | lightweight CR + SpecGate/ReviewGate/QualityGate as needed |
| strict | auth, payment, security, data migration, production, protected paths | full fail-closed CR chain |
| legacy | existing code must be scanned before requirements are trusted | legacy scan + human confirmation |

Default lane: `standard`

## Read First

- `REPO_MAP.md`
- `COMMANDS.yml`
- Current CR under `change-requests/`, when one exists

## Risk Triggers

Escalate to `strict` when the change touches authentication, authorization,
payment, security, data migration, production configuration, or protected paths.

## Quick Knowledge Sinks

- Confirmed reusable lessons: `notes/`
- Untriaged ideas and possible rules: `inbox/`
- Day-level progress and handoff notes: `journal/`
- Formal durable rules and decisions: `docs/`
