# Acceptance Spec: Modularize DeliverHQ Runtime

## CR-ID
CR-004

## 1. Data Spec

本 CR 不引入业务数据实体。新增的运行结果对象包含：命令、退出码、标准输出、标准错误、超时状态；所有字段必须可序列化且不持有进程句柄。

数据不变式：相同脚本、参数、工作目录和环境输入下，统一执行接口必须保留原始退出码与输出文本；超时必须返回确定性的失败结果。

## 2. Interface Spec

- `execution_runtime.run_script(...)`：执行 Python 脚本并返回结构化结果，不直接退出进程。
- `orchestrator_routing`：提供 CR 规模分析、场景路由和成本估算纯逻辑。
- `selftest_contracts`：按契约域导出检查函数；`scripts/selftest.py` 继续作为唯一公开一键入口。

兼容约束：`skill_orchestrator.py`、`gate_wrapper.py` 和 `selftest.py` 的现有 CLI、标准输出关键行及退出码保持不变。

## 3. Behavior Spec

### 场景 1：统一执行接口正常运行
- **Given** 一个返回退出码 0 并输出 UTF-8 文本的 Python 脚本
- **When** 通过统一执行接口调用
- **Then** 返回成功结果、退出码 0 和完整 UTF-8 输出
- **Measurable Success** Linux 与 Windows CI 的 Python 3.10/3.13 矩阵全部通过

### 场景 2：执行异常与超时
- **Given** 一个非零退出或超过指定时限的脚本
- **When** 通过统一执行接口调用
- **Then** 非零退出码原样保留，超时转换为确定性失败结果，调用方不产生未处理异常
- **Measurable Success** 自动化测试覆盖非零退出和超时两个分支

### 场景 3：重构后公开行为兼容
- **Given** 当前 `selftest.py`、orchestrator 和 Gate wrapper 的既有调用方式
- **When** 完成模块拆分后执行回归测试
- **Then** 入口测试全部通过，selftest 仍输出 `通过: 37/37`，Gate 集合与组合规则不变
- **Measurable Success** 本地与 GitHub CI 结果均为 100% 通过

### 场景 4：模块依赖保持单向
- **Given** 新增的执行、路由和 selftest 契约模块
- **When** 运行架构契约检查
- **Then** Gate 脚本之间没有新增 import 边，编排器依赖执行模块，执行模块不反向依赖编排器
- **Measurable Success** `gate_composition_contract` 和新增依赖方向测试全部通过

## 非功能验收

- 兼容性：支持 Python 3.10 和 3.13、Windows 和 Linux。
- 性能：完整 selftest 总时长不得比当前基线增加 20% 以上。
- 可维护性：`skill_orchestrator.py` 与 `selftest.py` 的行数均下降；新模块职责单一。
- 安全性：命令继续使用参数数组执行，不引入 `shell=True`。

## Facts

| # | 事实 | 来源 | 确认人 | 日期 |
|---|---|---|---|---|
| F1 | 当前 selftest 为 37 项契约 | v5.15.4 selftest | Codex | 2026-07-11 |
| F2 | Gate 集合已冻结 | `gate_composition_check.py` | DeliverHQ rules | 2026-07-11 |

## Assumptions

| # | 假设 | 风险级别 | 验证方式 | 验证期限 | 状态 |
|---|---|---|---|---|---|
| A1 | 公开 CLI 行为必须完全兼容 | P1 | 入口回归测试 | PR 合并前 | verified |

## Open Questions

| # | 问题 | 阻断级别 | 负责人 | 截止日期 | 状态 |
|---|---|---|---|---|---|
| Q1 | 架构方案是否批准进入编码 | P0 | Kevin | 2026-07-11 | resolved |

**SpecGate 状态**：READY
