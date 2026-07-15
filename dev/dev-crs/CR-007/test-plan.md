# Test Plan: CR-007

## 测试策略

以契约测试覆盖 Node/Python CLI、项目状态发现、只读工件预检、Worktree 分支与 CR-ID、MemoryStore 迁移和发布卫生；再用全量 pytest、框架 selftest 与 npm pack 做回归。

| 层次 | 文件/命令 | 覆盖 |
|---|---|---|
| CLI 契约 | `tests/test_entrypoints.py` | AC-1、AC-2、AC-5；纯 JSON、缺 home、CR 歧义、无写入 |
| Worktree | `tests/test_worktree_manager.py` | AC-3；默认分支探测、语义 CR-ID、非法输入先失败 |
| Memory | `tests/test_memory_store.py` | AC-4；语义去重、旧索引迁移、生命周期、导出保护 |
| Runtime | `tests/test_runtime_modules.py` | AC-3、AC-5；发布清单忽略运行时缓存 |
| 全量回归 | `python -m pytest -q` | 54 passed、5 subtests passed |
| 框架自检 | `python skill/scripts/selftest.py` | 37/37 passed |
| 发布预算 | `npm pack --dry-run --json` | 226 files，1,197,573 bytes |

## 阻断标准

- 任一测试失败。
- `go --json` 混入非 JSON 文本或产生文件写入。
- npm 解压体积超过 1,200,000 bytes，或发布清单包含 Python 缓存。
- 既有 5 动词或冻结 Gate 集合发生变化。

## 最终结果

全部自动化测试与自检通过；未执行网络测试，未新增第三方依赖。
