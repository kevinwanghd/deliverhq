# Red Lines — 红线体系

> 来源：企业微信团队"AI代码生成率94%"经验

## 目录结构

```
red_lines/
├── red_lines.yaml          # 单一真源（YAML DSL）
├── red_lines_critical.md   # Critical 红线（全局强制加载）
└── ../red_lines_by_stage/ # 分阶段红线
```

## 红线分类

### Critical（6条）- 全局强制

| ID | 标题 | enforcement |
|----|------|-------------|
| RL-C01 | 编译必须通过 | fail_closed |
| RL-C02 | 未按阶段执行 | fail_closed |
| RL-C03 | 先看后写 | fail_closed |
| RL-C04 | 先模仿后发明 | fail_closed |
| RL-C05 | 禁止修改受保护路径 | fail_closed |
| RL-C06 | git commit 必须同步执行 | fail_closed |

### Standard（8条）- 按阶段加载

| ID | 标题 | phase |
|----|------|-------|
| RL-S01 | UI 改动必须比对语义桥 | implement |
| RL-S02 | 禁止语义联想扩大范围 | implement |
| RL-S03 | 跨会话知识必须沉淀 | commit |
| RL-S04 | 禁止遗漏设计稿 | breakdown |
| RL-S05 | 视觉对齐必须逐项核对 | verify |
| RL-S06 | 禁止 LLM 手工分桶 | breakdown |
| RL-S07 | 阶段内重试不超过 2 轮 | simulator |
| RL-S08 | 设计稿筛选必须用脚本 | breakdown |

## 使用方式

### AI 启动时

加载 `red_lines_critical.md`，牢记 6 条 Critical 红线。

### 进入特定阶段时

加载 `../red_lines_by_stage/{phase}.md`，了解该阶段的 Standard 红线。

### 触发红线时

使用 `red_lines_critical.md` 中的报告模板，格式化为：

```markdown
⛔ 触发红线 RL-XX：<标题>

当前情形：<具体说明>

建议处理：<回退到哪个步骤 / 需要用户确认什么>
```
