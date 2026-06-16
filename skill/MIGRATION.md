# DeliverHQ 迁移指南

> 如何将 DeliverHQ 治理体系迁移到其他 agent 平台（如 Cursor、Windsurf、Cline、其他 AI IDE）

## 验收标准

✅ **完全验收通过**

无论是扫描老项目还是开发新项目，都要在主目录下生成 `DeliverHQ/` 文件夹，包含完整的 46 个文件 + 8 个目录。

```bash
# 运行自检脚本验证完整性
cd DeliverHQ
python3 scripts/check_skeleton.py .

# 预期输出：
# ✅ DeliverHQ 骨架完整，可以用于新项目开发或老项目扫描。
# 目录: 8/8
# 文件: 46/46
```

## 迁移步骤

### 步骤 1：复制整个 DeliverHQ 文件夹

```bash
# 从源项目复制完整 DeliverHQ 目录到新项目
cp -r /path/to/source-project/DeliverHQ /path/to/new-project/

# 或打包传输
cd /path/to/source-project
tar czf deliverhq-skeleton.tar.gz DeliverHQ/
# 在新项目解压
tar xzf deliverhq-skeleton.tar.gz
```

### 步骤 2：定制 DeliverHQ 配置

在新项目中修改以下文件以适配项目：

#### 2.1 `dir-graph.yaml`（必改）
```yaml
workspace:
  name: "NewProject"  # 改为新项目名

# 更新 protected_paths（项目特定的敏感路径）
protected_paths:
  - ../config/production.yml  # 改为新项目的配置文件路径
  - ../src/core/**            # 改为新项目的核心代码路径

# 更新 dev-agent 的 writes 路径
agents:
  dev-agent:
    writes: ['../src/**', '../lib/**']  # 改为新项目的源码目录
```

#### 2.2 `docs/CONTEXT.md`（必改）
```markdown
# Project Context

## Overview
{{新项目描述}}

## Tech Stack
{{新项目技术栈}}

## Architecture Pattern
{{新项目架构模式}}
```

#### 2.3 `docs/architecture.md` / `interfaces.md` / `data-model.md`（必改）
- 清空或替换为新项目的实际架构/接口/数据模型
- 或保留模板结构，标记为 `[待扫描后填充]`

#### 2.4 `docs/rules.md`（可选）
- 保留通用规则（rules #1-6）
- 删除源项目特定规则（rules #7-11）
- 扫描后补充新项目规则

#### 2.5 `docs/decisions.md` / `mistake-book.md`（必清空）
- 删除源项目的决策和错题
- 保留文件结构和表头

#### 2.6 `docs/reports/`（必清空或删除）
- 删除源项目的扫描报告
- 扫描新项目时重新生成

### 步骤 3：在 agent 平台中配置入口

不同平台的配置方式：

#### Cursor / VS Code
在项目根目录创建 `.cursorrules` 或 `.vscode/settings.json`：
```json
{
  "cursor.instructions": "read DeliverHQ/CLAUDE.md and DeliverHQ/AGENTS.md before any development task"
}
```

#### Windsurf
在项目根目录创建 `.windsurfrules`：
```
Before any development:
1. Read DeliverHQ/AGENTS.md
2. Read DeliverHQ/dir-graph.yaml
3. Read DeliverHQ/docs/CONTEXT.md
4. Run python DeliverHQ/scripts/pre_dev_gate.py <CR-ID>
```

#### Cline / 其他
在项目根目录创建 `INSTRUCTIONS.md`：
```markdown
# AI Development Instructions

## Before Writing Any Code

1. Read `DeliverHQ/AGENTS.md` for behavior rules
2. Read `DeliverHQ/dir-graph.yaml` for permissions and protected paths
3. Read `DeliverHQ/docs/CONTEXT.md` for project context
4. If starting a new CR, run: `python DeliverHQ/scripts/pre_dev_gate.py <CR-ID>`

## Fail-Closed Rules

- If CR-ID, current phase, or documentation is unclear, STOP and ASK.
- Do NOT develop when SpecGate, DesignGate, or ContextWindowGate blocks.
- Do NOT modify protected paths without explicit approval.

## 文档不完备 = 不开发

AI 必须验证文档完备性，否则提醒人类工程师阻断开发。
```

### 步骤 4：验证迁移

#### 4.1 运行自检
```bash
cd DeliverHQ
python3 scripts/check_skeleton.py .
# 预期：✅ 34/34 文件完整
```

#### 4.2 测试老项目扫描
让 AI 执行：
```
扫描当前项目，生成 DeliverHQ baseline 和 code-health-report
```

