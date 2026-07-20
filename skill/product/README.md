# DeliverHQ 产品经理版

产品经理只需要维护 `docs/PRD.md`，然后运行：

```text
python scripts/prd_validate.py docs/PRD.md --strict
python scripts/prd_sync.py
```

同步结果位于 `docs/agent/`：

- `prd-manifest.yml`：需求与版本信息
- `task-map.yml`：按 PRD 任务映射生成的研发任务
- `acceptance-spec.md`：包含验收条件正文和职责约束
- `change-report.md`：本次 PRD 变更摘要

产品版只负责需求整理和研发交接，不执行开发、评审、测试门禁或发布。
