---
name: code-review
description: 对 PR/分支做代码审查。双轴（Standards + Spec）并行 sub-agent。Dev/Review 必须分离。适用：ReviewGate、对抗式验证、CR 交付前质量检查。
---

# Code Review — DeliverHQ 对抗式验证

ReviewGate 的核心原则：**Dev Agent 和 Review Agent 必须是不同主体**。
干活的人和验收的人不能是同一个 Agent。

## 双轴审查

### 轴 1：Standards（标准合规）
- 本项目 `docs/rules.md` 的正式规则
- `docs/rules-candidates.md` 中的候选规则
- `docs/CONTEXT.md` 的项目词汇
- 反模式检测（Fowler Code Smells baseline）

### 轴 2：Spec（需求忠实）
- CR 的 `acceptance-spec.md`
- PRD 锚点 `[PRD-XXX]`
- `traceability.yml` 需求→代码映射

## 流程

### 1. 固定比较点

```bash
git diff main...<分支>  # 三点 diff，比 main 新增的部分
git log <分支> --oneline  # 提交列表
```

### 2. 识别 Spec 来源（按优先级）

1. 提交信息中的 issue 引用（`#123`、`Closes #45`）
2. CR 目录的 `acceptance-spec.md`
3. `docs/PRD.md` 的功能锚点

### 3. 识别 Standards 来源

- `docs/rules.md`（canonical）
- `docs/rules-candidates.md`（draft）
- `docs/CONTEXT.md`（词汇约定）

### 4. Standards sub-agent 检查

输出格式（每文件/每块）：
```
## [文件名]
- [hard] 违反规则：引用规则（rules.md:行号）
- [judgement] 可能的气味：Mysterious Name — "这行变量名"
```

Fowler Smells Baseline（即使项目无规则也适用）：
- Mysterious Name
- Duplicated Code
- Feature Envy
- Data Clumps
- Shotgun Surgery
- Divergent Change

### 5. Spec sub-agent 检查

输出格式：
```
## [文件名]
- 缺少：spec 要求了但 diff 里没有（引用 acceptance-spec 行号）
- 越界：diff 里有但 spec 没要求（引用 acceptance-spec 行号）
- 实现错误：做出来了但做法不对（引用 acceptance-spec + diff 行号）
```

### 6. 汇总报告

```markdown
## Standards
- 硬违规数: N
- 气味判断数: M
- 最严重: ...

## Spec
- 缺口数: N
- 越界数: M
- 实现错误数: K
- 最严重: ...
```

## ReviewGate 报告

审查结果写入 CR 的 `review-report.md`：
```bash
python DeliverHQ/scripts/reviewgate.py change-requests/CR-XXX/
```

通过 ReviewGate 的条件：
- Standards 无 hard 违规
- Spec 无缺口
- Review Agent 独立完成（不是 Dev Agent 自审）
