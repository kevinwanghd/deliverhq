# Gate 错误信息改进指南

## 当前状态

v4.8.1 的 Gate 错误信息已经比较清晰，基本遵循以下格式：

```python
# ✅ 好的错误信息
blockers.append("P0 通过率 65%，未达标（目标 100%）")
blockers.append("缺少章节: Data Spec, Behavior Spec")
blockers.append("包含 3 处 [待确认] 或 [TODO] 未解决")

# ❌ 需要改进的错误信息
blockers.append("验收场景缺失")  # 太简略
blockers.append("文档不完整")    # 不明确
```

---

## 改进原则

### 1. 说明具体问题
❌ "验收场景缺失"  
✅ "验收场景缺失：未找到 '### 场景' 章节，至少需要 1 个验收场景"

### 2. 提供可操作指引
❌ "文档不完整"  
✅ "缺少章节: Data Spec, Interface Spec。请参考 acceptance-spec.md 模板补充"

### 3. 量化具体数值
❌ "测试不通过"  
✅ "P0 测试通过率 65%（目标 100%），失败: test_login, test_checkout"

### 4. 说明位置和上下文
❌ "模板变量未替换"  
✅ "包含未替换模板变量: {{FEATURE_NAME}}, {{DEADLINE}}（共 3 处）"

---

## 各 Gate 错误信息审查

### ✅ SpecGate (scripts/specgate.py)

**状态**: 错误信息已经很清晰  

**示例**:
- ✅ "缺少 SDD 结构: Data Spec（数据规格）, Interface Spec（接口规格）"
- ✅ "包含模板变量: {{FEATURE_NAME}}, {{AUTHOR}}（共 3 处）"
- ✅ "包含 5 处 [待确认] 或 [TODO] 未解决"
- ✅ "P0 Open Questions 未解决"
- ✅ "包含模糊词但无量化指标: 尽快, 优化, 高性能 等 7 个"

**无需改进**

---

### ✅ QualityGate (scripts/qualitygate.py)

**状态**: 错误信息已经清晰

**示例**:
- ✅ "P0 通过率 65%，未达标（目标 100%）"
- ✅ "测试覆盖率 45%，目标 ≥ 80%"
- ✅ "构建验证失败"
- ✅ "单元测试失败"

**无需改进**

---

### ✅ ReviewGate (scripts/reviewgate.py)

**状态**: 错误信息基本清晰

**示例**:
- ✅ "review-report.md 状态为 BLOCKED"
- ✅ "review-report.md 结论不明确"
- ✅ "存在 3 个 P0 阻断问题"
- ✅ "缺少章节: 代码审查结论, P0 问题列表"

**无需改进**

---

### ✅ WritebackGate (scripts/writeback_gate.py)

**状态**: 错误信息基本清晰

**示例**:
- ✅ "缺少章节: 技术决策, 遇到的问题, 经验总结"
- ✅ "包含模板变量，未填充实际内容"
- ✅ "traceability.yml 未填充实际内容"

**无需改进**

---

### 🟡 DesignGate (scripts/designgate.py)

**需要检查**: 未在 grep 结果中出现，可能缺少清晰的 blocker 信息

**优先级**: P2（非关键路径）

---

### 🟡 DeployGate (scripts/deploygate.py)

**需要检查**: 未在 grep 结果中出现

**优先级**: P2（非关键路径）

---

## 总结

**当前状态**: v4.8.1 的主要 Gate（Spec/Quality/Review/Writeback）错误信息已经符合清晰化标准

**建议**:
- P1: 无需额外改进（已满足要求）
- P2: 可以检查 DesignGate 和 DeployGate 是否需要优化

**结论**: ✅ P1-5 任务实际上已经在 v4.7/v4.8 开发中完成，当前版本错误信息已经清晰
