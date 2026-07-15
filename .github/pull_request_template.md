## 背景

<!-- 为什么需要这个变更？对应哪个目标(正向链路/逆向链路/治理)？ -->

## 变更内容

<!-- 这个 PR 改了什么。建议 3-7 条要点。 -->

-
-
-

## 不包含的内容

<!-- 明确写出本 PR 不包含什么,避免范围蔓延。没有可写"无"。 -->

-

## 变更类型

- [ ] 新能力(scripts/ 下新增脚本或 gate)
- [ ] 治理规则调整(Gate 阈值、组合规则、不变式)
- [ ] 文档/能力矩阵
- [ ] 缺陷修复
- [ ] 重构(行为不变)

## 自测确认

- [ ] 本地 `cd skill && python scripts/selftest.py` **全绿**(粘贴 `通过: N/N` 行)
- [ ] 若动了 Gate 数量/组合:同步更新了 `gate_composition_check.py` 的 FROZEN_GATES / ALLOWED_GATE_EDGES
- [ ] 若新增脚本:在 `CAPABILITY-MATRIX.md` 登记,并加了对应 selftest 契约(正反例)
- [ ] 若改了入口链文档(AGENTS/SKILL/CLAUDE/dir-graph/CONTEXT/MEMORY/REPO_MAP):`python scripts/token_budget.py` 仍在预算内
- [ ] 改版本时:`VERSION.yml` / `package.json` / `README` / `CHANGELOG` 一并 bump(version_consistency 契约)

## 测试证据

<!-- 粘贴 selftest 的总结行,例如:通过: 34/34 -->

```
通过: __/__
```

## 风险与回滚

<!-- 低风险可写"低风险, revert 即可"；大变更需写具体风险和回滚路径。 -->

- 风险点：
- 回滚：
