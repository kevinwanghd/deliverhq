# DeliverHQ 鑳藉姏鐭╅樀

> 鍗曚竴鑳藉姏鐘舵€佹簮銆係KILL.md / README.md / AGENTS.md 鐨勮兘鍔涙壙璇轰互鏈枃涓哄噯銆?

鐘舵€佸瓧娈碉細
- status: stable / experimental / placeholder / roadmap
- integrated: integrated / not_integrated
- default_enabled: true / false
- allowed_in_pipeline: true / false

> **璋冪敤鍒嗗眰锛堝€?Matt Pocock 鍙岃酱妯″瀷锛?*锛氳兘鍔涙寜 `default_enabled` 娲剧敓涓轰袱灞傗€斺€?
> `default_enabled=true` 鈫?**core**锛坢odel-invoked锛岄粯璁ゆ祦绋嬪父椹?context锛夛紱
> `default_enabled=false` 鈫?**on-demand**锛坲ser-invoked锛岄浂 per-turn 鎴愭湰锛屾寜闇€鍔犺浇锛夈€?
> 娲剧敓涓庢湁鐣屾鏌ヨ `scripts/capability_tiers.py`锛坄capability_tiers_contract` 閿佹 core 涓婄晫锛?
> 闃叉甯搁┗鑳藉姏鏃犲０鑶ㄨ儉锛夈€傛煡鐪嬶細`python scripts/capability_tiers.py`銆?

<!-- BEGIN GENERATED CAPABILITIES -->
| 能力 | 脚本/文档 | status | integrated | default_enabled | allowed_in_pipeline | 说明 |
|---|---|---|---|---:|---:|---|
| CR 初始化 | scripts/init_cr.py | stable | integrated | true | false | 创建 CR、state.yml、运行时目录；默认懒物化核心文件，`--full-template` 保留完整模板复制；worktree 创建失败只警告 |
| CR 状态机 | scripts/cr_state.py | stable | integrated | true | true | 管理 lane/phase/next_required_gate/evidence |
| SpecGate | scripts/specgate.py | stable | integrated | true | true | 验收规格 fail-closed 检查 |
| DesignGate | scripts/designgate.py | experimental | integrated | true | true | UI/设计产物检查，后端项目需 metadata 声明跳过 |
| ContextWindowGate | scripts/context_window_check.py | experimental | integrated | true | true | 校验 context-summary 结构、最多两阶段全文、来源 SHA-256、已排除方案与 next_action；旧摘要 warning-first |
| PermissionGate | scripts/permissiongate.py | experimental | integrated | false | true | 最小权限边界检查；依赖 git status/protected_paths/人工例外，不能视为深度自动化安全能力 |
| PreDevGate | scripts/pre_dev_gate.py | stable | integrated | true | true | 开发前真实门禁；通过后进入 DevPhase，不直接进入 Review；`--suggest-lane` 调 lane_advisor 给客观规模建议 |
| DevPhase Handoff | scripts/dev_phase.py | stable | integrated | true | true | 运行/确认 PreDevGate、检查 worktree、输出开发上下文；不自动写代码 |
| Worktree Manager | scripts/worktree_manager.py | stable | integrated | false | false | 仅通过 init_cr/dev_phase 调用，不作为 Dev Agent 直接进 pipeline |
| ReviewGate | scripts/reviewgate.py | stable | integrated | false | true | 代码实现后手动/状态机运行，默认 pipeline 不跨过人工开发点 |
| QualityGate | scripts/qualitygate.py | stable | integrated | false | true | 默认 hybrid；必须有 verification-manifest.yml，parse_only 仅 demo/兼容；可选 must_haves 谓词（见下） |
| must_haves 谓词（借 GSD 判据语法） | scripts/must_haves_check.py | experimental | integrated | false | true | 确定性校验 verification-manifest 的 must_haves 段（key_links/artifacts/min_lines/exports/contains/反 stub）；断言"建出来的=计划的"；QualityGate 调用，无此段则跳过（向后兼容）。非向 GSD agent-verifier 收敛，是给已有确定性门禁补判据语法 |
| DeployGate | scripts/deploygate.py | experimental | integrated | false | true | 部署就绪检查，不做真实部署 |
| WritebackGate | scripts/writeback_gate.py | stable | integrated | false | true | 交付后知识沉淀检查 |
| Gate Contract Check | scripts/gate_contract_check.py | stable | integrated | true | false | 验证脚本存在、正反例与参数契约 |
| Orchestrator | scripts/skill_orchestrator.py + scripts/orchestrator_core.py + scripts/orchestrator_routing.py | experimental | integrated | true | true | 薄 CLI + 编排 core + 纯路由/成本模块；默认 pipeline 停在 dev handoff |
| Execution Runtime | scripts/execution_runtime.py | stable | integrated | false | false | 统一无 shell Python 脚本执行、UTF-8、超时和结构化结果；Gate wrapper 与 orchestrator 共用 |
| Selftest Contract Suite | scripts/selftest.py + scripts/selftest_contracts/* | stable | integrated | true | false | 薄入口；37 项契约按 core/workflow/governance 三域注册，保持原汇总接口 |
| Failure Attribution | scripts/failure_attribution.py | experimental | integrated | true | false | 已接入 gate evidence 输出结构化归因 |
| Mistake Book Dedup | scripts/update_mistake_book.py | experimental | integrated | true | false | CR+Gate+failure_hash 去重，重复 3 次标记 rules_candidate |
| Routing Eval | scripts/eval_routing.py + evals/*routing-cases.md | stable | integrated | true | false | selftest 真实执行，禁止 total=0 通过 |
| Workflow Router | scripts/workflow_router.py | experimental | integrated | false | false | 规则版低噪路由，输出可解释 JSON；不替代人工判断 |
| Legacy Scan（逆向，目标2） | scripts/scan_legacy.py | experimental | integrated | false | false | 客观扫描老项目：技术栈/测试覆盖/复杂度/敏感域；review_required 由客观信号推导，AI 无权降级。文件按相对路径确定性排序，并产出 reverse-input-flatten.yml（借 BMAD flatten：每文件 sha256 + 整体 input_hash），同一份代码必产同一候选集（flatten_reproducible_contract） |
| ReverseSpecGate（逆向） | scripts/reverse_spec_gate.py | experimental | integrated | false | true | 未裁决高风险逆向需求 → BLOCK；selftest 有正反例契约（reverse_spec_contract） |
| Reverse Confirm（逆向） | scripts/confirm_reverse_spec.py | experimental | integrated | false | false | 人工逐条裁决候选：confirm/modify/reject/defer + is_real_requirement |
| Reverse → Spec（逆向） | scripts/reverse_to_spec.py | experimental | integrated | false | false | 已确认条目 → acceptance-spec.md + traceability.yml；产物须过 SpecGate 才进正向链路 |
| Goal Contract（loop 目标契约） | scripts/goal_contract.py | experimental | integrated | false | true | 五段式目标契约校验；完成标准=指标+不变量双轨，缺 invariants→BLOCK（防 Goodhart）；selftest 有契约（loop_control_contract） |
| 反钻空子检查（Anti-Gaming） | scripts/anti_gaming_check.py | experimental | integrated | false | true | 从 git diff 客观检测：删测试/禁用断言/降阈值/改门禁脚本/超范围 → BLOCK；不询问 Agent 自评 |
| 重试守卫（Retry Guard） | scripts/retry_guard.py | experimental | integrated | false | false | 同类失败（复用 failure_attribution 归因）达 max_retries → needs_human；拒绝原地重复假设 |
| PlanChecker（执行层） | scripts/plan_checker.py | experimental | integrated | false | true | 机检 plan.yml：task 粒度/依赖/文件冲突/AC 覆盖；brownfield 强制 read/write、复用搜索和破坏性变更证据；派生 wave |
| 证据补全 Loop（执行层） | scripts/evidence_loop.py | experimental | integrated | false | true | 可恢复 loop：扫 CR 缺哪些 evidence(spec/traceability/changed-files/manifest/test-plan)→列 gaps+next_action→写回 needs_human。复用 cr_state/reviewgate口径/write_gate_evidence，不新增 Agent；selftest 有契约 |
| Gate JSON Output | scripts/gate_json_output.py + scripts/runtime_support.py | experimental | integrated | false | false | 作为最小 Gate evidence schema helper 集成到 write_gate_evidence；不含 Dashboard/Viewer |
| Dynamic Workflows / Tournament / Fan-out | docs/ROADMAP-v4.8.md | roadmap | not_integrated | false | false | 不得在入口文档承诺为可用能力 |
| Scout / Repo Harness | scripts/bootstrap_project.py + scripts/scan_legacy.py + scripts/scan_legacy_structure.py | experimental | integrated | false | false | deliverhq bootstrap 组合现有 Legacy Scan，发现已有上下文、命令和抽象并附 path/hash 证据；默认只读，apply 只建候选文件 |
| PRD 层（产品意图唯一来源） | docs/PRD.md | experimental | integrated | true | false | 产品意图唯一来源，薄/给人看/仅人工维护；功能锚点 `[PRD-XXX]` 是 CR 挂载点；CR 用 derived_from 回指 |
| PRD↔CR 对账（DriftCheck） | scripts/drift_check.py | experimental | integrated | true | true | 重算 PRD 锚点哈希（排除「关联 CR」行）与 CR 记录比对；confirmed 失配→NEED_HUMAN_DECISION，reverse-engineered→仅警告；specgate 检查9 复用同逻辑，warning-first |
| Project Structure Governance | scripts/init_project_structure.py + scripts/structuregate.py + structure-profiles/fullstack-web.yml | experimental | integrated | false | false | opt-in 初始化 AI 友好/人类易复查目录契约；默认不生成业务代码，不进入默认阻断链路 |
| Lane Advisor（客观规模分档） | scripts/lane_advisor.py | experimental | integrated | false | false | 按 changed_files/ac_count/敏感域给 lane 建议；轻入口同时返回 required/skipped Gates、时间/token 区间、因素与置信度 |
| STATE 指针（借 Pocock /handoff） | scripts/handoff_state.py | experimental | integrated | false | false | 从各 CR 的 state.yml 汇总刷新极小 `STATE.md`（每轮必读），长会话/compaction 后重建治理上下文；agent 无关、零 hook，替代 SessionStart hook（避免 per-harness shim 膨胀） |
| Legacy Structure Scan | scripts/scan_legacy_structure.py | experimental | integrated | false | false | 只读扫描老项目目录结构，生成 structure-assessment-report.md 与 STRUCTURE-PROFILE.candidate.yml；不搬目录不改源码 |
| ArchitectureGate（架构确认门禁） | scripts/architecturegate.py | experimental | integrated | true | true | 第二道人工门禁；编码前必须有 architecture-design.md 并人工确认；缺章节或残留 {{}} → BLOCKED |
| 证据驱动编码 + 架构对齐报告 | change-requests/CR-TEMPLATE/architecture-alignment-report.md | experimental | integrated | true | false | Dev Agent 按架构实施 + 产对齐报告；缺证据 block 而非硬写；missing 最多回流 5 轮 |
| 直读审计 direct-read-audit | change-requests/CR-TEMPLATE/design/direct-read-audit.md | experimental | integrated | false | false | UI 编码前四元组追溯（node_id→属性→原始值→代码映射）；designgate C 端 warning-first |
| 视觉还原审计 visual-auditor | change-requests/CR-TEMPLATE/design/visual-audit-report.md | experimental | integrated | false | false | 对照设计源查还原度，偏差清单回流 code-generator 修复（遵守 direct-read-audit） |
| 移动端高保真门禁强化 | scripts/designgate.py + dir-graph design_gate | experimental | integrated | true | true | 识别 Android/iOS/Flutter/RN/鸿蒙/小程序 → 强制 C 端高保真；专项校验平台规范/多机型/深色模式/交互状态 |
| 编译验证多平台 bundle | verification-manifest.yml (platform_bundles) | experimental | integrated | false | true | 复用 QualityGate + 可选 iOS/Android/Harmony/RN bundle；编译失败自动定位修复 |
| RN/Figma 可选适配指南 | RN-FIGMA-ADAPTER-GUIDE.md | experimental | integrated | false | false | 可选适配层；核心门禁工具无关，可整体替换为其他技术栈 |
| Gate 缓存（Fingerprint） | scripts/gate_cache.py + scripts/gate_wrapper.py | experimental | integrated | false | false | 依赖文件 SHA256 fingerprint 缓存：gate 已通过且依赖未变→跳过执行；实测 token 消耗 -50~73%；`DELIVERHQ_GATE_CACHE=0` 禁用。详见 references/gate-cache-guide.md |
| 子 CR 拆解（Epic→Story） | scripts/create_sub_cr.py | experimental | integrated | false | false | 大需求拆分为多个子 CR（数字后缀 CR-001-01/02/03）；每个子 CR 独立走完整 Gate 链，上下文天然隔离；Epic 只走轻量 spec；自动维护 sub-crs.yml。详见 references/sub-cr.md |
| CR 规模分析（Decompose） | scripts/skill_orchestrator.py decompose | experimental | integrated | false | false | 分析 CR 规模（token 估算 + criteria 数量）；超阈值（criteria>10 或 tokens>5000）给出拆解建议；建议器非 Gate，不强制阻断 |
| 动词路由器（Route） | scripts/skill_orchestrator.py route | experimental | integrated | false | false | 根据场景（新需求/bug/重构/legacy/已有spec）推荐动词流；支持关键词匹配或交互式问答。借鉴 Pocock ask-matt |
| grill（需求澄清拷问） | scripts/grill.py | experimental | integrated | false | false | 生成 acceptance-spec 之前逐条拷问需求（一次一问+推荐答案），产出 request-clarifications.md；条件步，缺 request.md 则跳过。借鉴 Pocock grilling |
| Knowledge Lifecycle Audit | scripts/memory_store.py audit | experimental | integrated | false | false | 审计外部记忆 active/superseded/deprecated/obsolete 状态、晋升候选与证据路径，避免知识只进不出 |
| Capability Stocktake | scripts/capability_stocktake.py | experimental | integrated | false | false | 新增能力前检查现有能力复用/扩展路径，要求记录 why_existing_insufficient，防止能力矩阵膨胀 |
| Wording Drift Check | scripts/wording_drift_check.py | experimental | integrated | false | false | 检查入口文档引用 CAPABILITY-MATRIX.md 且不重复维护能力状态表，减少跨文档措辞漂移 |
<!-- END GENERATED CAPABILITIES -->

