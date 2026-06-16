# DeliverHQ

> AI 交付防翻车治理框架，作为 **Claude Agent Skill** 一行命令安装。

DeliverHQ 通过**可执行门禁**（信证据不信声明）把 AI 开发从"文档驱动"升级为"证据驱动"：
- **正向**：结构化规格 → SpecGate → 开发 → QualityGate（真跑 build/test/lint）→ ReviewGate（核对 git diff + traceability）
- **逆向**：老项目 `代码 → 需求文档`（客观风险分级 + 强制人工裁决）
- **Loop 可控**：目标契约（指标+不变量双轨防 Goodhart）、反钻空子检查（从 diff 取证）、重试上限（→ needs_human）

## 安装

```bash
# 装到当前项目（默认，交互选择位置）
npx deliverhq init

# 装到全局 ~/.claude/skills
npx deliverhq init --global

# 非交互（CI 友好）
npx deliverhq init --yes

# 验证健康度（检测 Python/PyYAML + 跑 selftest）
npx deliverhq doctor
```

安装后 skill 落在 `.claude/skills/deliverhq/`，重启 Claude Code 即可被自动发现（靠 SKILL.md frontmatter 的 description 触发）。

## 运行时要求

DeliverHQ 的门禁是 **Python 脚本**（不是 Node）。npx 只负责安装 + 环境检测，真正执行由 Claude 在对话里按需调用。需要：

- **Python 3.6+**
- **PyYAML**（`pip install PyYAML`）

`npx deliverhq doctor` 会检测这两项并运行 selftest（健康时输出"通过: N/N"）。

## 它不是什么

- 不是一个被 `npx` 持续运行的服务——npx 跑完即退，skill 文件留在磁盘供 Claude 读取。
- 不替代人工审查——high-risk 决策、reward-hacking 检出、重试耗尽都会交还人类（`needs_human`）。

## 文档（安装后在 skill 目录内）

- `SKILL.md` — 入口与"何时使用"
- `LEGACY-REVERSE-GUIDE.md` — 老项目逆向改造
- `LOOP-CONTROL-GUIDE.md` — 目标契约 / 防 Goodhart / 重试上限
- `CROSS-PLATFORM.md` — Windows/macOS/Linux 兼容说明
- `CAPABILITY-MATRIX.md` — 能力状态真相源（stable/experimental/roadmap）

## License

MIT
