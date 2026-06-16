# 错误案例库

> 记录开发过程中的错误案例，避免重复犯错

---

**使用说明**：
- QualityGate 失败时自动记录（通过 update_mistake_book.py）
- 也可人工添加值得记录的错误案例
- 定期回顾，转化为 rules.md 中的规则

## 错误案例模板

### 错误：{{CR-ID}} - {{Gate}} 失败
- **日期**：YYYY-MM-DD
- **CR-ID**：CR-XXX
- **失败门禁**：SpecGate / DesignGate / QualityGate / ...
- **问题描述**：{{具体问题}}
- **根本原因**：{{为什么会发生}}
- **改进措施**：{{如何避免}}
- **相关规则**：rules.md #{{规则编号}}

---

**示例**：

### 错误：CR-015 - QualityGate 失败
- **日期**：2026-06-10
- **CR-ID**：CR-015
- **失败门禁**：QualityGate
- **问题描述**：单元测试覆盖率 65%，未达到 80% 目标
- **根本原因**：边界条件测试用例缺失
- **改进措施**：补充边界条件测试（null、空数组、超大值）
- **相关规则**：rules.md #12（单元测试覆盖率 ≥ 80%）

---

**模板版本**: v4.5  
**更新日期**: 2026-06-12

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-14
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65%，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-14
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65%，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-14
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65%，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-14
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65%，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-14
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65%，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-14
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65%，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65%，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65%，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65%，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65%，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65%，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65%，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65%，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65%，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：standard/high-risk CR 缺少 verification-manifest.yml
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65% ，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：standard/high-risk CR 缺少 verification-manifest.yml
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65% ，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65% ，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65% ，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65% ，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65% ，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65% ，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65% ，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65% ，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：构建验证失败; 单元测试失败
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65% ，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65% ，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65% ，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65% ，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查

### 错误：CR-BLOCKED-EXAMPLE - QualityGate 失败
- **日期**：2026-06-15
- **last_seen**：2026-06-15
- **CR-ID**：CR-BLOCKED-EXAMPLE
- **失败门禁**：QualityGate
- **failure_hash**：54672b209790
- **count**：12
- **converted_to_rule**：false
- **rules_candidate**：true
- **问题描述**：quality-report.md 状态为 BLOCKED; P0 通过率 33%，未达标; 测试覆盖率 65% ，目标 ≥ 80%
- **根本原因**：质量检查未通过
- **改进措施**：加强单元测试和代码审查
