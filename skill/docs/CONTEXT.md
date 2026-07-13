# Project Context
> 这是 DeliverHQ 安装包的安全占位页，不代表宿主项目事实。不要把示例技术栈、命令或架构写成 confirmed 信息。

## Bootstrap Status

- status: unscanned
- authority: host project documents + repository evidence
- command: `npx deliverhq bootstrap --path <host-repo> --json`

## Context Source Policy

首次进入已有项目时：

1. 先发现 `AGENTS.md`、`CLAUDE.md`、Cursor/Windsurf/Copilot 规则、`ARCHITECTURE.md`、`CONTRIBUTING.md` 与 README。
2. 保留这些文档各自的权威范围，不强制复制成单一大文档。
3. 代码扫描结论必须附 path、line 和 SHA-256；无证据推断只能标 inferred。
4. `bootstrap --apply` 只生成 `DeliverHQ/*.candidate`，人工审查后再采用。
5. 架构大改或扫描超过 90 天时重新运行 Bootstrap。

## Expected Project Context

人工确认后的宿主上下文应覆盖：

- 产品/业务边界与域语言
- 技术栈、版本和权威命令
- Module、Interface、依赖方向和关键数据流
- 既有抽象索引与复用规则
- protected paths、敏感域和禁动清单
- 测试、CI、部署和回滚方式
- 已知技术债、假设和证据来源

## DeliverHQ Governance Pointers

- 行为规则：`AGENTS.md`
- 目录权限：`dir-graph.yaml`
- 仓库地图：`REPO_MAP.md`
- 权威命令：`COMMANDS.yml`
- 能力状态：`CAPABILITY-MATRIX.md`
- 当前 CR：`change-requests/CR-*`
