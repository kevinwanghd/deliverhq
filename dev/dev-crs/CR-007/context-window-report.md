# ContextWindowGate Report: CR-007

> ContextWindowGate 检查报告。验证滑动窗口纪律：最多 2 个阶段全文，阶段切换必须更新 context-summary.md。

## Verdict
**PASS** / **BLOCKED** / **NEED_HUMAN_DECISION**

## Checked

### 滑动窗口纪律
- [x] / [ ] `context-summary.md` 存在
- [x] / [ ] 当前阶段已标注
- [x] / [ ] 已完成阶段已压缩为摘要
- [x] / [ ] 关键决策已记录
- [x] / [ ] Open Issues 已跟踪

### 阶段切换检查
上次阶段：{{上次阶段名称}}
当前阶段：{{当前阶段名称}}

- [x] / [ ] 阶段切换时 `context-summary.md` 已更新
- [x] / [ ] 上次阶段产物已归档到摘要

### 上下文负载
| 层级 | 内容 | 大小 | 状态 |
|---|---|---|---|
| 当前阶段全文 | {{文档列表}} | {{X}} KB | 已加载 |
| 上一阶段全文 | {{文档列表}} | {{Y}} KB | 已加载 |
| 更早阶段摘要 | context-summary.md | {{Z}} KB | 已压缩 |

**总上下文大小**：{{X+Y+Z}} KB
**阈值**：< 500 KB（建议）

## Blockers

{{如 Verdict = BLOCKED}}

| # | 阻断项 | 说明 |
|---|---|---|
| 1 | {{如：context-summary.md 缺失}} | 阶段切换但未更新摘要 |
| 2 | {{如：携带 3+ 阶段全文}} | 超过滑动窗口限制（max_consecutive_phases_in_full: 2） |
| 3 | {{如：关键决策未记录}} | context-summary.md > Key Decisions 为空 |

## Warnings

{{如 PASS 但有警告}}

| # | 警告 | 说明 |
|---|---|---|
| 1 | {{如：上下文接近阈值}} | 当前 {{X}} KB，接近 500 KB，建议进一步压缩 |
| 2 | {{如：Open Issues 过多}} | {{N}} 个未解决问题，可能影响后续阶段 |

## Evidence

### 检查的文件
- `change-requests/CR-{{ID}}/context-summary.md`
- `change-requests/CR-{{ID}}/acceptance-spec.md`
- `change-requests/CR-{{ID}}/design/**`
- `change-requests/CR-{{ID}}/implementation-plan.md`

### 阶段历史
```
Spec (已完成，已压缩)
  ↓
Design (已完成，已压缩)
  ↓
Context (已完成，已压缩)
  ↓
Dev (上一阶段，全文)
  ↓
Test (当前阶段，全文) ← 当前位置
```

### 摘要完整性
- Spec 摘要：✅ 存在（3 句话概括 + 关键验收条件）
- Design 摘要：✅ 存在（设计要点 + 关键决策）
- Dev 摘要：⚠️ 需补充（当前仅全文）

## Next Actions

### 如 PASS
✅ 放行进入下一阶段

### 如 BLOCKED
❌ 反馈给 Context Agent：
- [ ] 更新 `context-summary.md`
- [ ] 压缩已完成阶段为摘要
- [ ] 记录关键决策
- [ ] 跟踪 Open Issues
- [ ] 重新提交 ContextWindowGate

### 如 NEED_HUMAN_DECISION
⚠️ 以下问题需人工决策：
| # | 决策点 | 选项 | 影响 |
|---|---|---|---|
| 1 | {{如：是否压缩当前阶段}} | 压缩 / 保留全文 | 影响下游可见信息量 |

## 滑动窗口状态

```
[════════════════════════════════════════════]
 Spec  Design Context  Dev   Test  Quality
 (压缩) (压缩) (压缩) (全文) (全文)  (未开始)
                        ↑────↑
                      滑动窗口（2 阶段全文）
```

## Gate 执行日志
- 执行时间：{{timestamp}}
- 执行者：ContextWindowGate Skill
- 检查脚本：`scripts/context_window_check.py`
- 配置：`dir-graph.yaml > context_window`
