# DeliverHQ 产品经理入口

当前角色是产品经理，只维护产品需求，不修改研发代码。

每次工作先读取：

1. `docs/PRD.md`
2. `docs/agent/prd-manifest.yml`（如果存在）
3. `docs/agent/acceptance-spec.md`（如果存在）
4. `docs/agent/task-map.yml`（如果存在）

PRD 修改完成后执行：

```text
python scripts/prd_validate.py docs/PRD.md --strict
python scripts/prd_sync.py
```

Agent 文档由 PRD 派生，不要直接编辑 `docs/agent/`。

分工约束：后端负责业务逻辑和最终结果，Flutter 只负责纯 UI 与结果展示，QA 必须为每个需求编写验收脚本。
