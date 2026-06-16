# DeliverHQ 能力矩阵

> 单一能力状态源。SKILL.md / README.md / AGENTS.md 的能力承诺以本文为准。

状态字段：
- status: stable / experimental / placeholder / roadmap
- integrated: integrated / not_integrated
- default_enabled: true / false
- allowed_in_pipeline: true / false

| 能力 | 脚本/文档 | status | integrated | default_enabled | allowed_in_pipeline | 说明 |
|---|---|---|---|---:|---:|---|
| CR 初始化 | scripts/init_cr.py | stable | integrated | true | false | 创建 CR、state.yml、运行时目录；worktree 创建失败只警告 |
| CR 状态机 | scripts/cr_state.py | stable | integrated | true | true | 管理 lane/phase/next_required_gate/evidence |
| SpecGate | scripts/specgate.py | stable | integrated | true | true | 验收规格 fail-closed 检查 |
| DesignGate | scripts/designgate.py | experimental | integrated | true | true | UI/设计产物检查，后端项目需 metadata 声明跳过 |
| ContextWindowGate | scripts/context_window_check.py | experimental | integrated | true | true | 当前主要检查摘要存在和上下文纪律，schema 化仍是后续项 |
| PermissionGate | scripts/permissiongate.py | experimental | integrated | false | true | 最小权限边界检查；依赖 git status/protected_paths/人工例外，不能视为深度自动化安全能力 |
| PreDevGate | scripts/pre_dev_gate.py | stable | integrated | true | true | 开发前真实门禁；通过后进入 DevPhase，不直接进入 Review |
| DevPhase Handoff | scripts/dev_phase.py | stable | integrated | true | true | 运行/确认 PreDevGate、检查 worktree、输出开发上下文；不自动写代码 |
| Worktree Manager | scripts/worktree_manager.py | stable | integrated | false | false | 仅通过 init_cr/dev_phase 调用，不作为 Dev Agent 直接进 pipeline |
| ReviewGate | scripts/reviewgate.py | stable | integrated | false | true | 代码实现后手动/状态机运行，默认 pipeline 不跨过人工开发点 |
| QualityGate | scripts/qualitygate.py | stable | integrated | false | true | 默认 hybrid；必须有 verification-manifest.yml，parse_only 仅 demo/兼容 |
| DeployGate | scripts/deploygate.py | experimental | integrated | false | true | 部署就绪检查，不做真实部署 |
| WritebackGate | scripts/writeback_gate.py | stable | integrated | false | true | 交付后知识沉淀检查 |
| Gate Contract Check | scripts/gate_contract_check.py | stable | integrated | true | false | 验证脚本存在、正反例与参数契约 |
| Orchestrator | scripts/skill_orchestrator.py | experimental | integrated | true | true | 默认 pipeline 停在 dev handoff；不假装自动完成开发/验收 |
| Failure Attribution | scripts/failure_attribution.py | experimental | integrated | true | false | 已接入 gate evidence 输出结构化归因 |
| Mistake Book Dedup | scripts/update_mistake_book.py | experimental | integrated | true | false | CR+Gate+failure_hash 去重，重复 3 次标记 rules_candidate |
| Routing Eval | scripts/eval_routing.py + evals/*routing-cases.md | stable | integrated | true | false | selftest 真实执行，禁止 total=0 通过 |
| Workflow Router | scripts/workflow_router.py | experimental | integrated | false | false | 规则版低噪路由，输出可解释 JSON；不替代人工判断 |
| Legacy Scan（逆向，目标2） | scripts/scan_legacy.py | experimental | integrated | false | false | 客观扫描老项目：技术栈/测试覆盖/复杂度/敏感域；review_required 由客观信号推导，AI 无权降级 |
| ReverseSpecGate（逆向） | scripts/reverse_spec_gate.py | experimental | integrated | false | true | 未裁决高风险逆向需求 → BLOCK；selftest 有正反例契约（reverse_spec_contract）|
| Reverse Confirm（逆向） | scripts/confirm_reverse_spec.py | experimental | integrated | false | false | 人工逐条裁决候选：confirm/modify/reject/defer + is_real_requirement |
| Reverse → Spec（逆向） | scripts/reverse_to_spec.py | experimental | integrated | false | false | 已确认条目 → acceptance-spec.md + traceability.yml；产物须过 SpecGate 才进正向链路 |
| Goal Contract（loop 目标契约） | scripts/goal_contract.py | experimental | integrated | false | true | 五段式目标契约校验；完成标准=指标+不变量双轨，缺 invariants→BLOCK（防 Goodhart）；selftest 有契约（loop_control_contract）|
| 反钻空子检查（Anti-Gaming） | scripts/anti_gaming_check.py | experimental | integrated | false | true | 从 git diff 客观检测：删测试/禁用断言/降阈值/改门禁脚本/超范围 → BLOCK；不询问 Agent 自评 |
| 重试守卫（Retry Guard） | scripts/retry_guard.py | experimental | integrated | false | false | 同类失败（复用 failure_attribution 归因）达 max_retries → needs_human；拒绝原地重复假设 |
| PlanChecker（执行层） | scripts/plan_checker.py | experimental | integrated | false | true | 机检 plan.yml：task 粒度/verify/done/依赖/文件冲突/AC 覆盖；派生 wave；selftest 有契约。Worker=Dev Agent、Verifier=ReviewGate（不新增角色） |
| 证据补全 Loop（执行层） | scripts/evidence_loop.py | experimental | integrated | false | true | 可恢复 loop：扫 CR 缺哪些 evidence(spec/traceability/changed-files/manifest/test-plan)→列 gaps+next_action→写回 needs_human。复用 cr_state/reviewgate口径/write_gate_evidence，不新增 Agent；selftest 有契约 |
| Gate JSON Output | scripts/gate_json_output.py | experimental | not_integrated | false | false | 独立工具，尚未成为所有 Gate 的统一输出层 |
| Loop Mode | scripts/loop_mode.py | experimental | not_integrated | false | false | 不进默认流程，需人工监督 |
| Darwin Score | scripts/darwin_score.py | experimental | not_integrated | false | false | 仅报告观察，不硬阻断 |
| Quality Ratchet | scripts/quality_ratchet.py | experimental | not_integrated | false | false | 仅报告观察，不硬阻断 |
| Dynamic Workflows / Tournament / Fan-out | docs/ROADMAP-v4.8.md | roadmap | not_integrated | false | false | 不得在入口文档承诺为可用能力 |
| Scout / Repo Harness | docs/ROADMAP-v4.8.md | roadmap | not_integrated | false | false | 规划项 |

## 设计约束

1. 默认 pipeline 只跑到 `dev_phase.py`，输出开发上下文后停止；代码实现、Review、Quality、Deploy、Writeback 必须在实现完成后显式推进。
2. QualityGate 默认不能只读 AI 写的 `quality-report.md`。缺少 `verification-manifest.yml` 或没有启用真实命令时 fail-closed。
3. `worktree_manager.py` 是工具，不是 Dev Agent。任何 pipeline 不得把 CR 路径直接传给它假装开发。
4. Darwin Score / Quality Ratchet 先做观察报告，不进入阻断链路。
5. 新能力进入默认流程前，必须同时满足：脚本存在、参数契约测试、正反例或 dry-run 测试、README/SKILL 能力状态同步。

**版本**: v5.0.0  
**最后更新**: 2026-06-15
