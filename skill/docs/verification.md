# 验收标准

> 定义项目级的验收标准和检查清单

## 代码验收标准

### 功能完整性
- [ ] 所有验收场景通过（acceptance-spec.md）
- [ ] 边界条件已测试
- [ ] 异常情况已处理

### 代码质量
- [ ] 单元测试覆盖率 ≥ 80%
- [ ] 无 P0/P1 级别的静态分析告警
- [ ] 代码审查通过

### 文档完整性
- [ ] acceptance-spec.md 无 [待确认] 占位符
- [ ] implementation-plan.md 技术方案清晰
- [ ] traceability.yml 映射完整

### 性能与安全
- [ ] 关键接口性能指标达标
- [ ] 无明显安全漏洞（SQL 注入、XSS、硬编码密钥）
- [ ] 敏感数据已脱敏

---

**使用说明**：
- 每个 CR 交付前对照此清单检查
- 可根据项目特点定制此清单
- Quality Agent 会参考此标准生成 quality-report.md

---

## 证据类型映射（evidence-type-per-claim，借 Superpowers）

> **原则**：每条"完成/通过"声明都必须绑定一种**客观、可复现**的证据类型——
> 不接受 Agent 自报。这张表把 DeliverHQ 已有机制（anti_gaming_check 读 git diff、
> QualityGate 真跑命令、must_haves 谓词）对齐成"声明 ⇒ 必需证据"的统一规约。
> 它是 anti_gaming_check / QualityGate 的文档面，不是新增 Gate。

| 声明类型 | 必需的客观证据 | 由谁取证（已有机制） |
|---|---|---|
| "实现了功能 X" | git diff 中存在对应源码改动 + traceability.yml 映射 | ReviewGate / traceability |
| "测试通过" | 真实执行 verification-manifest 的 test 命令并返回 0 | QualityGate（execute，禁 parse_only 蒙混） |
| "覆盖率达标" | coverage 命令真实输出 ≥ 阈值；阈值未被调低 | QualityGate + anti_gaming_check(#3) |
| "没删测试过关" | git diff 测试用例数净未减少 | anti_gaming_check(#1) |
| "断言仍生效" | git diff 无新增 skip/xfail/注释掉的 assert | anti_gaming_check(#2) |
| "没绕过门禁" | git diff 未改 scripts/*gate*/selftest/*contract* | anti_gaming_check(#4) |
| "改动在范围内" | git diff 落在 goal-contract.allowed_paths 内 | anti_gaming_check(#5) |
| "产物=计划" | must_haves 谓词成立（key_links/artifacts/min_lines/exports/反 stub） | must_haves_check（QualityGate 调用） |
| "PRD↔CR 一致" | PRD 锚点哈希与 CR derived_from 记录一致 | drift_check / SpecGate 检查 9 |

**反模式（明确禁止）**：用"我已确认 / 看起来没问题 / 应该通过"等**叙述性签字**替代上述任一证据。
验收时问 Agent "有没有作弊" 是方法论错误——不能靠问作弊者抓作弊（见 `scripts/anti_gaming_check.py`）。

**模板版本**: v4.5  
**更新日期**: 2026-06-12
