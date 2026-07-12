# Request: Bootstrap、Lane 成本提示与 Context 证据强化

## CR-ID
CR-006

## 提出人
Kevin（由 Codex 根据 2026-07-12 指令记录）

## 需求背景

DeliverHQ 已有较完整的规格、门禁、执行和验证能力，但首次进入宿主项目时仍依赖模板和人工补全；轻入口不能直观展示治理成本；ContextWindowGate 主要检查文档存在与章节，尚未验证输入是否过期；Brownfield 变更缺少复用搜索和破坏性修改证据。

## 业务目标

1. 一条命令只读扫描宿主仓库并生成可审查的项目上下文候选。
2. route 输出推荐 lane、原因、必经/跳过 Gate 以及可解释的时间和 token 成本区间。
3. ContextWindowGate 验证结构化上下文、输入哈希和阶段范围。
4. PlanChecker 对复用搜索与破坏性修改证据执行确定性检查，不新增 Gate。

## 功能范围

- 新增 `npx deliverhq bootstrap [--path <repo>] [--json] [--apply]`。
- 默认只输出扫描结果；`--apply` 仅写入宿主项目 `DeliverHQ/` 下的候选治理文件，不改业务源码。
- 扩展 route JSON 和人类输出，保持现有字段兼容。
- 扩展 `context-summary.md` schema 与 ContextWindowGate。
- 扩展 `plan.yml` task schema 与 PlanChecker。
- 更新 README、能力矩阵、模板和契约测试。

## 非目标

- 不新增 Gate 或 Agent。
- 不自动修改宿主项目业务代码。
- 不自动批准架构或高风险变更。
- 不实现动态多 Agent tournament。

## 验收标准（高层）

- Bootstrap 对同一仓库产生确定性结果，默认零写入，`--apply` 不覆盖已确认文件。
- route 同时返回 lane、理由、成本与 Gate 计划，旧调用保持可用。
- 过期 input hash、超过两阶段全文或缺少必需结构时 ContextWindowGate 阻断。
- 声明破坏性修改却缺引用扫描证据，或 Brownfield 任务缺复用搜索证据时 PlanChecker 阻断。
- selftest、Python tests、Node entrypoint tests 全部通过。

## 优先级
P0
