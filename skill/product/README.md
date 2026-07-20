# DeliverHQ 产品经理版

安装时建议显式指定需求/项目目录：

```text
npx deliverhq product --path D:\Code\YourProject
```

未传 `--path` 时，安装器会提示确认当前目录，避免把 `.deliverhq/` 创建到错误位置。

## 在 Codex 里的常用口令

把原型、截图、需求背景发给 Codex 后，可以直接说：

```text
请按 DeliverHQ PRD 标准，帮我把这个原型/需求整理成 PRD，并写入 .deliverhq/docs/PRD.md。

要求：
1. 业务逻辑尽量放后端，Flutter 只做纯 UI 和结果展示
2. 每个需求必须包含可测试的验收条件
3. 每个需求必须拆出研发交付任务，QA 必须写验收测试脚本
4. 如果信息不完整，请列出待澄清问题，不要自行脑补
```

如果已经有一份老 PRD，可以直接说：

```text
请按 DeliverHQ PRD 标准，把这份老 PRD 标准化改造成新的 PRD，并写入 .deliverhq/docs/PRD.md。

要求：
1. 保留老 PRD 中已经明确的业务事实、范围、规则和验收要求
2. 不要自行脑补缺失信息，缺失内容放到待澄清问题
3. 为每个需求补齐稳定的 REQ/AC ID
4. 验收条件用可测试的 Given/When/Then 表达
5. 按团队分工拆任务：后端承载业务逻辑，Flutter 只做纯 UI 和结果展示，QA 必须写验收测试脚本
```

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
