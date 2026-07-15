# Implementation Plan: CR-007

## 技术方案

采用“薄适配器 + 可导入内核”结构：Node CLI 只解析参数和发现项目内核心；Python `deliver.py` 组合 `deliverhq.go`；GoDecision 复用现有路由结果并增加状态发现与工件预检。可靠性修复保持局部，MemoryStore 先做向后兼容 schema 演进。

## 实施步骤

1. 为现有失败补回归测试，修复 Windows 输出、CR-ID 和默认分支行为。
2. 改造包装卫生契约，使测试生成的缓存不污染发布判定。
3. 实现 GoDecision、ArtifactPreflight、活跃 CR 发现和 CLI 转发。
4. 扩展 MemoryEntry 生命周期与语义指纹，保持旧索引兼容。
5. 运行 focused tests、全量 pytest、selftest、npm pack；独立审查 diff。

## 文件边界

允许修改：`bin/cli.js`、`skill/deliverhq/*`、相关 `skill/scripts/*`、`tests/*`、必要入口文档和 CR-007 产物。禁止新增 Gate 或修改冻结 Gate 集合。

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| route/go 逻辑重复 | go 直接调用既有 route 决策函数 |
| 旧 memory index 解析失败 | `from_dict` 对缺失字段补安全默认值 |
| Node 路径发现命中陈旧全局安装 | go 优先项目 `DeliverHQ/`/`.deliverhq/`，测试隔离 HOME |
| selftest 放松后漏发缓存 | 检查 npm pack 发布清单，而不是工作树缓存 |

## 开发进度

| 步骤 | 状态 |
|---|---|
| 规格与架构 | completed |
| 回归测试 | completed |
| 实现 | completed |
| 全量验证 | completed |
| Review/Writeback | completed |
