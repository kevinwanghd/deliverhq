# CR-TEMPLATE 使用指南

本目录是 Change Request (CR) 的完整模板，包含从需求输入到交付归档的全部文档。

## 快速开始（推荐）

使用初始化脚本自动创建新 CR：

```bash
cd DeliverHQ
python scripts/init_cr.py CR-001 "实现用户登录功能" "产品经理"
```

脚本会自动：
1. 复制 `CR-TEMPLATE` → `CR-001`
2. 替换所有模板变量（`CR-002`、`实现 worktree 隔离机制` 等）
3. 填充当前日期和提出人

## 手动创建（不推荐）

```bash
cd DeliverHQ/change-requests
cp -r CR-TEMPLATE CR-001
cd CR-001

# 手动替换变量（容易遗漏）
find . -type f -exec sed -i 's/CR-002/CR-001/g' {} \;
find . -type f -exec sed -i 's/实现 worktree 隔离机制/实现用户登录功能/g' {} \;
find . -type f -exec sed -i 's/2026-06-13/2026-06-11/g' {} \;
```

## 文件清单（20 个）

### 需求与规格（Spec Agent）
- `request.md` — 需求输入（产品经理填写）
- `acceptance-spec.md` — 验收规格（Spec Agent 生成）

### 设计（Design Agent）
- `design/lo-fi-spec.md` — B 端低保真设计
- `design/hi-fi-spec.md` — C 端高保真设计
- `design/prototype.html` — 可交互原型
- `design/design-decisions.md` — 设计决策记录
- `design/assets/` — 设计稿图片目录

### 开发与测试（Dev/Test Agent）
- `context-summary.md` — 上下文摘要（滑动窗口）
- `implementation-plan.md` — 实施计划
- `test-plan.md` — 测试计划

### 质量与归档（Quality/Writeback Agent）
- `quality-report.md` — 质量检查报告
- `writeback-report.md` — 交付归档报告

### 决策与追溯
- `human-decisions.md` — 人工决策记录
- `traceability.yml` — 需求到代码映射
- `exceptions.yml` — 规则豁免记录

### Gate 报告（5 个门禁）
- `specgate-report.md` — SpecGate 检查结果
- `designgate-report.md` — DesignGate 检查结果
- `context-window-report.md` — ContextWindowGate 检查结果
- `qualitygate-report.md` — QualityGate 检查结果
- `writeback-gate-report.md` — WritebackGate 检查结果

## 工作流程

```
1. 填写 request.md（需求方）
   ↓
2. Spec Agent 生成 acceptance-spec.md
   ↓
3. 运行 SpecGate 检查
   python ../../scripts/specgate.py acceptance-spec.md
   ↓
4. (如有 UI) Design Agent 生成设计稿
   ↓
5. 运行 DesignGate 检查
   python ../../scripts/designgate.py .
   ↓
6. Context Agent 生成 context-summary.md
   ↓
7. Dev Agent 实现代码 + 生成 implementation-plan.md
   ↓
8. Test Agent 编写测试 + 生成 test-plan.md
   ↓
9. Quality Agent 检查 + 生成 quality-report.md
   ↓
10. 运行 QualityGate 检查
    python ../../scripts/qualitygate.py .
   ↓
11. Writeback Agent 归档 + 生成 writeback-report.md
   ↓
12. 运行 WritebackGate 检查
    python ../../scripts/writeback_gate.py .
   ↓
13. 交付完成，移动到 delivery/YYYY-MM/CR-XXX/
```

## 模板变量说明

| 变量 | 说明 | 示例 |
|---|---|---|
| `CR-002` | CR 编号 | CR-001 |
| `实现 worktree 隔离机制` | CR 名称 | 实现用户登录功能 |
| `2026-06-13` | 日期 | 2026-06-11 |
| `Kiro AI` | 提出人 | 产品经理 |

使用 `init_cr.py` 会自动替换这些变量。

## 注意事项

- ⚠️ 不要直接修改 `CR-TEMPLATE`，它是模板本身
- ✅ 从 `CR-TEMPLATE` 复制出新 CR 再修改
- ✅ 使用 `init_cr.py` 避免手动替换变量出错
- ✅ 运行 `pre_dev_gate.py` 确保文档完备后再开发
