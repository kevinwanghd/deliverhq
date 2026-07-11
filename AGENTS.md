# Codex Project Entry

This repository keeps its shared agent behavior rules in `skill/AGENTS.md`.

Before making changes:

1. Read and follow `skill/CLAUDE.md` as the shared tool entry.
2. Read and follow the files referenced by `skill/CLAUDE.md`, especially
   `skill/AGENTS.md`.
3. Apply repository-root engineering conventions together with the DeliverHQ
   governance rules. If instructions conflict, follow the higher-priority or
   more specific instruction.

## GitHub Workflow

- Never push changes directly to `main`.
- Create a dedicated branch for every change submitted to GitHub.
- Run the required verification before committing.
- Push the branch and create a pull request.
- Do not merge the pull request unless the user explicitly requests it.

Do not duplicate the full DeliverHQ rules here. Keep shared behavior in
`skill/AGENTS.md` so Claude Code and Codex use one maintained source.
