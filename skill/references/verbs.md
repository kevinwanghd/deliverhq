# 用户面动词（脚本收口，默认入口）

> 借鉴 OpenMole 的克制：把"直面 54 个脚本"的认知负荷收口为 **5 个动词**，
> 兑现 `skill_orchestrator.py` 早已声明的 "thin harness orchestrates fat skills"。
> 只动人机接口，不动 fail-closed 证据门禁内核。

## 5 个动词 → 脚本链

| 动词 | 链路（顺序执行，任一 BLOCK 即停并透传原始报告） | 覆盖门禁 / 对应 phase |
|---|---|---|
| `spec`    | specgate → drift_check | 验收规格完备性 + PRD↔CR 对账（Spec/SpecGate） |
| `design`  | designgate → architecturegate | UI/设计产物 + 架构设计人工确认（Design/Architecture） |
| `dev`     | pre_dev_gate → context_window_check → dev_phase | 开发前门禁 + 上下文纪律 + 交接（**停在写码前**；Context/Dev） |
| `verify`  | goal_contract*（条件） → reviewgate → qualitygate → anti_gaming_check | 目标契约双轨 + 对抗式审查 + 真实构建/测试 + 反钻空子（Review/Quality） |
| `archive` | writeback_gate → update_rule_maturity | 知识沉淀 + 规则成熟度（Writeback/Memory） |

> *`goal_contract` 是**条件步**：仅当 CR 内有 `goal-contract.yml` 时才跑（显式启用 loop 治理的 CR）；
> 缺失则**跳过而非失败**——不强制每个 CR 都写目标契约，保住 fast-lane。
> 它放在链首，是为了在信任 review/quality 的指标**之前**先校验"指标+不变量"双轨（防 Goodhart：
> 只盯 metrics 会被"删测试"达成）。`verify` 失败后会跑 `retry_guard` 的**只读 status** 展示收敛状态，
> 但**绝不自动 record**——record 需人/Agent 给出新假设（达上限转 needs_human）。

## 用法

```bash
python scripts/skill_orchestrator.py verbs                          # 看动词→链路
python scripts/skill_orchestrator.py verb spec    change-requests/CR-001
python scripts/skill_orchestrator.py verb dev     change-requests/CR-001
python scripts/skill_orchestrator.py verb verify  change-requests/CR-001
python scripts/skill_orchestrator.py verb archive change-requests/CR-001
python scripts/skill_orchestrator.py validate-verbs                # 校验动词层未漂移
```

## 纪律红线（动词不得反噬可观测性）

1. **默认入口非唯一入口**：底层每个脚本仍可经 `execute` / 直接调用（调试 / CI / 高级用法）。
   动词只是收口，不删门禁——每一步仍是原来的 fail-closed 脚本。
2. **任一步 BLOCK → 立即停止并透传该脚本 verbatim 报告**，不做二次概括（保留"哪一环、为什么"的取证粒度）。
   由 `execute_skill` 失败分支透传 stdout 实现。
3. **派生自单一事实源**：动词的「门禁 step」从 `gate_composition_check.FROZEN_GATES` 派生，
   `validate-verbs` 做机器校验——既不漂移、也不漏掉任何冻结门禁；不另起平行清单。
   selftest 的 `verb_layer_contract` 已锁死。
4. **不触碰 `get_default_pipeline()`**（受 `default_pipeline_contract` 锁定：自动链停在 dev handoff）。
5. **`verify` 失败不自动跑 retry_guard**——重试需人/Agent 给出新假设，由人显式发起
   （达上限转 needs_human，见 `LOOP-CONTROL-GUIDE.md`）。

## 不进日常动词链、按需单独调用的门禁（文档化，不丢失）

- `permissiongate` —— high-risk 时由 `pre_dev_gate` 内部复用（`ALLOWED_GATE_EDGES`）
- `deploygate` —— 部署就绪检查
- `structuregate` —— 项目结构契约（模式 1 初始化）
- `reverse_spec_gate` —— 逆向需求未裁决高风险阻断（模式 2 扫描老项目）
