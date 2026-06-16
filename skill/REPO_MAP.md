# REPO_MAP.md

> 仓库模块地图模板。用于让 Agent 先读地图，不要自己在代码库里乱摸。

## Modules

| Module | Path | Owner | Purpose | Notes |
|---|---|---|---|---|
| application | `src/` | TBD | Main application code | Adjust for the host project |
| tests | `tests/` | TBD | Automated tests | Keep aligned with verification-manifest.yml |
| docs | `docs/` | TBD | Product/engineering docs | Project docs, not DeliverHQ governance docs |

## Critical paths

- See `dir-graph.yaml` `protected_paths` for protected files.
- Keep this map small and practical; update only when module ownership or structure changes.
