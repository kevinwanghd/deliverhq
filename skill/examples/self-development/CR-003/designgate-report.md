# DesignGate Report: CR-003

> DesignGate 检查报告。验证设计产物完备性。C 端 UI 必须高保真，B 端 UI 可低保真通过。

## Verdict
**PASS** / **BLOCKED** / **N/A** (无 UI)

## Checked

### UI 类型判定
- UI 类型：**C 端** / **B 端** / **无 UI**
- 判定依据：{{从 acceptance-spec / request 中识别}}

### C 端 UI 检查（blocking: true）
- [x] / [ ] 存在 `design/hi-fi-spec.md`
- [x] / [ ] 包含高保真设计稿（主界面 + 关键状态）
- [x] / [ ] 视觉规范完整（色彩/字体/间距）
- [x] / [ ] 交互细节定义（状态/动画）
- [x] / [ ] 可交互原型或等效产物（`design/prototype.html`）
- [x] / [ ] 设计资源已交付（Figma 链接 / 切图）

### B 端 UI 检查（override_allowed: true）
- [x] / [ ] 存在 `design/lo-fi-spec.md` 或 `design/hi-fi-spec.md`
- [x] / [ ] 页面结构清晰（布局图/线框图）
- [x] / [ ] 交互流程完整
- [x] / [ ] 字段清单明确

## Blockers

{{如 Verdict = BLOCKED}}

| # | 阻断项 | 说明 |
|---|---|---|
| 1 | {{如：C 端 UI 缺少高保真设计稿}} | `design/hi-fi-spec.md` 不存在或内容不完整 |
| 2 | {{如：设计稿未交付}} | Figma 链接失效或无切图资源 |

## Warnings

{{如 PASS 但有警告}}

| # | 警告 | 说明 |
|---|---|---|
| 1 | {{如：B 端仅低保真}} | 建议补充高保真以提升开发还原度 |

## Evidence

### 检查的文件
- `change-requests/CR-{{ID}}/design/lo-fi-spec.md`
- `change-requests/CR-{{ID}}/design/hi-fi-spec.md`
- `change-requests/CR-{{ID}}/design/prototype.html`
- `change-requests/CR-{{ID}}/design/assets/`

### 扫描结果
- UI 类型：{{C 端 / B 端 / 无 UI}}
- 设计文档数：{{N}}
- 设计稿数量：{{M}} 张
- 可交互原型：{{存在 / 缺失}}

### 设计资源清单
```bash
ls design/assets/  # 切图/图标资源
{{screen-main.png}}
{{screen-interaction.png}}
{{icon-*.svg}}
```

## Override Request (仅 B 端)

{{如 B 端 UI 仅低保真，请求 override}}

**Override 理由**：
- 内部管理后台，视觉要求不高
- 开发资源有限，优先功能实现
- 可在后续迭代补充高保真

**Override 批准**：待人工审批

## Next Actions

### 如 PASS
✅ 放行进入 Context 阶段

### 如 BLOCKED
❌ 反馈给 Design Agent：
- [ ] 补充高保真设计稿（C 端）
- [ ] 补充可交互原型
- [ ] 交付设计资源（Figma 链接 + 切图）
- [ ] 重新提交 DesignGate

### 如 N/A
➡️ 跳过 DesignGate，直接进入 Context 阶段（纯后端无 UI）

## Gate 执行日志
- 执行时间：{{timestamp}}
- 执行者：DesignGate Skill
- 检查脚本：`scripts/designgate.py`
- 配置：`dir-graph.yaml > design_gate`
