# 架构设计：证据化 Bootstrap、轻路由与 Brownfield 护栏

## CR-ID
CR-006

## 1. 模块拆分与目录结构

| Module | 职责 | 文件落点 |
|---|---|---|
| Legacy Scan Facade | 组合现有结构/行为扫描，发现现有上下文并产证据报告 | `skill/scripts/bootstrap_project.py`，复用 `scan_legacy*.py` |
| npm CLI Adapter | 暴露 bootstrap Interface，不承载扫描逻辑 | `bin/cli.js` |
| Routing Module | 在现有 CLI 决策 seam 内扩展 Gate 计划和成本模型 | `skill/scripts/deliver.py` |
| Plan Evidence | 校验 read/write、reuse 和 destructive evidence | `skill/scripts/plan_checker.py` |
| Context Evidence | 校验来源哈希、两阶段窗口和恢复字段 | `skill/scripts/context_window_check.py` |
| Templates/Docs | 提供稳定 schema 和用户说明 | CR 模板、README、能力矩阵、references |

## 2. 数据流与状态管理

```text
repo → existing-doc discovery → existing Legacy scanners → evidence normalization
     → BootstrapReport → stdout/json → optional create-only candidate write

request → existing classifier → lane → Gate plan + explainable cost range

plan/context artifacts → deterministic validators → PASS/BLOCK evidence
```

Bootstrap 不建立第二套 scanner。现有扫描器负责事实采集，Facade 负责组合、来源归一和输出。

## 3. 接口封装与依赖

- `build_bootstrap_report(repo: Path) -> dict`
- `apply_candidates(report, deliverhq_home) -> list[dict]`
- `estimate_route_cost(decision, factors) -> dict`
- Plan task schema：`read_files/write_files/reuse_checks/destructive_change`
- Context handoff schema：`sources/input_hashes/excluded_approaches/next_action`

只使用现有依赖。所有路径经过 resolve 和仓库范围检查。

## 4. 异常处理与验证策略

- 无效路径 fail-fast。
- 单个探针失败进入 warnings，其他扫描继续。
- candidate 写入逐文件原子化，已有文件不覆盖。
- Gate 缺证据 fail-closed。
- route 新字段为 additive change。

## 5. 测试接缝

| Seam | 覆盖 | 类型 |
|---|---|---|
| `node bin/cli.js bootstrap/route` | 用户可见 CLI | 集成 |
| Python Module Interface | 报告、成本、hash、evidence | 单元 |
| selftest contracts | 安装包内能力 | 契约 |

复用现有最高 Interface，不针对每个 helper 扩大测试表面。

## 6. 设计分块到实现映射

| Block | 文件 | 证据 |
|---|---|---|
| T1 Bootstrap Facade | bootstrap script、CLI、tests | AC-1/2 |
| T2 Route cost | routing/deliver/tests | AC-3 |
| T3 Plan evidence | plan checker/template/tests | AC-4/5 |
| T4 Context handoff | context gate/template/tests | AC-6 |
| T5 Docs/registry | README、capabilities、references | packaging/selftest |

## 7. 平台与 UI

无 UI。使用 pathlib 与 Node path 保持跨平台。

## ArchitectureGate 检查点

- [x] 没有复制 Legacy Scan 实现
- [x] 没有新增 Gate
- [x] 写入集中在 create-only adapter seam
- [x] 测试覆盖最高 Interface
- [x] 所有 block 有落点和验收条件
- [x] 无模板变量

**ArchitectureGate 状态**：READY
**人工确认**：已确认（Kevin / 2026-07-12，指令：全部完成并验收后提交 GitHub）
