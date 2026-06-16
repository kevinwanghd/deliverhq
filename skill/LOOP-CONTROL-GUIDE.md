# Loop 可控性指南（Goal Contract / 防 Goodhart / 重试上限）

> 把自动化 loop 从"跑任务"升级成"可控、可验证、防钻空子的循环"。
> 核心信条：**信证据不信声明；指标是必要条件不是目标；失败有上限有出口。**

## 一、为什么需要这三件套

AI 自动化 loop 最常见的三种翻车：
1. **目标模糊** —— "自动修复/优化"无法验收，Agent 自说自话完成。
2. **Goodhart / Reward Hacking** —— 为通过指标破坏真实目标（删测试让测试绿、调低阈值、改门禁脚本）。
3. **无限重试** —— 同一错误原地打转，烧 token 不收敛，也不交还人类。

对应三件套：**Goal Contract**（治1）、**反钻空子检查**（治2）、**重试守卫**（治3）。

## 二、Goal Contract（目标契约）

每个自动化 loop 必须先有一份 `goal-contract.yml`（模板见 `change-requests/CR-TEMPLATE/`）。

五段式 + **完成标准双轨**：

```yaml
goal: "为 /todos 接口增加 limit/offset 分页"   # 真实意图，非指标
success_criteria:
  metrics:        # 可测指标（必要条件）
    - id: tests_pass
      command: "pytest tests/"
      expect: exit_zero
  invariants:     # 不变量（防 Goodhart，缺则校验 BLOCK）
    - tests_not_reduced
    - coverage_threshold_not_lowered
    - gate_scripts_unmodified
    - no_disabled_assertions
verification_commands: [...]   # 必须真实执行，输出即证据
boundaries:
  allowed_paths: ["src/**", "tests/**"]
  forbidden_actions: ["删除测试以让测试通过", "降低 Gate 阈值", ...]
on_failure:
  max_retries: 3
  retry_requires_new_hypothesis: true
  on_exhausted: needs_human
escalate_to_human_when: [...]
```

**关键设计：`metrics` + `invariants` 双轨。** 只写 `metrics`（"test 全绿"）会被"删测试"达成——指标不等于目标。`invariants` 是兜底的不变量，由反钻空子检查从 git diff 客观核验。

校验：
```bash
python scripts/goal_contract.py change-requests/CR-XXX
# 缺 invariants → BLOCK（堵 Goodhart 漏洞）；目标模糊/占位符 → BLOCK
```

## 三、反钻空子检查（从证据查，不问 Agent）

```bash
python scripts/anti_gaming_check.py change-requests/CR-XXX
```

从 **git diff 客观检测**五类作弊（任一命中 → BLOCK，交还人类）：

| 检测项 | 信号 |
|--------|------|
| 删测试过关 | 测试函数定义净减少 |
| 禁用断言 | 新增 skip/xfail/注释掉的 assert |
| 降阈值过关 | coverage_threshold/threshold 被调低 |
| 改门禁绕过 | scripts/*gate*.py、selftest.py、*contract*.py 被改 |
| 超范围 | 改动落在 goal-contract.allowed_paths 之外 |

**方法论要点**：不设"问 Agent 有没有作弊"这种自评问答——那违背"不信 Agent 自报"原则。一律从 diff 取证。非 git 环境无法取证时降级为 WARNING（不假 PASS）。

## 四、重试守卫（防无限重试 + needs_human 出口）

```bash
# 每次失败记录一次，带新假设
python scripts/retry_guard.py change-requests/CR-XXX record \
    --gate QualityGate --blocker "单元测试失败" --hypothesis "怀疑异步竞争，改用 await"

# 查看重试状态
python scripts/retry_guard.py change-requests/CR-XXX status
```

规则：
- **同类失败**判定复用 `failure_attribution`（gate + failure_type），避免"换个错误信息就重置计数"。
- 达 `max_retries`（默认 3，可被 goal-contract 覆盖）→ CR 进入 `needs_human` 状态（写回 state.yml）。
- **每次重试必须带新假设**，与上次同类相同 → 拒绝（禁止原地重复打转）。

## 五、loop 生命周期与状态

CR 状态（`cr_state.py`）：
```
draft → spec_review → ... → code_review → testing → deploy_ready → deployed → archived
                                                    ↘ blocked
                                                    ↘ needs_human   ← 重试耗尽 / 检测到钻空子 / 高风险决策
                                                    ↘ cancelled
```

`needs_human` 是本次新增的关键出口：当 loop 无法自行收敛时，明确交还人类，而不是无限重试或假装成功。

## 六、推荐串联（一个 loop 的完整防护）

```bash
# 0. 启动前：目标契约合规
python scripts/goal_contract.py change-requests/CR-XXX        # 不合规不启动

# ... Agent 开发 ...

# 1. 验收时：真实门禁 + 反钻空子（信证据）
python scripts/qualitygate.py change-requests/CR-XXX
python scripts/anti_gaming_check.py change-requests/CR-XXX    # 查 reward hacking

# 2. 失败时：记录 + 重试上限
python scripts/retry_guard.py change-requests/CR-XXX record --gate QualityGate --blocker "..." --hypothesis "..."
# 耗尽 → needs_human，交还人类
```

## 七、诚实边界

- 三件套均标记为 **experimental**（见 CAPABILITY-MATRIX.md）。
- 反钻空子检查覆盖"最常见"的钻空子，非全部；它提高作弊成本，不能证明绝对没作弊。
- 重试"同类失败"判定依赖 failure_attribution 的归因质量，归因错分可能影响计数。
- 这三件套**降低**翻车概率、**提高**可复盘性，但不替代人工审查 —— 这正是 needs_human 出口存在的意义。
