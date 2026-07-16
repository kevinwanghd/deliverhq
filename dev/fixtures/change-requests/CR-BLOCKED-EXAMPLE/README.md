# CR-BLOCKED-EXAMPLE

> **警告**：这是一个反例 CR，故意包含错误，用于验证 Gate 能够正确阻断。

## 用途

用于测试 DeliverHQ 的 Gate 脚本是否能正确识别和阻断不合格的文档。

## 包含的错误

### acceptance-spec.md
- ✗ 包含 `{{模板变量}}`
- ✗ 包含 `[待确认]` 占位符
- ✗ 存在 P0 Open Questions (status=open)
- ✗ 包含模糊词但无量化指标

### quality-report.md
- ✗ P0 测试失败
- ✗ 测试覆盖率 < 80%

### context-summary.md
- ✗ 缺失（测试 ContextWindowGate）

## 预期结果

```bash
# SpecGate 应该 BLOCKED
python scripts/specgate.py change-requests/CR-BLOCKED-EXAMPLE/acceptance-spec.md
# 预期输出: ❌ BLOCKED

# QualityGate 应该 BLOCKED
python scripts/qualitygate.py change-requests/CR-BLOCKED-EXAMPLE
# 预期输出: ❌ BLOCKED

# ContextWindowGate 应该 BLOCKED
python scripts/context_window_check.py change-requests/CR-BLOCKED-EXAMPLE
# 预期输出: ❌ BLOCKED
```

## 正例对比

- **正例**: `CR-EXAMPLE` 应该通过所有 Gate
- **反例**: `CR-BLOCKED-EXAMPLE` 应该被所有 Gate 阻断

## 自检集成

`selftest.py` 应该同时验证：
- ✅ CR-EXAMPLE 的 SpecGate PASS
- ✅ CR-BLOCKED-EXAMPLE 的 SpecGate BLOCKED
