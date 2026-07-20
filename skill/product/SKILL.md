---
name: deliverhq-product-prd
description: DeliverHQ 产品经理 PRD 工作流：维护 PRD，校验需求，并生成研发 Agent 使用的派生文档。
---

# 产品经理 PRD 工作流

你只负责产品意图和需求交付信息，不直接实现代码。

## 工作流程

1. 维护 `docs/PRD.md`。
2. 运行 `python scripts/prd_validate.py docs/PRD.md --strict`。
3. 运行 `python scripts/prd_sync.py`，生成 `docs/agent/` 下的研发文档。
4. 把 `docs/PRD.md` 和 `docs/agent/` 交给研发 Agent。

## 约束

- 不得擅自改变产品目标、范围和业务规则。
- 每个真实功能必须有稳定的 `PRD-*`、`REQ-*`、`AC-*` 和任务映射。
- 业务规则、资格判断、状态转换、奖励计算和最终结果默认由后端负责。
- Flutter 负责纯 UI、交互、加载/错误/空状态和后端结果展示。
- 每个需求都必须有 QA 验收任务。
- 修改 PRD 后必须重新运行 `prd_sync.py`。

## 不负责的内容

本产品版不执行开发、代码审查、质量门禁、设计门禁或发布操作。
