# QualityGate Report: {{CR_ID}}

> QualityGate 检查报告。汇总 `quality-report.md` 结果，判定是否放行交付。

## Verdict
**PASS** / **BLOCKED**

## Checked

### P0 检查项通过率
- 文档完备性：{{X}}/{{N}} ✅ / ❌
- 代码质量：{{Y}}/{{M}} ✅ / ❌
- 测试覆盖：{{Z}}/{{K}} ✅ / ❌
- 门禁通过：{{W}}/{{L}} ✅ / ❌

**P0 通过率**：{{(X+Y+Z+W)/(N+M+K+L)*100}}%（必须 = 100%）

### P1 检查项通过率
- 架构一致性：{{A}}/{{B}}
- 可观测性：{{C}}/{{D}}
- 文档同步：{{E}}/{{F}}

**P1 通过率**：{{(A+C+E)/(B+D+F)*100}}%（建议 ≥ 80%）

## Blockers

{{如 Verdict = BLOCKED，列出所有 P0 未通过项}}

| # | 阻断项 | 类型 | 详情 | 责任 |
|---|---|---|---|---|
| 1 | {{如：敏感信息硬编码}} | 代码质量 | 文件：{{path}}，行：{{line}} | Dev |
| 2 | {{如：单测覆盖率 68%}} | 测试覆盖 | 目标 ≥ 80%，差距 12% | Test |
| 3 | {{如：SpecGate BLOCKED}} | 门禁 | 模糊点未解决 | Spec |

## Warnings

{{P1 未通过项}}

| # | 警告 | 类型 | 说明 |
|---|---|---|---|
| 1 | {{如：单文件 3200 行}} | 架构 | `{{ServiceName}}.cs` 超阈值 | 建议拆分 |
| 2 | {{如：关键操作无日志}} | 可观测性 | {{MethodName}} 缺日志 | 补充 |

## Evidence

### 质量报告
来源：`change-requests/CR-{{ID}}/quality-report.md`

- 质量等级：{{🟢 PASS / 🟡 PASS_WITH_WARNING / 🔴 BLOCKED}}
- P0 阻断项数：{{N}}
- P1 警告项数：{{M}}

### 门禁状态
| 门禁 | 状态 | 报告 |
|---|---|---|
| SpecGate | PASS / BLOCKED | `specgate-report.md` |
| DesignGate | PASS / BLOCKED / N/A | `designgate-report.md` |
| ContextWindowGate | PASS / BLOCKED | `context-window-report.md` |

### 测试结果
- 单元测试：{{M}}/{{N}} 通过（{{X}}% 覆盖率）
- 集成测试：{{K}}/{{L}} 通过
- 回归测试：{{A}}/{{B}} 通过（现有 145 个）

### 代码扫描
```bash
# 敏感信息扫描
grep -rE 'password.*=|token.*=' *.cs  # 命中数：{{N}}

# 行数检查
wc -l *.cs | awk '$1 > 3000'  # 超 3000 行文件数：{{M}}
```

## Next Actions

### 如 PASS
✅ 放行进入 Writeback 阶段
- [ ] Writeback Agent 归档交付物
- [ ] Memory Agent 沉淀知识
- [ ] WritebackGate 验证归档完整性

### 如 BLOCKED
❌ 反馈开发者修复：
- [ ] 修复 P0 阻断项 #1
- [ ] 修复 P0 阻断项 #2
- [ ] 修复 P0 阻断项 #3
- [ ] 重新运行 Quality Agent
- [ ] 重新提交 QualityGate

**预估修复时间**：{{X}} 天

## 质量趋势

| 指标 | 本次 | 上次 | 趋势 |
|---|---|---|---|
| P0 通过率 | {{X}}% | {{Y}}% | ↑ / ↓ / → |
| 测试覆盖率 | {{A}}% | {{B}}% | ↑ / ↓ / → |
| 代码行数 | {{M}} | {{N}} | ↑ / ↓ / → |
| 技术债务项 | {{C}} | {{D}} | ↑ / ↓ / → |

## 放行条件清单

- [ ] P0 检查项 100% 通过
- [ ] 所有门禁 PASS
- [ ] 回归测试无失败
- [ ] 无敏感信息硬编码
- [ ] 关键链路无静默吞异常
- [ ] 单测覆盖率 ≥ 80%

**当前状态**：{{X}}/{{N}} 满足

## Gate 执行日志
- 执行时间：{{timestamp}}
- 执行者：QualityGate Skill
- 检查脚本：`scripts/qualitygate.py`
- 输入：`quality-report.md` + Gate 报告
