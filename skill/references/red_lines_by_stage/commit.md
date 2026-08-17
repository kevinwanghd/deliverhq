# 提交阶段红线（commit）

> 加载时机：进入「提交」阶段时
> 违反后果：知识无法跨会话传承，AI 重复踩坑

---

## RL-S03：跨会话知识必须沉淀

### 规则

> 每次需求开发后必须更新 TECH_SPEC.md

### TECH_SPEC.md 位置

- `docs/knowledge-base/TECH_SPEC.md`
- 或 CR 目录内的 `tech-spec.md`

### TECH_SPEC.md 章节结构

```
§0  AI 自检清单      ← 给下次会话的 AI 当"入场扫描"
§1  功能边界        ← 哪些做、哪些不做（防越界）
§3  模块地图        ← 文件 + 关键方法 + 调用链
§5  不变式          ← 不能动的命名、文件清单、拦截边界
§7  演进事件        ← 按时间线排列的 BUG-N / ITER-N / REV-N
§8  产物清单        ← 每次 commit 改了什么
§9  版本号          ← v1.0 → v1.1 → ... → v2.0 (baseline 合并)
```

### 沉淀时机

| 场景 | 是否需要沉淀 |
|------|-------------|
| 首次实现新功能 | ✅ 必须 |
| 迭代升级现有功能 | ✅ 必须 |
| Bug 修复 | ✅ 必须 |
| 代码重构（改变调用链）| ✅ 必须 |
| 纯代码格式化 | ❌ 可选 |

### 禁止行为

- 开发完成后直接 commit，没有更新 TECH_SPEC.md
- 遗漏关键调用链信息
- 用模糊描述代替具体文件路径

### 正确示例

```markdown
## §7 演进事件

### ITER-001 (2026-08-16)
**功能**：邮件列表顶部小红条提示

**新增文件**：
- `App/Mailbox/MList/View/XYZTipsView.mm`
- `App/Mailbox/MList/Controller/XYZMListController.mm` (修改)

**调用链**：
```
用户点击 → XYZMListController → XYZTipsView → showWarningTips:
```

**不变式**：
- TipsView 高度固定 44pt
- 颜色使用 base_gray_100
```

### 触发报告模板

```markdown
⛔ 触发红线 RL-S03：跨会话知识必须沉淀

当前情形：
- 是否有 TECH_SPEC.md 更新记录：{has_update}
- 是否有调用链信息：{has_call_chain}
- 是否有产物清单：{has_artifacts}

建议处理：
1. 运行 tech_spec_manager.py 追加本次演进
2. 确认 §7 演进事件已记录
3. 确认 §8 产物清单已更新
4. 确认有 HK-2 人工确认
```
