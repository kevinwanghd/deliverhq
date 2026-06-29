# Token 优化方案 v2（实用版）

## 调研结论

经过代码审查，发现：
1. **evidence/ 是必要的**：baseline-comparison 需要读取 JSON 来对比
2. **修改所有 Gate 风险大**：40+ 个文件，回归成本高
3. **真正的痛点**：用户反馈的是"改一个字段"就要重跑整个 CR

## 根因重新定位

用户说"改一个字段消耗很多 token"，真正的问题不是 Gate 读取文件，而是：
- **没有增量执行机制**：改一个 spec 字段，要重跑 spec → design → dev → verify 全链路
- **没有断点续传**：QualityGate 失败后，修复代码要重新读取所有上游产物

## 新优化方案：Gate 缓存 + 增量执行

### 优化 1: Gate 结果缓存（最高优先级）

**问题**: 改一个字段后，已通过的 Gate 需要重新执行

**方案**: Gate 结果加 fingerprint 缓存

```yaml
# state.yml
gates:
  spec:
    status: passed
    fingerprint: sha256(request.md + acceptance-spec.md)
    last_check: 2026-06-29T10:00:00Z
  
  design:
    status: passed
    fingerprint: sha256(acceptance-spec.md + design/*.md)
    last_check: 2026-06-29T10:30:00Z
```

**逻辑**:
1. Gate 运行前，计算当前 fingerprint
2. 如果 fingerprint 没变 && status=passed → **跳过执行，直接返回 PASS**
3. 如果 fingerprint 变了 → 重新执行

**收益**: 
- 修改 implementation-plan.md 时，spec/design Gate 直接跳过（节省 ~3000 tokens）
- 只有受影响的 Gate 才重新执行

### 优化 2: 子 CR 拆解（解决"CR 太大"）

**问题**: 单个 CR 包含太多文件，上下文爆掉

**方案**: Epic → Story 拆解（同 v1 设计）

```
CR-2024-001/          # Epic
  request.md
  sub-crs.yml
  
CR-2024-001-A/        # Story
  request.md
  acceptance-spec.md
  ...
```

**实施**: 
- 新增 `decompose` 动词：分析 CR，建议拆解点
- 新增 `create_sub_cr.py`：创建子 CR
- Gate 支持检查子 CR 依赖

### 优化 3: Evidence 外置存储（可选，降低优先级）

**问题**: evidence/ JSON 文件占 39% token

**方案**: 
- evidence/ 移到 `.deliverhq-cache/CR-xxx/evidence/`
- CR 目录只保留符号链接
- Gate 需要时才解析链接读取

**收益**: CR 目录从 7364 tokens → 4500 tokens（-39%）

**风险**: 需要修改所有 Gate 的 evidence 读取路径

---

## 实施计划（调整后）

### Phase 1: Gate 缓存（P0，最快见效）

**工作量**: 1-2 天

1. state.yml 加 fingerprint 字段
2. 每个 Gate 运行前检查 fingerprint
3. fingerprint 计算：`sha256(依赖文件内容)`
4. 验证：修改 implementation-plan.md，spec/design Gate 跳过

**预期**: token 消耗 -50%（中间阶段改动场景）

### Phase 2: 子 CR 拆解（P1，解决大 CR）

**工作量**: 2-3 天

1. 设计 sub-crs.yml schema
2. 实现 decompose 动词（分析拆解点）
3. 实现 create_sub_cr.py
4. Gate 支持子 CR 依赖检查

**预期**: 单个 CR 从 10000+ tokens → 5000 tokens

### Phase 3: Evidence 外置（P2，可选）

**工作量**: 1 天

1. evidence/ 移到 .deliverhq-cache/
2. CR 目录创建符号链接
3. 更新 Gate 读取路径

**预期**: CR 目录 -39% token

---

## 实施：Phase 1 - Gate 缓存

立即实施最高 ROI 的优化。
