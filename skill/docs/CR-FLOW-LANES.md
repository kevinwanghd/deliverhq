# CR Flow Lanes - 三档流程分层

## 设计原则

**不是所有任务都需要完整 CR 流程**。根据风险和复杂度分为三档，避免过度治理。

---

## 三档流程定义

### Fast Lane（快速通道）

**适用场景**:
- 小 bug 修复（< 50 行代码）
- 文档错别字修复
- 配置调整（非生产）
- 日志增强
- 注释补充

**Gate 要求**:
- ✅ SpecGate（简化版，只检查是否有 acceptance-spec.md）
- ✅ QualityGate（只检查构建 + P0 测试）
- ❌ 跳过 DesignGate
- ❌ 跳过 ReviewGate（可选人工审查）
- ❌ 跳过 DeployGate

**预期时间**: < 2 小时

**标识**: CR 目录包含 `lane: fast` 在 metadata.yml

---

### Standard Lane（标准通道）

**适用场景**:
- 标准功能开发
- 代码重构
- 常规需求
- API 新增
- 性能优化

**Gate 要求**:
- ✅ SpecGate（完整）
- ✅ DesignGate
- ✅ ReviewGate
- ✅ QualityGate
- ✅ DeployGate
- ✅ WritebackGate

**预期时间**: 1-3 天

**标识**: CR 目录包含 `lane: standard` 在 metadata.yml（默认）

---

### High-Risk Lane（高风险通道）

**适用场景**:
- 权限和认证相关
- 支付和金融交易
- 数据迁移和备份
- 生产部署脚本
- 安全相关变更
- 核心架构变更

**Gate 要求**:
- ✅ SpecGate（严格模式）
- ✅ DesignGate（架构审查）
- ✅ ReviewGate（对抗式审查，多人）
- ✅ QualityGate（覆盖率 ≥ 90%）
- ✅ DeployGate（包含回滚演练）
- ✅ PermissionGate（新增）
- ✅ WritebackGate
- ✅ **人工最终确认**（必须）

**预期时间**: 3-7 天

**标识**: CR 目录包含 `lane: high-risk` 在 metadata.yml

---

## 使用方式

### 1. 创建 CR 时指定 Lane

```bash
# Fast Lane
python scripts/init_cr.py CR-001 "修复登录按钮样式" --lane fast

# Standard Lane（默认）
python scripts/init_cr.py CR-002 "用户登录日志功能"

# High-Risk Lane
python scripts/init_cr.py CR-003 "支付接口重构" --lane high-risk
```

### 2. Lane 自动决策

如果用户未指定，系统根据关键词自动判断：

**自动判定为 High-Risk**:
- 标题包含：权限、支付、迁移、部署、安全、核心架构
- 修改 protected_paths

**自动判定为 Fast**:
- 标题包含：typo、文档、注释、日志
- 修改行数 < 50

**其他**: Standard Lane

---

## Lane 配置文件

每个 CR 的 `metadata.yml` 包含：

```yaml
cr_id: CR-001
title: "修复登录按钮样式"
lane: fast  # fast | standard | high-risk
created_at: "2026-06-14"
owner: "dev-agent"
risk_level: low  # low | medium | high
estimated_days: 0.5

gates:
  spec: required
  design: skip
  review: optional
  quality: required
  deploy: skip
  writeback: skip
```

---

## Gate 矩阵

| Gate | Fast Lane | Standard Lane | High-Risk Lane |
|------|-----------|---------------|----------------|
| SpecGate | ✅ 简化 | ✅ 完整 | ✅ 严格 |
| DesignGate | ❌ 跳过 | ✅ 必需 | ✅ 架构审查 |
| ReviewGate | ⚠️ 可选 | ✅ 必需 | ✅ 对抗式 + 多人 |
| QualityGate | ✅ 构建 + P0 | ✅ 完整 | ✅ 覆盖率 ≥ 90% |
| DeployGate | ❌ 跳过 | ✅ 必需 | ✅ + 回滚演练 |
| PermissionGate | ❌ 跳过 | ❌ 跳过 | ✅ 必需 |
| WritebackGate | ❌ 跳过 | ✅ 必需 | ✅ 必需 |
| 人工确认 | ❌ 不需要 | ❌ 不需要 | ✅ **必需** |

---

## 实现方式

### 1. init_cr.py 增加 --lane 参数

### 2. pre_dev_gate.py 根据 Lane 决定检查项

### 3. 各 Gate 支持 Lane 模式

- SpecGate 增加 `--mode fast|standard|strict`
- QualityGate 根据 Lane 调整覆盖率阈值
- ReviewGate 根据 Lane 决定是否对抗式审查

---

## 监控指标

- Fast Lane 使用率
- Standard Lane 平均耗时
- High-Risk Lane 人工确认次数
- Lane 误判率（应该 High-Risk 但走了 Standard）

---

**状态**: ✅ 设计完成  
**下一步**: 实现 init_cr.py 的 --lane 参数和 metadata.yml 支持
