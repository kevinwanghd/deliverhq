# Request: 统一入口、验证闭环与记忆生命周期基础

## CR-ID
CR-007

## 提出人
用户

## 提出日期
2026-07-13

## 需求背景
DeliverHQ 的证据门禁强于纯 Markdown 工作流，但当前入口仍要求用户理解 CR、阶段、路径和底层命令；同时框架自身测试存在默认分支、CR-ID 校验、pytest 收集和缓存卫生误报，mistake-book 也会积累重复且不可失效的条目。

## 业务目标
用一个自然语言入口完成项目内核心发现、风险路由、活跃 CR 恢复和工件预检；修复框架自身验证闭环；为跨 CR 教训提供可去重、可复核、可失效的数据模型。

## 功能描述
1. 新增 `deliverhq go`：读取项目状态，输出目标阶段、当前 CR、缺失工件、恢复动作和可执行命令，默认只读。
2. 修复 Windows 输出、worktree 默认分支与 CR-ID 校验、pytest 测试形态、selftest 包装卫生判定。
3. 升级 MemoryStore：使用 agent 无关路径、稳定 SHA-256 指纹和 lesson 生命周期字段，同时保持旧索引可读。

## 非功能需求
- 兼容 Python 3.10+、Node.js 14+ 和 Windows/macOS/Linux。
- 默认执行不得创建 CR、推进状态或修改业务代码。
- 旧的 MemoryEntry JSON 索引可继续加载。
- 全量 pytest、自检与 npm 包装测试必须通过。

## 约束条件
- 不新增 Gate，不改变现有 Gate 集合和 5 个动词语义。
- 不破坏 `route`、`bootstrap`、`doctor` 等已有 CLI。
- 所有新行为必须有确定性自动化测试。

## 优先级
P0

## 验收标准（高层）
- 用户在项目根运行 `npx deliverhq go "继续" --json` 能得到无占位符的下一步决策。
- 工件缺失时 `go` 返回 `can_proceed=false` 与明确恢复动作。
- 测试和 selftest 在正常生成 Python 缓存后仍全绿。
- 相同根因的 lesson 可合并计数，并支持 active/superseded/deprecated 生命周期。

## 附件
- flow-kit GO、PROGRESS、LESSONS、A-evolve 设计对照分析（本次会话）。
