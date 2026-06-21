# Project Structure Governance

> 目标：让项目从第一天起拥有 AI 友好、人类易复查、可长期维护的目录结构。

DeliverHQ 的结构治理不是 create-next-app，也不是自动重构老项目。它只做三件事：

1. 用 `STRUCTURE-PROFILE.yml` 描述项目结构契约。
2. 用 `REPO_MAP.md` / `COMMANDS.yml` 给人和 AI 共同导航。
3. 用 `StructureGate` 检查明显结构漂移。

## 新项目：strict mode

```bash
deliverhq init-project --profile fullstack-web
python DeliverHQ/scripts/structuregate.py . --profile DeliverHQ/STRUCTURE-PROFILE.yml
```

生成内容：

- `apps/web`
- `apps/api`
- `apps/worker`
- `packages/shared-types`
- `packages/sdk`
- `packages/ui`
- `config`
- `docs`
- `tests/e2e`
- `infra`
- `scripts`
- `DeliverHQ/STRUCTURE-PROFILE.yml`
- `DeliverHQ/REPO_MAP.md`
- `DeliverHQ/COMMANDS.yml`

不生成：

- 业务代码
- API handler
- UI component
- 数据库 schema
- CI workflow
- Docker 镜像配置

## 老项目：progressive mode

老项目不要自动搬目录。先扫描：

```bash
python DeliverHQ/scripts/scan_legacy_structure.py .
```

输出：

- `DeliverHQ/docs/reports/structure-assessment-report.md`
- `DeliverHQ/STRUCTURE-PROFILE.candidate.yml`

原则：

- 历史问题先 warning，不直接大搬家。
- 新代码必须进入目标结构。
- 结构迁移必须按模块创建 migration CR。
- 旧目录可以 fenced，但不能继续扩散。

## AI 友好规则

- AI 修改前必须读 `DeliverHQ/REPO_MAP.md`。
- AI 必须读 `DeliverHQ/STRUCTURE-PROFILE.yml` 判断文件应该放哪里。
- 不允许创建未授权顶层目录。
- 不允许把测试放在根目录。
- 不允许提交 `.env` / `.env.production`。
- 新后端模块放 `apps/api/src/modules/<feature>`。
- 新前端功能放 `apps/web/src/features/<feature>`。
- 共享契约放 `packages/shared-types`。

## 人类复查规则

Review 顺序建议：

1. `STRUCTURE-PROFILE.yml`：结构契约是否合理。
2. `REPO_MAP.md`：模块边界是否清楚。
3. `COMMANDS.yml`：验证命令是否真实可运行。
4. PR diff：按 apps / packages / infra / docs / DeliverHQ 分区审查。
5. `traceability.yml`：需求 → 代码 → 测试 → impact 是否闭合。

## StructureGate MVP 检查

P0 阻断：

- 缺少 `STRUCTURE-PROFILE.yml`
- 缺少 required dirs
- 出现 forbidden top-level dirs
- 提交 `.env` 或 `.env.production`
- 测试文件出现在错误位置
- backend/frontend/config 文件违反 profile placement rules

P1 警告：

- legacy paths 在 progressive mode 中仍存在
- Agent writes / protected paths 需要人工复核

## 明确不做

- 不自动重构老项目目录
- 不生成业务代码
- 不引入 GitNexus / Graphify
- 不做 Dashboard
- 不做 Dynamic Workflow Executor
- 不自动发布或自动合并