验证：
- `docs/reports/code-health-report.md` 生成且内容适配新项目
- `docs/reports/legacy-scan-report.md` 生成

#### 4.3 测试新项目开发流程
```bash
# 1. 创建测试 CR
cp -r DeliverHQ/change-requests/CR-TEMPLATE DeliverHQ/change-requests/CR-001

# 2. 让 AI 填写 request.md
# 3. 让 AI 运行开发前门禁
python3 DeliverHQ/scripts/pre_dev_gate.py CR-001

# 预期：如果 acceptance-spec.md 缺失或有占位符，应输出 BLOCKED
```

## 关键检查点

### ✅ 必须通过的验收项

| # | 检查项 | 验证方法 |
|---|---|---|
| 1 | DeliverHQ 目录存在于项目主目录 | `ls DeliverHQ/` |
| 2 | 46 个文件 + 8 个目录完整 | `python3 DeliverHQ/scripts/check_skeleton.py .` |
| 3 | `dir-graph.yaml` 已适配新项目 | 检查 `workspace.name` 和 `protected_paths` |
| 4 | `docs/CONTEXT.md` 已更新 | 检查项目描述和技术栈 |
| 5 | AI 能读取 `AGENTS.md` 和 `dir-graph.yaml` | 询问 AI："请总结 DeliverHQ 的行为规则" |
| 6 | AI 开发前会验证文档完备性 | 让 AI 开发一个缺少 acceptance-spec 的 CR，观察是否阻断 |
| 7 | 老项目扫描能生成报告 | 检查 `docs/reports/*.md` 是否生成 |

### ❌ 常见错误

| 错误 | 后果 | 修复 |
|---|---|---|
| 未修改 `dir-graph.yaml` 的项目名和路径 | AI 写入错误路径 | 更新 `workspace.name` 和 `agents.*.writes` |
| 未清空源项目的决策/错题 | 混淆新旧项目知识 | 删除 `docs/decisions.md` 和 `mistake-book.md` 内容 |
| AI 平台未配置入口 | AI 不读取 DeliverHQ 规则 | 创建 `.cursorrules` / `INSTRUCTIONS.md` |
| 跳过 `pre_dev_gate.py` 检查 | 文档不完备仍开发 | 在 AI 指令中强制运行门禁脚本 |

## 平台特定注意事项

### Cursor
- 支持 `.cursorrules` 文件
- AI 会自动读取项目根的 `CLAUDE.md`（如有）
- 建议：在 `.cursorrules` 中引用 `DeliverHQ/AGENTS.md`

### Windsurf
- 支持 `.windsurfrules` 文件
- 可配置多步骤指令链
- 建议：将门禁检查作为前置步骤

### Cline
- 支持项目根 `INSTRUCTIONS.md`
- 建议：显式列出 fail-closed 规则

### 其他平台
- 如不支持配置文件，手动在每次对话开始时提醒 AI：
  > "请先阅读 DeliverHQ/AGENTS.md 和 dir-graph.yaml，了解项目治理规则"

## 成功标志

迁移成功的标志：

1. **老项目扫描**：AI 能在 `DeliverHQ/` 下生成完整的 baseline + 扫描报告
2. **新项目开发**：AI 在开发前主动验证文档完备性，缺失时阻断并提醒
3. **门禁生效**：AI 遵守 SpecGate / DesignGate / QualityGate 等门禁规则
4. **知识沉淀**：每次交付后，AI 更新 `rules.md` / `decisions.md` / `mistake-book.md`

## 疑难解答

### Q: AI 不读取 DeliverHQ 配置怎么办？
A: 在每次对话开始时显式提醒："请先阅读 DeliverHQ/AGENTS.md"；或在平台配置文件中强制加载。

### Q: 文件太多，AI 记不住？
A: DeliverHQ 设计了滑动窗口机制（`context-summary.md`），AI 只需记住当前阶段 + 上一阶段全文，更早的压缩为摘要。

### Q: 如何验证 AI 真的会阻断开发？
A: 创建一个缺少 `acceptance-spec.md` 的 CR，让 AI 开始开发，观察是否提示 BLOCKED。

### Q: 其他项目需要重新生成所有文件吗？
A: 不需要。复制整个 `DeliverHQ/` 文件夹，只修改 `dir-graph.yaml` 和 `docs/CONTEXT.md` 等项目特定文件即可。

## 联系与支持

迁移过程中遇到问题，参考：
- `DeliverHQ/README.md`（使用指南）
- `DeliverHQ/AGENTS.md`（行为规则）
- `DeliverHQ/docs/verification.md`（验收标准）
