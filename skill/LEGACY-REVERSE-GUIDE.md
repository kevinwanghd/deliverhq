# 老项目逆向改造指南（目标2）

> 把老项目转化成"可通过需求文档驱动开发"的项目。
> 核心原则：**逆向无独立真相可对照，因此高风险模块强制人工裁决，bug 不得被固化为需求。**

## 为什么需要人工裁决

正向开发（目标1）是 `需求 → 代码`，需求是人给的"应该是什么"，门禁能卡住。
逆向（目标2）是 `代码 → 需求 → 再开发`，而"从代码猜需求"这一步天生没有真相可对照：

- AI 可能把 **bug 当成 feature**
- 把**临时 workaround 当成设计意图**
- 漏掉代码里没体现的**隐性业务规则**

最危险的不是"AI 说不确定"的模块（会被人审），而是 **AI 自信但理解错了** 的模块。
所以本流程**不靠 AI 自评**决定哪些要人看，而是靠**客观信号**（无测试/敏感域/高复杂/高频改动/与现有测试矛盾）。

## 完整流程（5 步）

```
代码 → [1.scan] → 候选 → [2.AI填推断] → [3.人工裁决] → [4.Gate] → [5.转化] → acceptance-spec → 正向开发链路
```

### 步骤 1：客观扫描

```bash
python scripts/scan_legacy.py <老项目源码目录> \
    --out change-requests/CR-XXX/reverse-spec-candidates.yml \
    --report change-requests/CR-XXX/legacy-scan-report.md
```

产出 `reverse-spec-candidates.yml`，每个模块一个候选条目，**客观层已填**：
- `test_coverage`（none/partial/full）
- `complexity`（low/medium/high）
- `sensitive_domain`（auth/payment/data/permission/crypto/external）
- `change_frequency`（来自 git 历史）
- `review_required` —— 由上述客观信号**自动推导**，AI 无权降级

### 步骤 2：AI 填推断层（草稿）

AI 为每个候选填写（这是**草稿，待证伪**，不是结论）：
- `inferred_behavior`：从代码推断该模块在做什么
- `assumptions`：代码未明确证实的假设（高危项，人工必看）
- `evidence.contradicting_tests`：与推断矛盾的现有测试（非空会强制 review）

### 步骤 3：人工逐条裁决

```bash
# 列出待裁决的高风险条目
python scripts/confirm_reverse_spec.py change-requests/CR-XXX/reverse-spec-candidates.yml --list

# 确认为真需求（必须给验收条件）
python scripts/confirm_reverse_spec.py <yml> --id RC-002 --action confirm \
    --criteria "连续5次密码错误后账户锁定30分钟" --by "张三"

# 判定为 bug/技术债（不固化为需求，入 known-deviations）
python scripts/confirm_reverse_spec.py <yml> --id RC-005 --action reject \
    --note "历史 bug，应修复而非固化" --by "张三"

# 暂缓
python scripts/confirm_reverse_spec.py <yml> --id RC-007 --action defer
```

**每条必须回答 `is_real_requirement`：真需求 还是 bug/技术债？** 这是防止把现状固化的关键。

### 步骤 4：ReverseSpecGate（硬约束）

```bash
python scripts/reverse_spec_gate.py change-requests/CR-XXX
```

BLOCK 条件（任一）：
1. 存在 `review_required:true` 且 `unconfirmed` 的高风险条目
2. 已确认但未回答 `is_real_requirement`
3. 标为真需求却没写验收条件

### 步骤 5：转化为正向开发文档

```bash
python scripts/reverse_to_spec.py change-requests/CR-XXX
```

产出：
- `acceptance-spec.md` —— **能通过 SpecGate**，无缝进入正向开发链路（目标1）
- `traceability.yml` —— 反向映射：需求 → 现有代码 → 现有测试
- `known-deviations.md` —— 被判定为 bug/债的条目（改造 CR 的候选输入）

之后即可运行 `specgate.py` 验证，进入目标1 的正向门禁链路。

## "转化成功"的可验证标准

老项目转化完成 = 同时满足：
- ✅ 所有 `review_required` 条目都已裁决（无 `unconfirmed`）→ ReverseSpecGate PASS
- ✅ 所有真需求条目都有 `becomes_acceptance_criteria` 且反向映射到现有代码
- ✅ 转化产出的 `acceptance-spec.md` 通过 SpecGate
- ✅ 敏感域模块 100% 经人工确认

## 边界与诚实声明

- 本能力标记为 **experimental**（见 CAPABILITY-MATRIX.md）
- 它**加速**逆向，但**不保证**逆向的绝对正确——最终正确性依赖人工裁决质量
- 复杂度估算对非 Python 语言为近似（按行数）；Python 用 AST 较准
- `test_coverage` 为粗粒度判断（测试文本是否提及模块名），不等于真实覆盖率
- selftest 的 `reverse_spec_contract` 检查保证这条链路始终可用（非文档摆设）
