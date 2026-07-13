# Acceptance Spec: Productize DeliverHQ Packaging and Metadata

## CR-ID
CR-005

## 1. Data Spec

能力记录字段固定为：`id`、`name`、`script`、`status`、`integrated`、`default_enabled`、`allowed_in_pipeline`、`description`。`id` 必须唯一且稳定；状态值必须来自现有枚举。

发布清单记录 npm tarball 的文件数、压缩大小、解压大小和路径列表。任何发布内容都不得包含活动 CR、内部归档实现或开发过程文档。

## 2. Interface Spec

- `deliverhq.capabilities.load_registry()` 返回经过 schema 校验的能力记录。
- `deliverhq.capabilities.render_matrix()` 确定性生成能力矩阵 Markdown 表格。
- `scripts/capability_registry.py check|render` 提供兼容 CLI。
- `scripts/capability_tiers.py` 从 YAML registry 分类，不再解析 Markdown 表格。
- 原 `scripts/execution_runtime.py` 和 `scripts/orchestrator_routing.py` 导入接口继续可用。

## 3. Behavior Spec

### 场景 1：机器能力源生成文档
- **Given** 合法的 `capabilities.yml`
- **When** 运行 registry check/render
- **Then** 所有 ID 唯一、脚本引用有效、生成表格与已提交矩阵一致
- **Measurable Success** 正例返回 0，重复 ID 或非法状态返回非零

### 场景 2：能力分层兼容
- **Given** 当前能力 registry
- **When** 运行 `capability_tiers.py --json`
- **Then** core/on-demand 总数与 registry 一致，分类仍由 `default_enabled` 决定
- **Measurable Success** selftest capability contract 和新增 registry 测试全部通过

### 场景 3：npm 发布瘦身
- **Given** v5.16.0 基线约 367 文件、1.6 MB 解压体积
- **When** 运行 `npm pack --dry-run --json`
- **Then** 发布包不含活动 CR、`examples/self-development`、`docs/superpowers`、`_archived` 实现
- **Measurable Success** 文件数不超过 260，解压体积不超过 1.2 MB

### 场景 4：Python 包兼容
- **Given** 新的 `skill/deliverhq/` 包
- **When** 从包路径或旧 scripts 路径导入 runtime/routing
- **Then** 两种入口指向相同实现，现有 CLI、17 项测试和 37 项 selftest 行为不变
- **Measurable Success** Windows/Linux、Python 3.10/3.13 CI 全部通过

## 非功能验收

- 生成结果确定性：相同 YAML 输入产生字节一致的表格。
- 兼容性：不删除现有公开脚本入口。
- 安全性：registry renderer 不执行 YAML 中的脚本或命令。
- 性能：registry check 在 2 秒内完成。

## Facts

| # | 事实 | 来源 | 确认人 | 日期 |
|---|---|---|---|---|
| F1 | v5.16.0 npm dry-run 为约 367 文件、1.6 MB | npm pack | Codex | 2026-07-12 |
| F2 | capability_tiers 当前解析 Markdown | source inspection | Codex | 2026-07-12 |

## Assumptions

| # | 假设 | 风险级别 | 验证方式 | 验证期限 | 状态 |
|---|---|---|---|---|---|
| A1 | 用户安装只需要模板、运行脚本、核心文档和固定测试样例 | P1 | npm pack 清单 + selftest | PR 合并前 | verified |

## Open Questions

| # | 问题 | 阻断级别 | 负责人 | 截止日期 | 状态 |
|---|---|---|---|---|---|
| Q1 | 第三批架构是否批准 | P0 | Kevin | 2026-07-12 | resolved |

**SpecGate 状态**：READY
