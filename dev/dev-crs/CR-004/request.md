# Request: Modularize DeliverHQ Runtime

## CR-ID
CR-004

## Goal

完成第二批可维护性改造，在保持现有 CLI、Gate 结果、状态推进和 `selftest` 输出兼容的前提下：

1. 建立统一的脚本执行接口，供 Gate wrapper 和 orchestrator 复用。
2. 将 `skill_orchestrator.py` 的路由、成本估算与执行职责拆开。
3. 将 `selftest.py` 按契约域拆分，保留原一键入口和汇总格式。

## Constraints

- 不新增、删除或重命名冻结 Gate。
- 不改变公开 CLI 参数和退出码。
- 不改变现有 37 项 selftest 契约名称与汇总语义。
- 每一步必须可独立测试和回滚。
- GitHub 交付必须通过独立分支和 Draft PR。
