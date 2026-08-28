---
name: tdd
description: 测试驱动开发。适用场景：开发新功能（提及"红绿重构"、需要集成测试）、修复 bug（先写失败的测试）、QualityGate 准备（test-plan → verification-manifest）。配合 QualityGate 使用。
---

# Test-Driven Development — DeliverHQ 质量门禁版

TDD 是红 → 绿循环。DeliverHQ 的 TDD 在这个循环上叠加了 Gate 检查：
**Red（写失败的测试）→ Green（只写通过测试的最小代码）→ Refactor → QualityGate**。

## 循环规则

### Red（先写失败测试）

- **只测公共接口**，不测私有实现
- 预期值来自独立真相：已知常量、规格文档、算例
- 不能是循环论证（`expect(add(a,b)).toBe(a+b)` 是白测）
- 按垂直切片写：测一个场景 → 实现 → 再测下一个

### Green（只写通过测试的最小代码）

- **不许写超出当前测试的代码**
- 不要揣测未来需求
- 一个测试 → 一条最小实现路径

### Refactor（重构）

- **不在红绿循环里重构**
- 重构放到 ReviewGate 之后
- 测试本身也要重构（去除重复 setup）

## DeliverHQ 集成

### 1. 写 Test Plan

```bash
# 在 CR 目录下创建 test-plan.md
python DeliverHQ/scripts/pre_dev_gate.py CR-XXX --suggest-lane
```

Test Plan 必须包含：
- 公共接口（seam）列表——**测试前先和用户确认 seams**
- 每个接口的测试场景（正常/异常/边界）
- 预期值来源（规格/常量/算例）

### 2. 写 verification-manifest.yml

```bash
# 生成 minimal 模板
cp DeliverHQ/change-requests/CR-TEMPLATE/verification-manifest-minimal.yml \
   change-requests/CR-XXX/verification-manifest.yml
```

minimal 字段（必须）：
```yaml
test_command: "pytest tests/ -v"
coverage_threshold: 80
signature: "<agent-id>:<timestamp>"
```

### 3. QualityGate 验证

```bash
python DeliverHQ/scripts/qualitygate.py change-requests/CR-XXX/ \
  --manifest verification-manifest.yml
```

QualityGate 是 fail-closed：
- 无 `verification-manifest.yml` → BLOCKED
- `test_command` 失败 → BLOCKED
- 覆盖率低于门槛 → BLOCKED

### 4. 自动记录错误

QualityGate 失败时自动调用：
```bash
python DeliverHQ/scripts/update_mistake_book.py CR-XXX \
  --gate QualityGate --blocker "..."
```

## Anti-patterns

- **循环论证**：断言重新算出期望值，和代码用同样逻辑
- **水平切片**：一次性写完所有测试再一次性写实现
- **私有方法测试**：测实现细节而非行为
- **缺少 seam 确认**：不先问用户就写测试
