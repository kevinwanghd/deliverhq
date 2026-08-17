# Red Lines By Stage — 分阶段红线

> 来源：企业微信团队"AI代码生成率94%"经验
> 按阶段加载，违反污染工程规范

## 阶段与红线映射

| 阶段 | 红线 ID | 标题 |
|------|----------|------|
| breakdown | RL-S04 | 禁止遗漏设计稿 |
| breakdown | RL-S06 | 禁止 LLM 手工分桶 |
| breakdown | RL-S08 | 设计稿筛选必须用脚本 |
| implement | RL-S01 | UI 改动必须比对语义桥 |
| implement | RL-S02 | 禁止语义联想扩大范围 |
| verify | RL-S05 | 视觉对齐必须逐项核对 |
| simulator | RL-S07 | 阶段内重试不超过 2 轮 |
| commit | RL-S03 | 跨会话知识必须沉淀 |

## 文件列表

- `breakdown.md` — 需求拆解阶段红线
- `implement.md` — 实现阶段红线
- `verify.md` — 验证阶段红线
- `simulator.md` — 模拟器验证阶段红线
- `commit.md` — 提交阶段红线
