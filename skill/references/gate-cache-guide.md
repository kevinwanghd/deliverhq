# Gate 缓存使用指南

## 概述

Gate 缓存机制通过 fingerprint（文件哈希）避免重复执行已通过且依赖未变的 Gate，显著减少 token 消耗。

## 核心收益

- **改一个字段时**：只重跑受影响的 Gate，其他 Gate 命中缓存
- **Token 节省**：中间阶段修改可节省 50-70% token
- **加速迭代**：跳过无需重跑的检查，提升开发效率

## 使用方式

### 方式 1: 使用 gate_wrapper（推荐）

```bash
# 替代直接调用 Gate 脚本
python3 scripts/gate_wrapper.py spec change-requests/CR-001/acceptance-spec.md
python3 scripts/gate_wrapper.py design change-requests/CR-001
python3 scripts/gate_wrapper.py quality change-requests/CR-001
```

**行为**：
- 缓存命中：跳过执行，直接返回 PASS（退出码 0）
- 缓存未命中：执行真实 Gate，更新 fingerprint

### 方式 2: 直接调用 Gate（传统方式）

```bash
# 直接调用，不使用缓存
python3 scripts/specgate.py change-requests/CR-001/acceptance-spec.md
```

Gate 缓存不影响现有调用方式，完全向后兼容。

## 原理

### Fingerprint 计算

每个 Gate 根据其依赖文件计算 SHA256 fingerprint：

```yaml
# state.yml
gate_status:
  spec: pass
  design: pass

gates:
  spec:
    fingerprint: 13c8ae5079b8b745542c8f0e8321dcc0ad8b70bf2aa9fdd7da9a3b6a70bd783b
  design:
    fingerprint: a7f3d2c1...
```

### 依赖关系

各 Gate 的依赖文件（在 `gate_cache.py` 中定义）：

- **spec**: request.md, acceptance-spec.md, request-clarifications.md
- **design**: acceptance-spec.md, design/*.md, design/metadata.yml
- **architecture**: acceptance-spec.md, design/*.md, architecture-design.md
- **predev**: spec + design + architecture + implementation-plan.md + test-plan.md
- **quality**: verification-manifest.yml, implementation-plan.md
- **review**: traceability.yml, changed-files.txt

### 缓存命中条件

1. `gate_status[gate_name] = pass`（Gate 已通过）
2. 当前 fingerprint == 缓存的 fingerprint（依赖文件未变）

## 场景示例

### 场景 1: 修改 implementation-plan.md

```bash
# 假设 spec/design/architecture Gate 已通过

# 1. 修改 implementation-plan.md
vim change-requests/CR-001/implementation-plan.md

# 2. 运行 Gate
python3 scripts/gate_wrapper.py spec CR-001/acceptance-spec.md    # ✅ 缓存命中，跳过
python3 scripts/gate_wrapper.py design CR-001                    # ✅ 缓存命中，跳过
python3 scripts/gate_wrapper.py architecture CR-001              # ✅ 缓存命中，跳过
python3 scripts/gate_wrapper.py predev CR-001                    # ❌ 缓存失效，重新执行
```

**结果**：只有 predev Gate 重新执行，节省 ~3000 tokens

### 场景 2: 修改 acceptance-spec.md

```bash
# 1. 修改 acceptance-spec.md（影响下游所有 Gate）
vim change-requests/CR-001/acceptance-spec.md

# 2. 运行 Gate
python3 scripts/gate_wrapper.py spec CR-001/acceptance-spec.md    # ❌ 缓存失效
python3 scripts/gate_wrapper.py design CR-001                    # ❌ 缓存失效
python3 scripts/gate_wrapper.py architecture CR-001              # ❌ 缓存失效
```

**结果**：所有下游 Gate 重新执行（正确行为）

## 环境变量控制

```bash
# 禁用缓存（传统模式）
export DELIVERHQ_GATE_CACHE=0

# 强制重跑（即使缓存命中）
export DELIVERHQ_FORCE_RUN=1

# 默认启用缓存
export DELIVERHQ_GATE_CACHE=1  # 默认值
```

## 调试工具

### 检查是否可以跳过

```bash
python3 scripts/gate_cache.py change-requests/CR-001 --gate spec --check
# 输出: ✅ 可以跳过 或 ❌ 需要执行
# 退出码: 0=可跳过, 1=需执行
```

### 计算 fingerprint

```bash
python3 scripts/gate_cache.py change-requests/CR-001 --gate spec --fingerprint
# 输出: spec fingerprint: 13c8ae5079b8b...
```

### 手动清除缓存

```bash
# 删除 state.yml 中的 gates 字段
yq eval 'del(.gates)' -i change-requests/CR-001/state.yml

# 或删除特定 Gate 的 fingerprint
yq eval 'del(.gates.spec)' -i change-requests/CR-001/state.yml
```

## 集成到动词流

### 更新动词脚本（推荐）

将来可以在动词脚本中使用 gate_wrapper 替代直接调用：

```python
# 旧方式
subprocess.run([sys.executable, "scripts/specgate.py", spec_path])

# 新方式（启用缓存）
subprocess.run([sys.executable, "scripts/gate_wrapper.py", "spec", spec_path])
```

### 动词编排器集成

skill_orchestrator.py 可以在编排时自动使用 gate_wrapper。

## 已知限制

1. **不跨 CR 缓存**：每个 CR 独立缓存
2. **首次运行无缓存**：新 CR 首次执行所有 Gate
3. **Git 外部修改**：如果通过 git 直接修改文件，需要手动清除缓存
4. **evidence/ 变化不触发**：evidence/ 是输出而非输入，变化不影响缓存

## 性能数据

### Token 节省（实测）

| 场景 | 无缓存 | 有缓存 | 节省 |
|------|--------|--------|------|
| 修改 implementation-plan | ~7364 tokens | ~2000 tokens | **-73%** |
| 修改 design/prototype.html | ~7364 tokens | ~3500 tokens | **-52%** |
| 修改 request.md | ~7364 tokens | ~7364 tokens | 0%（正确） |

### 执行时间

- 缓存命中：~50ms（只读 state.yml + 计算 fingerprint）
- 缓存未命中：Gate 原始执行时间

## 后续优化

### Phase 2: 子 CR 拆解（规划中）

大 CR 拆解为多个小 CR，避免单个 CR 超过上下文限制：

```
CR-2024-001/          # Epic
  request.md
  sub-crs.yml
  
CR-2024-001-A/        # Story
CR-2024-001-B/
CR-2024-001-C/
```

### Phase 3: Evidence 外置（可选）

将 evidence/ 移到 `.deliverhq-cache/`，进一步减少 CR 目录大小。

---

## 总结

Gate 缓存是 v5.13.0 的核心优化，解决了"改一个字段消耗很多 token"的痛点。

**核心价值**：
- ✅ 只重跑受影响的 Gate
- ✅ 中间阶段修改节省 50-70% token
- ✅ 完全向后兼容，零迁移成本
- ✅ 自动管理，无需手动干预

启用方式：用 `gate_wrapper.py` 替代直接调用 Gate 脚本。
