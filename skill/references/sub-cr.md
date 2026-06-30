# 子 CR 拆解指南（Epic → Story）

## 为什么需要子 CR 拆解

单个 CR 包含全生命周期工件（1400+ 行），大需求塞进一个 CR 会导致：
- **上下文爆掉**：Agent 无法同时处理 spec + design + code + review + test 所有层
- **并发受限**：子任务之间有依赖，但无法独立交付
- **历史不清晰**：一个大 CR 完成后，无法追溯哪个子任务做了什么

**Epic → Story** 模式解决这个问题：Epic 定义总体目标，每个子 CR（Story）独立走完整 Gate 链。

---

## 命名规则

**数字后缀**，无上限，排序自然：

```
CR-001/          # Epic（父 CR）
CR-001-01/       # Story 1
CR-001-02/       # Story 2（依赖 CR-001-01）
CR-001-03/       # Story 3（依赖 CR-001-02）
```

选择数字而非字母（CR-001-A/B/C）的理由：
- 没有26个的上限限制
- 排序直观（CR-001-03 = 第3个）
- 与现有 CR 编号风格一致

---

## 快速上手

### 1. 分析 CR 是否需要拆解

```bash
python3 scripts/skill_orchestrator.py decompose change-requests/CR-001
```

触发建议拆解的阈值（保守）：
- 验收条件 > 10 条
- CR 总量估算 > 5000 tokens

输出示例：

```
⚠️ 建议拆解（触发以下阈值）：
  - 验收条件 12 条（建议上限 10 条）

📋 拆解建议（Epic → Story 模式）：
  python3 scripts/create_sub_cr.py CR-001 --title "功能点 1"
  python3 scripts/create_sub_cr.py CR-001 --title "功能点 2" --depends-on CR-001-01
  ...
```

### 2. 创建子 CR

```bash
# 第一个子 CR（无依赖）
python3 scripts/create_sub_cr.py CR-001 --title "OAuth 2.0 集成"

# 第二个子 CR（依赖第一个完成）
python3 scripts/create_sub_cr.py CR-001 --title "JWT token 管理" --depends-on CR-001-01

# 第三个子 CR（依赖第二个）
python3 scripts/create_sub_cr.py CR-001 --title "权限管理迁移" --depends-on CR-001-02
```

### 3. 每个子 CR 独立走完整 Gate 链

```bash
# 子 CR 的 spec（grill→specgate→drift_check）
python3 scripts/skill_orchestrator.py verb spec change-requests/CR-001-01

# 子 CR 的 dev
python3 scripts/skill_orchestrator.py verb dev change-requests/CR-001-01

# 子 CR 的 verify
python3 scripts/skill_orchestrator.py verb verify change-requests/CR-001-01

# 子 CR 的 archive
python3 scripts/skill_orchestrator.py verb archive change-requests/CR-001-01
```

### 4. 查看 Epic 进度

```bash
# 列出所有子 CR
python3 scripts/create_sub_cr.py CR-001 --list

# 查看完成状态
python3 scripts/create_sub_cr.py CR-001 --status
```

输出示例：
```
=== CR-001 子 CR 列表 ===
Epic: 用户认证系统重构

  ✅ CR-001-01: OAuth 2.0 集成 [archived]
  🔄 CR-001-02: JWT token 管理 [code_review] ← CR-001-01
  ⏳ CR-001-03: 权限管理迁移 [draft] ← CR-001-02

进度: 1/3
```

---

## 目录结构

```
change-requests/
  CR-001/                      # Epic（父 CR）
    request.md                 # 总体需求
    acceptance-spec.md         # 高层验收标准（不涉及实现细节）
    sub-crs.yml                # 子任务清单（由 create_sub_cr.py 自动维护）
    state.yml                  # 父 CR 状态

  CR-001-01/                   # Story（子 CR）
    request.md                 # 子任务需求（引用父 CR）
    acceptance-spec.md         # 子任务规格（具体可测试）
    parent.yml                 # 回指父 CR（由 create_sub_cr.py 自动生成）
    design/
    architecture-design.md
    evidence/
    state.yml

  CR-001-02/                   # Story（依赖 CR-001-01）
    ...
```

### sub-crs.yml 结构

```yaml
epic: CR-001
title: "用户认证系统重构"
sub_crs:
  - id: CR-001-01
    title: "OAuth 2.0 集成"
    status: completed
    depends_on: []
    created_at: "2026-06-28T10:00:00+00:00"

  - id: CR-001-02
    title: "JWT token 管理"
    status: in_progress
    depends_on: [CR-001-01]
    created_at: "2026-06-28T10:01:00+00:00"
```

---

## 设计原则

- **Epic 只走轻量 spec**：Epic CR 只需要 grill + specgate + drift_check，不走 design/dev/verify
- **子 CR 独立走完整链路**：每个子 CR 有独立的 acceptance-spec、design、code、tests、evidence
- **上下文天然隔离**：每个子 CR 的 Gate 链在独立上下文中执行，不互相干扰
- **Gate 缓存自动生效**：子 CR 内修改文件只重跑受影响的 Gate（见 references/gate-cache-guide.md）
- **依赖不自动阻断**：目前依赖是文档化的，不自动检查。未来可加 check_epic_status 集成

---

## 常见问题

**Q: Epic CR 本身需要走多少 Gate？**  
A: 只走 `spec` 动词（grill → specgate → drift_check）。Epic 的目的是定义总体目标和拆解点，不包含实现。

**Q: 子 CR 完成后怎么汇总？**  
A: 用 `python3 scripts/create_sub_cr.py CR-001 --status` 检查所有子 CR 状态。当全部 archived 后，Epic CR 可以进入 archive。

**Q: 可以给子 CR 指定多个依赖吗？**  
A: 可以，`--depends-on CR-001-01 CR-001-02`。

**Q: 已有的大 CR 怎么迁移？**  
A: 
1. 把现有 CR 的 acceptance-spec 提炼成 Epic 高层验收标准
2. 用 `decompose` 分析拆解点
3. 创建子 CR，从模板重新写子任务规格
4. 关闭原来的大 CR

---

## 相关文档

- `references/gate-cache-guide.md` — Gate 缓存机制（子 CR 内自动生效）
- `references/verbs.md` — 5 个用户面动词（含子 CR 的完整流程）
- `scripts/create_sub_cr.py` — 子 CR 创建工具（含 --help）
