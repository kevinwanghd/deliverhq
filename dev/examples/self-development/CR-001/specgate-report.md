# SpecGate Report: CR-001

> SpecGate 检查报告。验证 `acceptance-spec.md` 完备性，确保文档不完备不开发。

## Verdict
**PASS** / **BLOCKED** / **NEED_HUMAN_DECISION**

## Checked

### 验收条件完整性
- [x] / [ ] 存在 `acceptance-spec.md`
- [x] / [ ] 包含 Given-When-Then 验收场景（≥ 3 个）
- [x] / [ ] 非功能需求已量化（性能/安全/可用性）

### 模糊点解决度
- [x] / [ ] 无 `[待确认]` 占位符
- [x] / [ ] 所有模糊点表格已标记为"已解决"
- [x] / [ ] 边界条件已明确定义

### 依赖项就绪度
- [x] / [ ] 所有外部依赖状态为"已就绪"或有明确时间点
- [x] / [ ] 内部依赖已确认可用

### 可测试性
- [x] / [ ] 每个验收条件可自动化测试
- [x] / [ ] 边界条件可重现

## Blockers

{{如 Verdict = BLOCKED，列出阻断项}}

| # | 阻断项 | 类型 | 详情 |
|---|---|---|---|
| 1 | {{如：存在 [待确认] 占位符}} | 模糊点未解决 | 位置：acceptance-spec.md 第 X 行 |
| 2 | {{如：依赖项状态未知}} | 依赖未就绪 | 依赖：{{external_api}} |

## Warnings

{{如 Verdict = PASS，但有警告}}

| # | 警告 | 说明 |
|---|---|---|
| 1 | {{如：性能指标偏宽松}} | P95 < 500ms，建议收紧到 200ms |

## Evidence

### 检查的文件
- `change-requests/CR-{{ID}}/request.md`
- `change-requests/CR-{{ID}}/acceptance-spec.md`

### 扫描结果
- 总验收场景数：{{N}}
- 待确认占位符数：{{M}}（必须 = 0）
- 模糊点数 / 已解决：{{X}} / {{Y}}（必须相等）

### 模板变量检查
```bash
grep -c '{{.*}}' acceptance-spec.md  # 必须 = 0（所有模板变量已替换）
```

## Next Actions

### 如 PASS
✅ 放行进入 Design 阶段（如有 UI）或 Context 阶段（纯后端）

### 如 BLOCKED
❌ 反馈给 Spec Agent 或需求方：
- [ ] 解决模糊点 #1
- [ ] 确认依赖项 #2
- [ ] 替换所有 `[待确认]` 占位符
- [ ] 重新提交 SpecGate

### 如 NEED_HUMAN_DECISION
⚠️ 以下问题需人工决策：
| # | 决策点 | 选项 | 影响 |
|---|---|---|---|
| 1 | {{如：是否包含该边界场景}} | A / B | {{影响范围}} |

## Gate 执行日志
- 执行时间：{{timestamp}}
- 执行者：SpecGate Skill
- 检查脚本：`scripts/specgate.py`
