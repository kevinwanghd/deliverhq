# Code Review Report: CR-BLOCKED-EXAMPLE

**审查人**: Tech Lead  
**审查时间**: 2026-06-10  
**代码版本**: commit deadbeef

---

## 审查结论

**结论**: ❌ BLOCKED

**总体评价**: 存在阻断性问题，不可进入测试阶段。

---

## 验收条件实现审查

### 场景 1: 核心功能实现
- ❌ 关键接口缺失
- ❌ 与 acceptance-spec.md 不一致

---

## 代码质量审查

### 代码规范
- ❌ 存在明显实现缺陷

### 测试质量
- ❌ 单元测试未覆盖关键路径

---

## Traceability 完整性

- ❌ implementation 与 tests 未完成映射

---

## 发现的问题汇总

### P0 阻断问题
1. 核心接口未实现
2. 关键测试失败

### P1 改进建议
- 修复实现后重新审查

---

## 审查结论

**批准意见**: ❌ REJECTED - 必须修复 P0 问题
