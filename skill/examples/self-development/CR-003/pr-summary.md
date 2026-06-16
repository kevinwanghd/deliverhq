# PR Summary: 实现 Loop Mode 执行引擎

> Dev Agent 的交付产物摘要，用于 Human Review

## CR-ID
CR-003

---

## What Changed

{{简洁描述本次变更的核心内容}}

**主要变更**：
- {{变更点 1}}
- {{变更点 2}}
- {{变更点 3}}

---

## Why

{{为什么要做这个变更？解决什么问题？}}

**背景**：{{问题背景}}

**目标**：{{期望达成的目标}}

---

## Linked Requirements

> 对照 acceptance-spec.md 的需求到实现的映射

| 需求 | 对应实现 | 文件 |
|------|----------|------|
| {{验收条件 1}} | {{实现说明}} | {{file.cs:line}} |
| {{验收条件 2}} | {{实现说明}} | {{file.cs:line}} |

**Traceability**: `traceability.yml` 包含完整映射

---

## Files Changed

**新增**：{{数量}} 个文件
- {{file1.cs}}
- {{file2.cs}}

**修改**：{{数量}} 个文件
- {{file3.cs}}
- {{file4.cs}}

**删除**：{{数量}} 个文件
- {{file5.cs}}

**总计**：{{总行数变化，例如：+500 -200}}

---

## Tests Run

### 单元测试
- **执行数量**：{{数量}} 个
- **通过率**：{{百分比}}
- **新增测试**：{{数量}} 个

### 集成测试
- **执行数量**：{{数量}} 个
- **通过率**：{{百分比}}

### 测试覆盖率
- **当前覆盖率**：{{百分比}}
- **变化**：{{+X% / -X%}}
- **目标**：≥ 80%

---

## Risks

### 已识别风险
| 风险 | 严重程度 | 缓解措施 | 状态 |
|------|----------|----------|------|
| {{风险描述}} | {{P0/P1/P2}} | {{缓解方案}} | {{已缓解/待处理}} |

### 潜在影响
- **性能影响**：{{有/无，说明}}
- **兼容性影响**：{{有/无，说明}}
- **数据影响**：{{有/无，说明}}

---

## Rollback Plan

### 回滚触发条件
- {{条件 1，例如：错误率 > 5%}}
- {{条件 2，例如：性能下降 > 50%}}

### 回滚步骤
1. {{步骤 1}}
2. {{步骤 2}}
3. {{步骤 3}}

### 回滚验证
- [ ] {{验证项 1}}
- [ ] {{验证项 2}}

---

## Human Review Checklist

### 代码审查
- [ ] 代码逻辑正确
- [ ] 符合编码规范
- [ ] 无安全隐患
- [ ] 错误处理完善
- [ ] 性能考虑合理

### 需求对照
- [ ] 所有验收条件已实现
- [ ] 无需求范围蔓延
- [ ] 边界条件已处理

### 测试审查
- [ ] 测试覆盖充分
- [ ] 关键路径有测试
- [ ] 测试用例可维护

### 部署审查
- [ ] 部署计划明确
- [ ] 回滚方案可行
- [ ] 影响范围可控

---

## PR Metadata

| 项 | 值 |
|---|---|
| PR URL | {{链接}} |
| PR Type | **Draft** / Ready |
| Source Branch | {{feature/xxx}} |
| Target Branch | {{main/master}} |
| Author | {{AI Agent / Human}} |
| Created At | {{YYYY-MM-DD HH:mm}} |
| Reviewers | {{reviewer1, reviewer2}} |

---

## CI Status

| Check | Status | Link |
|-------|--------|------|
| Build | {{PASS/FAIL/PENDING}} | {{链接}} |
| Test | {{PASS/FAIL/PENDING}} | {{链接}} |
| Lint | {{PASS/FAIL/PENDING}} | {{链接}} |
| Coverage | {{PASS/FAIL/PENDING}} | {{链接}} |

---

## Human Approval

| Reviewer | Decision | Time | Notes |
|----------|----------|------|-------|
| {{Name}} | {{Approved/Rejected/Pending}} | {{YYYY-MM-DD HH:mm}} | {{备注}} |

---

## Output Contract

- [x] Agent 只创建 Draft PR，不直接 merge
- [ ] PR 描述包含 CR 链接
- [ ] PR 描述包含验收项摘要
- [ ] PR 描述包含测试结果
- [ ] PR 描述包含风险说明
- [ ] CI 已运行
- [ ] Human Reviewer 已指定

---

**创建时间**: {{YYYY-MM-DD HH:mm}}  
**最后更新**: {{YYYY-MM-DD HH:mm}}  
**负责人**: {{Dev Agent / Human}}
