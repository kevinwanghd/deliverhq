# 架构设计: Modularize DeliverHQ Runtime

## CR-ID
CR-004

## 1. 模块拆分与目录结构

| 模块 | 职责 | 文件落点 |
|---|---|---|
| Execution Runtime | 统一 Python 脚本执行、UTF-8、超时和结构化结果 | `skill/scripts/execution_runtime.py` |
| Orchestrator Routing | 成本估算、CR 规模分析和场景路由纯逻辑 | `skill/scripts/orchestrator_routing.py` |
| Selftest Contracts | 按 core/workflow/governance 域承载契约检查 | `skill/scripts/selftest_contracts/` |
| Compatibility Entrypoints | 保留既有 CLI、参数、输出与退出码 | `skill/scripts/gate_wrapper.py`, `skill/scripts/skill_orchestrator.py`, `skill/scripts/selftest.py` |

## 2. 数据流与状态管理

CLI 入口解析参数后调用领域模块。orchestrator 只决定执行顺序，将脚本、参数、工作目录、环境和超时交给 Execution Runtime；Execution Runtime 返回不可变的结构化结果，由入口负责展示和退出。Gate 自身继续独立更新 CR 状态，不通过新模块互相调用。

selftest 入口创建共享测试上下文，将其传给 core、workflow、governance 三组契约注册函数，按现有顺序执行并汇总同名 37 项结果。示例 CR 快照与恢复仍由顶层入口统一管理。

## 3. 接口封装与依赖

- `execution_runtime.py` 只依赖 Python 标准库，不依赖 Gate 或 orchestrator。
- `orchestrator_routing.py` 只依赖标准库和只读 YAML 数据，不执行子进程。
- `skill_orchestrator.py` 和 `gate_wrapper.py` 依赖 Execution Runtime。
- `selftest_contracts` 可以依赖运行时 helper，但不得被生产 Gate 导入。
- 不引入第三方依赖，不修改冻结 Gate 集合。

依赖方向：入口 -> 编排/契约模块 -> Execution Runtime；禁止反向依赖。

## 4. 异常处理与验证策略

- 非零退出保留原始 return code、stdout 和 stderr。
- 超时返回 `timed_out=true` 和非零状态，不向普通调用方泄漏 `TimeoutExpired`。
- UTF-8 解码使用 `errors=replace`，保证 Windows 非 UTF-8 locale 下可诊断。
- 每次提取后运行入口测试和 37 项 selftest；最终运行四组 CI 矩阵、`node --check`、`npm pack --dry-run`、Gate composition check。
- 每阶段单独 commit，任一阶段失败可独立 revert。

## 5. 测试接缝 (Test Seams)

| 接缝 | 位置 (文件/模块) | 覆盖范围 | 是否复用现有 | 测试类型 |
|---|---|---|---|---|
| 公共 CLI 与 selftest 入口 | `tests/test_entrypoints.py` | Gate wrapper、orchestrator、selftest 的外部行为 | 是 | 集成测试 |
| Execution Runtime 返回值 | `tests/test_runtime_modules.py` | 成功、非零退出、超时、UTF-8 | 否 | 单元测试 |

**接缝选择理由**：公开入口是最高且已存在的兼容接缝；Execution Runtime 是新增的深模块，需要一个小接口单测覆盖异常语义。内部提取函数不逐个测试，避免测试绑定文件布局。

## 6. 设计分块到实现映射

| block | 目标文件 | 目标组件 | 数据字段 | 交互 | 设计源证据 |
|---|---|---|---|---|---|
| 统一执行 | `skill/scripts/execution_runtime.py` | `ExecutionResult`, `run_script` | returncode/stdout/stderr/timed_out | Python subprocess | AC 场景 1/2 |
| Gate 入口复用 | `skill/scripts/gate_wrapper.py` | wrapper main | gate/args/timeout | Execution Runtime | AC 场景 3 |
| 编排职责拆分 | `skill/scripts/orchestrator_routing.py`, `skill/scripts/skill_orchestrator.py` | routing/cost/decompose | verb/lane/cost | 纯逻辑 + orchestration | AC 场景 3/4 |
| 契约分组 | `skill/scripts/selftest_contracts/`, `skill/scripts/selftest.py` | contract registries | name/result | shared test context | AC 场景 3/4 |
| 回归测试 | `tests/test_runtime_modules.py`, `tests/test_entrypoints.py` | unittest suites | CLI/result | subprocess/import | 全部 AC |

## 7. 直读计划（direct-read plan）

N/A。本 CR 不涉及 UI；接口与行为以 acceptance-spec、当前 CLI 输出和测试断言为证据源。

## 8. 平台差异与验证策略

Windows 重点验证非 UTF-8 locale、路径分隔符和 `sys.executable`；Linux 重点验证标准 Python/Node 入口。GitHub Actions 使用 Windows/Linux 与 Python 3.10/3.13 的现有矩阵。

## ArchitectureGate 检查点

- [x] 模块拆分/目录结构明确
- [x] 数据流与状态管理清晰
- [x] 接口封装与依赖列全
- [x] 异常处理与验证策略明确
- [x] 测试接缝选择合理
- [x] 每个设计分块有实现映射
- [x] 直读计划已说明不适用
- [x] 无残留模板变量

**ArchitectureGate 状态**：READY
**人工确认**：已确认（Kevin / 2026-07-11）
