# DeliverHQ

> AI 交付防翻车治理框架，作为 **Agent Skill** 一行命令安装到 Claude Code / Hermes / Codex / Gemini 等。

DeliverHQ 通过**可执行门禁**（信证据不信声明）把 AI 开发从"文档驱动"升级为"证据驱动"：
- **正向**：结构化规格 → SpecGate → 开发 → QualityGate（真跑 build/test/lint）→ ReviewGate（核对 git diff + traceability）
- **逆向**：老项目 `代码 → 需求文档`（客观风险分级 + 强制人工裁决）
- **Loop 可控**：目标契约（指标+不变量双轨防 Goodhart）、反钻空子检查（从 diff 取证）、重试上限（→ needs_human）

## 安装（支持多 Agent）

DeliverHQ 核心是 **agent 无关**的 Python 门禁脚本。`init` 按目标 agent 把核心放到对应位置并生成入口：

```bash
# Claude Code（默认）→ .claude/skills/deliverhq/
npx deliverhq init

# Hermes → ~/.hermes/skills/deliverhq/
npx deliverhq init --target hermes --global

# Codex → .deliverhq/ + 向 AGENTS.md 注入指针
npx deliverhq init --target codex

# Gemini → .deliverhq/ + 向 GEMINI.md 注入指针
npx deliverhq init --target gemini

# 任意其它 agent → .deliverhq/ + 生成 DELIVERHQ.md 指针
npx deliverhq init --target generic

# 验证健康度（检测 Python/PyYAML + 跑 selftest）
npx deliverhq doctor

# 轻入口：先判断 quick / standard / strict / legacy
npx deliverhq route "refactor payment callback" --json

# 统一只读入口：结合项目中的活跃 CR、下一阶段和工件完整性给出具体命令
npx deliverhq go "继续当前任务" --path . --json
```

### 老项目首次入场

先做只读 Bootstrap。它复用 DeliverHQ 现有 Legacy Scan，发现 AGENTS/CLAUDE/架构文档、技术栈、项目命令和既有抽象；每条 confirmed 发现都带路径与 SHA-256 证据。

```bash
# 默认 report-only，不写宿主仓库
npx deliverhq bootstrap --path . --json

# 人工审查后生成 DeliverHQ/*.candidate 文件；绝不覆盖已有人工文件
npx deliverhq bootstrap --path . --apply
```

`route --json` 只做请求分流；`go --json` 进一步读取项目内 `DeliverHQ/change-requests/`，返回活跃 CR、目标阶段、工件预检和可执行的下一条命令。`go` 默认只读；多个活跃 CR 或需要人工审批时不会擅自推进。

`route --json` 同时返回推荐 lane、required/skipped Gates、时间与 token 区间、估算因素和置信度。估算是可解释区间，不是假装精确的账单。

| target | 落位 | 入口机制 |
|--------|------|---------|
| `claude` | `.claude/skills/deliverhq/` | SKILL.md frontmatter 自动发现 |
| `hermes` | `~/.hermes/skills/deliverhq/` | SKILL.md frontmatter 自动发现 |
| `codex` | `.deliverhq/` | 向 `AGENTS.md` 注入指针段（幂等，保留原有内容） |
| `gemini` | `.deliverhq/` | 向 `GEMINI.md` 注入指针段 |
| `generic` | `.deliverhq/` | 生成 `DELIVERHQ.md`，让任意 agent 读取 |

**两类机制**：带 skills 目录的 agent（Claude/Hermes）直接放整套文件夹，靠 frontmatter 发现；扁平指令文件的 agent（Codex/Gemini/其它）把核心放 `.deliverhq/`，再往它的指令文件注入一段"治理框架在哪、何时读"的指针。

`--global`/`--local` 仅对文件夹型有效；指针注入是幂等的（重装只更新那一段，不重复、不破坏你已有内容）。

## 运行时要求

DeliverHQ 的门禁是 **Python 脚本**（不是 Node）。npx 只负责安装 + 环境检测，真正执行由 agent 在对话里按需调用。需要：

- **Python 3.10+**
- **PyYAML**（`pip install PyYAML`）

`npx deliverhq doctor` 会检测这两项并运行 selftest（健康时输出"通过: N/N"）。

## 它不是什么

- 不是一个被 `npx` 持续运行的服务——npx 跑完即退，核心文件留在磁盘供 agent 读取。
- 不绑定某一个 agent——核心 agent 无关，只有"入口适配层"按 target 不同。
- 不替代人工审查——high-risk 决策、reward-hacking 检出、重试耗尽都会交还人类（`needs_human`）。

## 文档（安装后在核心目录内）

- `SKILL.md` — 入口与"何时使用"
- `AGENTS.md` — Agent 行为规则与门禁链
- `LEGACY-REVERSE-GUIDE.md` — 老项目逆向改造
- `LOOP-CONTROL-GUIDE.md` — 目标契约 / 防 Goodhart / 重试上限
- `CROSS-PLATFORM.md` — Windows/macOS/Linux 兼容说明
- `CAPABILITY-MATRIX.md` — 能力状态真相源（stable/experimental/roadmap）

## License

MIT
