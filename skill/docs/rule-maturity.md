# Rules 成熟度追踪

> 本文档定义 DeliverHQ 规则成熟度等级及其晋升条件。

## 成熟度等级

| 等级 | 含义 | 晋升条件 | 门禁行为 |
|------|------|----------|----------|
| `draft` | 候选规则，待验证 | 创建后首次引用 | 警告，不阻断 |
| `verified` | 经 CR 引用验证 | 至少 3 次被 CR 引用 + mistake-book 中有相关错误已被修复的证据 | 阻断 |
| `proven` | 经多个 CR 验证 | 至少 5 次被 CR 引用 + 持续遵守无违反记录 | 硬阻断 |

## 晋升规则（P3-3）

### draft → verified 晋升条件

1. **CR 引用次数**：该规则在至少 3 个不同 CR 的 `quality-report.md` 或 `writeback-report.md` 中被引用
2. **证据闭环**：mistake-book 中至少有 1 个相关错误（相同 failure_hash 前缀）已被标记为 `resolved`
3. **人工评审**：rules-candidates.md 中的候选条目经过评审并被晋升

### verified → proven 晋升条件

1. **CR 引用次数**：该规则在至少 5 个不同 CR 中被引用
2. **无违反记录**：连续 10 个 CR 中无违反该规则的记录
3. **使用稳定性**：该规则的触发条件在多个不同类型的需求中得到验证

## 成熟度更新流程

```
CR 交付 → quality-report 引用规则 → mistake-book 相关错误减少
    ↓
update_rule_maturity.py 扫描 delivery/ 中所有 CR 的引用记录
    ↓
自动更新 rules.md 中对应规则的成熟度等级
    ↓
人工评审后晋升或保留当前等级
```

## 当前成熟度分布

| 等级 | 规则数量 | 说明 |
|------|----------|------|
| draft | 3 | 规则 2, 3, 7 |
| verified | 4 | 规则 1, 4, 5, 6 |
| proven | 0 | 尚无达到 proven 等级的规则 |

## 自动更新脚本

```bash
# 扫描 delivery/ 中的规则引用并更新成熟度
python skill/scripts/update_rule_maturity.py
```

## 手动晋升

```bash
# 将候选规则晋升为正式规则
python skill/scripts/promote_rule_candidate.py <CR-ID> --gate P0 --detection static
```
