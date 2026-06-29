# Token 优化设计（v5.13.0）

## 问题诊断

### 问题 1: 改一个字段消耗很多 token

**数据**:
- 单个 CR 总计: **7,364 tokens** (~30KB)
- 热点: evidence/ (2,859 tokens, 39%) + reports (1,849 tokens, 25%)
- Gate 每次都全量读取上游产物

**根因**:
- 没有增量加载
- evidence/ JSON 文件累积（baseline 每个 578 tokens）
- traceability.yml 765 tokens，每个 Gate 都读

### 问题 2: CR 拆解太大，上下文爆掉

**数据**:
- CR-EXAMPLE: 1,429 行文件
- 从 request 到 writeback 全生命周期塞在一起
- 没有子任务拆解机制

---

## 优化方案

### P0: 延迟加载 evidence/ 和 reports/

**目标**: 减少 Gate 执行时的 token 消耗 60%+

**实施**:

1. **evidence/ 不自动加载**
   - Gate 脚本改为只验证 evidence/ 文件存在性
   - 只在 BLOCKED 或 debug 模式时才读取内容
   - 节省: ~2,859 tokens/次

2. **reports/ 延迟加载**
   - SpecGate/DesignGate/等中间 Gate 不读 report
   - 只有 WritebackGate 才读取所有 report
   - 节省: ~1,849 tokens/次

3. **traceability.yml 指针化**
   - Gate 只验证文件存在 + 读取摘要（前 10 行）
   - 完整内容只在 ReviewGate/WritebackGate 时读取
   - 节省: ~700 tokens/次

**预期效果**: Gate 执行从 ~7,364 tokens → ~2,000 tokens（-73%）

---

### P1: 子 CR 机制（Epic → Story）

**目标**: 大需求拆解为多个小 CR，避免单个 CR 超过上下文

**设计**:

```
change-requests/
  CR-2024-001/              # Epic (父 CR)
    request.md              # 总体需求
    acceptance-spec.md      # 高层验收标准
    sub-crs.yml             # 子任务清单
    state.yml               # 父 CR 状态

  CR-2024-001-A/            # Story (子 CR)
    request.md              # 子任务需求（引用父 CR）
    acceptance-spec.md
    design/
    ...
    state.yml
    parent: CR-2024-001     # 指向父 CR

  CR-2024-001-B/            # Story (子 CR)
    ...
```

**sub-crs.yml 结构**:

```yaml
epic: CR-2024-001
title: "用户认证系统重构"
sub_crs:
  - id: CR-2024-001-A
    title: "OAuth 2.0 集成"
    status: completed
    dependencies: []

  - id: CR-2024-001-B
    title: "JWT token 管理"
    status: in_progress
    dependencies: [CR-2024-001-A]

  - id: CR-2024-001-C
    title: "权限管理迁移"
    status: pending
    dependencies: [CR-2024-001-B]
```

**流程**:
1. 用户创建 Epic CR（定义总体目标）
2. `grill` 或 `spec` 阶段识别需要拆解
3. 生成 sub-crs.yml，创建子 CR 目录
4. 每个子 CR 独立走完流程
5. 所有子 CR 完成后，Epic CR 进入 writeback

**新增命令**:

```bash
# 创建子 CR
python3 scripts/create_sub_cr.py CR-2024-001 --title "OAuth 2.0 集成"

# 检查 Epic 状态
python3 scripts/check_epic_status.py CR-2024-001
```

---

### P2: 懒归档 + 摘要前置

**目标**: 只保留当前阶段需要的信息在上下文中

**懒归档**:

```
CR-EXAMPLE/
  request.md              # 当前阶段需要的
  acceptance-spec.md
  design/
  state.yml

  _archive/               # 已完成阶段产物
    review-report.md
    quality-report.md
    evidence/
```

**触发时机**: 每个 Gate PASS 后，将该阶段产物移到 `_archive/`

**摘要前置**:

每个大文件（>200 行）前加 TLDR：

```markdown
<!-- TLDR
架构决策: 采用微服务 + API Gateway
关键组件: UserService, AuthService, Gateway
测试接缝: REST API 层
-->

# Architecture Design
...
```

Gate 优先读 TLDR，只在需要时读全文。

---

## 实施计划

### Phase 1: 延迟加载（P0，1-2 天）
- [ ] 修改所有 Gate 脚本，移除自动加载 evidence/
- [ ] traceability.yml 改为只读摘要
- [ ] 增加 `--debug` 标志，允许全量读取（用于 troubleshooting）
- [ ] 验证: selftest 36/36，token 消耗 -70%

### Phase 2: 子 CR 机制（P1，2-3 天）
- [ ] 设计 sub-crs.yml schema
- [ ] 实现 create_sub_cr.py
- [ ] 实现 check_epic_status.py
- [ ] Gate 支持子 CR 依赖检查
- [ ] 验证: 手动创建 Epic + 3 个子 CR，全流程通过

### Phase 3: 懒归档（P2，1 天）
- [ ] 每个 Gate PASS 后移动产物到 _archive/
- [ ] 更新 Gate 读取路径（支持 _archive/ 回溯）
- [ ] 验证: CR-EXAMPLE 完整流程后，顶层只剩当前阶段文件

---

## 衡量标准

### Token 优化目标
- Gate 执行: 7,364 tokens → **2,000 tokens**（-73%）
- CR 总大小上限: 10,000 tokens（超过则强制拆解）

### CR 拆解目标
- 单个 CR 上限: **5,000 tokens**
- Epic 支持: 最多 10 个子 CR
- 子 CR 自动依赖检查

---

## 兼容性

- 现有 CR 无需迁移（向后兼容）
- 新 CR 自动应用优化
- 可通过 `--legacy-mode` 禁用优化（用于回归测试）
