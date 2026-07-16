# 架构设计：统一入口、验证闭环与记忆生命周期基础

## CR-ID
CR-007

## 1. 模块拆分与目录结构

| 模块 | 职责 | 文件落点 |
|---|---|---|
| Go 决策模块 | 组合既有 route、STATE/CR 发现和阶段工件预检 | `skill/deliverhq/go.py` |
| Python CLI | 暴露 go 子命令和 JSON/文本输出 | `skill/scripts/deliver.py` |
| Node CLI | 项目内核心发现并转发 go | `bin/cli.js` |
| 可靠性修复 | Windows 输出、CR-ID、默认分支、包装卫生 | `skill/scripts/init_cr.py`, `worktree_manager.py`, `selftest_contracts/suite.py` |
| Memory 生命周期 | 向后兼容的结构化 lesson、去重和状态 | `skill/scripts/memory_store.py`，后续可迁入 package |
| 自动化测试 | 最高接缝验证 CLI 与模块契约 | `tests/` 与既有 selftest contract |

## 2. 数据流与状态管理

```text
Node CLI go
  → resolve project-local core
  → Python deliver.py go
  → existing route decision
  → discover DeliverHQ home / active CR
  → infer target phase
  → artifact preflight
  → deterministic GoDecision JSON
```

MemoryStore 继续使用 JSON index，但 schema 增加版本化字段。加载旧条目时补默认值；相同 fingerprint 更新原条目，不覆盖人工文档。

## 3. 接口封装与依赖

- 复用 `routing_rules.py`，不复制风险关键词。
- 复用 `cr_state.py`/state.yml 字段，不引入第二套状态机。
- Node 仅负责核心路径发现和进程转发，不实现阶段逻辑。
- 仅使用标准库与既有 PyYAML。

## 4. 异常处理与验证策略

- 多活跃 CR 无法消歧：返回 needs_human，不猜测。
- 缺工件：返回 recovery_action，不执行下游命令。
- Windows 流输出：统一调用 `configure_utf8_stdio()`。
- 包装卫生：基于发布清单/显式排除缓存，而非把运行缓存当产品缺陷。
- 每个修复先补回归测试，再实现。

## 5. 测试接缝

| 接缝 | 位置 | 覆盖范围 | 复用现有 | 类型 |
|---|---|---|---|---|
| 公共 CLI | `tests/test_entrypoints.py` | Node→Python go、路径发现、JSON schema | 是 | 集成 |
| Python 模块 | `tests/test_runtime_modules.py` | preflight、memory 兼容与去重 | 是 | 单元 |
| 全框架自检 | `selftest.py` | Gate/包装/契约无回归 | 是 | E2E |

**接缝选择理由**：优先复用已有入口和运行时模块测试，避免为每个内部函数增加耦合测试。

## 6. 设计分块到实现映射

| block | 目标文件 | 目标组件 | 证据 |
|---|---|---|---|
| B1 go decision | `skill/deliverhq/go.py` | `build_go_decision` | AC-1/AC-2 |
| B2 CLI adapters | `skill/scripts/deliver.py`, `bin/cli.js` | go command | AC-1/AC-5 |
| B3 validation reliability | `init_cr.py`, `worktree_manager.py`, `suite.py` | validation/runtime | AC-3 |
| B4 lessons lifecycle | `memory_store.py` | `MemoryEntry`, `MemoryStore.add` | AC-4 |
| B5 regression suite | `tests/*` | automated evidence | AC-1..AC-5 |

## 7. 直读计划

不涉及 UI，N/A。

## 8. 平台差异与验证策略

- Windows：GBK 控制台、路径分隔符、Python 缓存。
- macOS/Linux：默认分支可能为 main/master/自定义；路径逻辑使用 pathlib。
- 通过 mock/temp repo 测试，不依赖开发者真实全局安装。

## ArchitectureGate 检查点
- [x] 模块拆分/目录结构明确
- [x] 数据流与状态管理清晰
- [x] 接口封装与依赖列全
- [x] 异常处理与验证策略明确
- [x] 测试接缝选择合理
- [x] 每个设计分块有实现映射
- [x] 不涉及视觉直读
- [x] 无模板变量

**ArchitectureGate 状态**：READY
**人工确认**：未单独确认（用户已授权开始实施；具体架构待代码审查后确认）
