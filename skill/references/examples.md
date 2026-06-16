# DeliverHQ Before/After 案例

## Case 1：没有 DeliverHQ

**场景**：开发者让 AI 实现"用户注册功能"

```
用户：帮我实现用户注册功能
AI：好的，我来实现。
（直接写代码，30 分钟后交付）
```

**结果**：
- 没有验收标准 → 返工两次才对齐产品预期
- 没有设计评审 → 密码存储用了明文，上线后才发现
- 没有测试计划 → 边界场景漏测（邮箱重复、密码太短）
- 没有知识沉淀 → 三周后另一人重复踩坑

**代价**：2 天返工 + 1 次安全事故

---

## Case 2：有 DeliverHQ

**场景**：同样的需求，走 DeliverHQ 流程

```
用户：帮我实现用户注册功能
AI：检测到 DeliverHQ 已启用，创建 CR-003。
```

**流程**：

### Step 1: Spec Agent 生成验收规格
- 输入：request.md（一句话需求）
- 输出：acceptance-spec.md（含 5 条可测试验收条件）

### Step 2: SpecGate 检查
```
⚠️ BLOCKED: 验收条件 #3 "密码强度合理" 不可测试
→ 修改为："密码至少 8 位，含大小写和数字"
✅ PASS
```

### Step 3: Design Agent（如有 UI）
- 生成低保真设计
- DesignGate 检查交互完整性

### Step 4: Dev Agent 实现
- 读取 acceptance-spec.md 作为实现约束
- 生成 implementation-plan.md
- 按计划编码

### Step 5: QualityGate
```
✅ 单元测试 12/12 通过
✅ 覆盖率 94%
✅ 无安全漏洞（密码 bcrypt 加密）
✅ PASS
```

### Step 6: Writeback Agent 沉淀知识
- rules.md 新增：「用户密码必须 bcrypt 加密，禁止明文存储」
- decisions.md 记录：「选择 bcrypt 而非 argon2，原因：生态成熟度」

**结果**：
- 一次通过，无返工
- 安全规范自动沉淀，后续 CR 自动遵循
- 验收条件可追溯到代码和测试

---

## 对比总结

| 维度 | 无 DeliverHQ | 有 DeliverHQ |
|---|---|---|
| 验收标准 | 口头/隐含 | 结构化、可测试 |
| 设计评审 | 无 | DesignGate 自动检查 |
| 质量保障 | 靠人记忆 | QualityGate 自动拦截 |
| 知识沉淀 | 不存在 | 自动写入 rules/decisions |
| 返工率 | 高 | 低 |
| 安全风险 | 靠运气 | Gate 拦截 |

---

## 核心价值

DeliverHQ 解决的不是"AI 能不能写代码"，而是：
1. **写之前**：确保需求明确、设计合理
2. **写之中**：约束执行边界、防止越权
3. **写之后**：沉淀知识、防止重复犯错
