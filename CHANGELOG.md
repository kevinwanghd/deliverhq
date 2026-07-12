# Changelog

本文件记录 **npm 包 `deliverhq`（安装器）** 的版本变化。
DeliverHQ 框架本身的版本见 `skill/VERSION.yml`（与安装器版本独立）。

版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## [5.17.0] - 2026-07-12

### 产品化发布与能力元数据

- 新增 `skill/capabilities.yml` 作为能力清单的机器可读单一事实源，并由 `scripts/capability_registry.py check|render` 校验/生成 `CAPABILITY-MATRIX.md`。
- `scripts/capability_tiers.py` 改为读取 YAML registry，不再解析 Markdown 表格，保留原公开函数入口。
- 新增 `skill/deliverhq/` Python package，迁入 runtime/routing 实现，旧 `scripts/execution_runtime.py` 与 `scripts/orchestrator_routing.py` 保持兼容 wrapper。
- 新增 npm pack 预算测试，发布包排除活动 CR、内部归档、运行期目录和历史优化材料；dry-run 包体降至 227 文件、约 1.20 MB 解压体积。

## [5.16.0] - 2026-07-11

### 模块化运行时

- 新增 `execution_runtime.py`，统一 Gate wrapper 与 orchestrator 的无 shell 脚本执行、UTF-8 解码、超时和结构化结果。
- 将 orchestrator 拆为薄兼容入口、编排 core 和独立路由/成本模块，保留原 CLI 与导入接口。
- 将 selftest 改为薄兼容入口，37 项契约按 core/workflow/governance 三域注册并由内部 suite 执行。
- 新增运行时成功、非零退出、超时、环境合并、依赖方向和薄入口结构测试。
- 修正 selftest 对旧文件布局的隐式依赖，保持最终汇总 `通过: 37/37`。

## [5.15.4] - 2026-07-11

### 入口可靠性与跨平台验证

- 修复 `gate_wrapper.py predev` 指向不存在的 `predev_gate.py`，改为真实入口 `pre_dev_gate.py`。
- 新增 Gate 映射、Node CLI 和默认命令配置的入口回归测试。
- `COMMANDS.yml` 及项目初始化模板默认使用 `enabled: false` / `command: null`，避免占位命令产生假成功。
- CI 扩展为 Ubuntu/Windows 与 Python 3.10/3.13 矩阵，并验证 CLI 语法和 npm 打包内容。
- 修复 Windows 非 UTF-8 locale 下 selftest 子进程解码和 token budget 控制台输出失败。
- 新增根目录 `AGENTS.md`，让 Codex 与 Claude Code 共用 `skill/AGENTS.md` 约束源，并强制 GitHub PR 工作流。

## [5.15.3] - 2026-07-01

### 全代码审计修复（多智能体 workflow 审计 59 个脚本，确认11个真 bug）

用多智能体 workflow 对全部 59 个 Python 脚本做深度审计（10组并行审计 + 每个 bug 独立对抗式验证），确认 11 个真 bug、驳回 19 个误报。这些 bug selftest 全绿也没抓到——因为契约测试只测"结构不漂移"，不测代码逻辑正确性。

**HIGH（7个）**
- `skill_orchestrator.py` `_has_gate_cache()`：遍历 gate_modules 却忽略 gm 变量，任何 gate 有 fingerprint 就误判当前 verb 缓存已启用。修复：加 `_norm()` 归一化匹配（specgate↔spec、pre_dev_gate↔predev），只查匹配当前 gm 的 key。
- `skill_orchestrator.py` execute_skill：subprocess.run 缺 timeout，Gate 挂起会无限等待。修复：加 timeout + TimeoutExpired 捕获。
- `scan_legacy.py` L165：`str(file_path)` 在 Windows 产生反斜杠导致 git log 失败。修复：改用 `as_posix()`。
- `gate_wrapper.py`：subprocess.run 无 timeout。修复：timeout=300 + 超时使下游缓存失效。
- `memory_store.py` `_load_index()`：index.json 损坏时 JSONDecodeError 未捕获导致崩溃。修复：try-except 降级为空 store。
- `structuregate.py` L114/L120：`name in legacy_paths` 因尾斜杠永远 False，progressive 模式遗留目录标记失效。修复：改用 `_under_legacy_path()`。
- `baseline_comparison.py` L152：coverage 正则 `(\d+)%` 匹配任意百分比，"15% improvement" 会被误当覆盖率。修复：加 coverage 上下文限定 + TOTAL 行兜底。

**MEDIUM（4个）**
- `selftest.py` L502：`split("|", 2)` 不足3段时 unpacking ValueError。修复：加 `len(parts) < 3` 防御。
- `scan_legacy_structure.py` L13：yaml 导入无 try/except。修复：ImportError 友好提示 + sys.exit(2)。
- `scan_legacy_structure.py` main()：project_root 无有效性检查，路径不存在时 iterdir 崩溃。修复：加 exists/is_dir 检查。
- `update_mistake_book.py` L147：failure_reason 无条件加 "..."，短原因被误加省略号。修复：仅实际截断时加。
- `promote_rule_candidate.py` L149：replace 无验证，block_text 找不到时静默跳过。修复：找不到时 raise ValueError。

---

## [5.15.2] - 2026-07-01

### Bug 修复（对 v5.15.0 P0 功能做 code review 发现的4个真实 bug）

根因：v5.15.0 三个 P0 功能照搬 flow-kit"一条8步链"心智模型，但 DeliverHQ 是
5个独立动词，架构不同。selftest 未抓到——因为契约测试只测"不漂移"，不测"新功能有效"。

#### Bug1 — 轻量模式空操作
**现象**：快速通道 chain `["pre_dev","context","dev"]` 与普通 dev 动词完全一样，"跳过 design/architecture" 是空话（design 是独立动词，本就不在 dev 链里）。  
**修复**：轻量模式改为在 dev 链内精简 `context`（小改动非必需），保留 pre_dev+dev；design 的跳过改为向用户建议（动词间选择）。附带修 `risky_keywords` 大小写 bug（"API" 在 `content.lower()` 里永远匹配不到）。

#### Bug2 — 成本预估缓存检测路径错
**现象**：检测 `evidence/.gate-cache` 文件，但 gate_cache 实际存 `state.yml` 的 `gates:` 字段，该文件永不存在 →"Gate 缓存已启用"提示永不触发。  
**修复**：新增 `_has_gate_cache()` 读 `state.yml` 的 `gates:` fingerprint 判断。

#### Bug3 — 首次入场扫描调错脚本
**现象**：调用 `scan_legacy.py --project-root`（该参数不存在，一触发就报错）；且 scan_legacy 产物是逆向需求候选，不是 CONTEXT.md。  
**修复**：CONTEXT.md 是"AI 分析代码后填写的上下文"，改为生成待填模板 + 引导 AI 填充，不再错误调用 scan_legacy。

#### Bug4 — 向后兼容没做到
**现象**：v5.15.1 号称兼容旧模板，但仍强制要求"测试接缝"节；旧模板没这节 → 旧 CR 仍被 BLOCK。  
**修复**：设计分块是核心章节必须有（##5/##6 都接受）；测试接缝是 5.14+ 新增，旧模板缺失降级为 warning 不 block。

#### 附带修复 — 非交互环境阻塞
`_check_first_time_setup` 和 `should_use_fast_lane` 的 `input()` 在 CI/管道会阻塞。加 `sys.stdin.isatty()` + `DELIVERHQ_NON_INTERACTIVE` 检测，非交互环境静默跳过。

---

## [5.15.1] - 2026-06-30

### Bug 修复（v5.15.0 验证报告的3个残余问题）

基于用户对 CR-001 的实测验证报告，修复三个残余问题：

#### 残余问题1：selftest.py 编码未覆盖（Bug1不彻底）
**问题**：SUBPROCESS_ENV 只在 skill_orchestrator.execute_skill 注入，selftest.py 的 subprocess 调用未覆盖。  
**影响**：Windows 直接运行 `python selftest.py` 仍有 5 项 UnicodeDecodeError（31/36），需手动 `PYTHONUTF8=1`。  
**修复**：`selftest.py` 开头统一设置 `os.environ`（PYTHONUTF8/PYTHONIOENCODING/PYTHONDONTWRITEBYTECODE）。  
**预期**：Windows 下直接运行 selftest.py 达到 35/36（与手动设置环境变量一致）。

#### 残余问题2：designgate mobile_keywords 太宽泛（Bug6残余）
**问题**：'客户端'/'App' 在某些业务里指"SDK客户端/合作方App"，非移动端UI，却命中移动端判定（优先级最高）。  
**影响**：Admin 后台 CR 仍可能被误判为 C端/移动端。  
**修复**：
- `mobile_keywords` 移除 '客户端'/'App'/'APP'（太宽泛）
- `ASCII_TOKEN_RE` 移除 'App|APP'
- 保留明确的移动端词（'移动端'/'原生'/iOS/Android/Flutter等）
- 新增需要上下文的组合词（'手机App'/'移动端客户端'）

**预期**：Admin 后台不再被误判为移动端。

#### 残余问题3：architecturegate 章节号向后兼容（Bug5残余）
**问题**：旧模板（5.14前）##5是设计分块，新模板（5.14+）##5是测试接缝、##6是设计分块，章节号反转后用旧模板建的 CR 用新 gate 会被 BLOCK。  
**影响**：无迁移路径，用户需手动调整旧 CR 的章节号。  
**修复**：gate 同时接受新旧两种顺序
- 测试接缝：##5 或 ##6 有一个即可
- 设计分块：##5 或 ##6 有一个即可

**预期**：旧模板 CR 和新模板 CR 都能通过 gate。

**验证状态**：感谢用户的详细验证报告和残余问题反馈。

---

## [5.15.0] - 2026-06-30

### 新增功能（P0 优化）

#### P0-1: 首次入场扫描机制（老项目护栏 B1）
**功能**：`init_cr.py` 首次使用时检测 CONTEXT.md 不存在 → 停下来问要不要扫描既有代码。  
**收益**：
- 一次性投资 15-50k tokens 生成 CONTEXT.md（技术栈/命名风格/既有抽象/禁动清单）
- 后续所有 CR 读这个文件，避免重复实现/破坏既有抽象
- 老项目护栏从"可选"变成"默认"

#### P0-2: 轻量模式（快速通道）
**功能**：`skill_orchestrator.py` 新增快速通道判断，小改动跳过完整 Gate 链。  
**触发条件**：
- 用户显式指定 `--fast` 或 `state.yml` 里 `lane=fast`
- `request.md` 里有 `[fast-lane]` 标记
- 智能检测：<200字 + 无高风险关键词（架构/数据库/API/migration/重构）
**收益**：
- dev 动词跳过 design/architecture gate，保留 spec + pre_dev（最低安全网）
- token 节省 30-40%
- 小改动不再"大材小用"

#### P0-3: Token 成本预估（透明化决策）
**功能**：`skill_orchestrator.py` 新增 TOKEN_ESTIMATES 表和 print_cost_estimate()。  
**行为**：
- 动词执行前显示预估 token 消耗范围和费用（Sonnet 定价）
- Gate 缓存节省可视化（"已启用，预计节省 $2.5"）
**收益**：
- 用户对成本有预期，从"盲目执行"变成"知情决策"
- 有助于决定"要不要走完整流程"

**灵感来源**：借鉴自 flow-kit 的首次入场扫描、轻量模式、成本透明化机制。

---

## [5.14.0] - 2026-06-30

### Bug 修复（安装后发现的6个问题）

#### Bug 1 — Windows 编码 UnicodeDecodeError
**影响**：Windows 系统下子进程用 GBK 解码 UTF-8 输出，selftest 一堆 UnicodeDecodeError 误报。  
**修复**：`skill_orchestrator.py` 新增 `SUBPROCESS_ENV`（含 `PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8`），`execute_skill` 的 `subprocess.run` 传入 `env=SUBPROCESS_ENV`。

#### Bug 2 — cwd 依赖（非 skill 根目录执行即失败）
**影响**：`script_path` 用相对路径，`subprocess.run` 无 `cwd=`，只能从 `skill/` 目录执行，安装后使用时必炸。  
**修复**：`script_path` 改绝对路径（`ROOT / skill.script_path`），`subprocess.run` 加 `cwd=ROOT`。

#### Bug 3 — pre_dev_gate 路径硬拼
**影响**：`main()` 硬拼 `DELIVERHQ_ROOT/change-requests/cr_id`（安装目录），用户项目里的 CR 找不到。  
**修复**：`main()` 优先接受绝对路径或存在的相对路径，兜底才拼 `DELIVERHQ_ROOT`。

#### Bug 4 — specgate `[待确认]` 误报
**影响**：文档说明文字里的 `` `[待确认]` `` 被当作未解决占位符误报。  
**修复**：新增 `_strip_code_from_content()`，检测前剥离围栏代码块/内联代码/缩进代码。

#### Bug 5 — architecturegate 章节号不一致
**影响**：模板新增 `## 5. 测试接缝` 后，gate 仍检查旧 `## 5. 设计分块`，导致用新模板建的 CR 全部被 BLOCK。  
**修复**：gate 的 required 列表加入 `## 5. 测试接缝`，设计分块改为 `## 6`；同步更新 CR-EXAMPLE 和 selftest 临时模板。

#### Bug 6 — designgate Admin 后台误判为 C端
**影响**：Admin 后台 spec 里含 `UI`/`页面` 等泛用词，被 C端优先级判定误判为 C端（要求高保真）。  
**修复**：新增 B端强信号列表（`Admin`/`管理后台`/`管理系统`等），优先级高于泛用 C端词；`UI`/`页面` 从 C端判据移除。

### 复盘

6个 bug 未被测试抓到的根因（见 AGENTS.md Loop 可控性章节的"诚实边界"）：
1. 测试夹具是理想 CR，不含 Admin 内容/代码块示例/边界词
2. 单一平台 CI（Linux），不触发 Windows 编码问题
3. 固定 cwd 执行，不模拟安装后的真实调用场景
4. 模板/Gate 无自动一致性检查，改模板忘了改 Gate

改进已加入 references/gotchas.md。

## [5.13.0] - 2026-06-30

### 子 CR 拆解（Epic → Story 模式，解决"CR 太大上下文爆掉"问题）

**问题**: 大需求塞进单个 CR → 1400+ 行文件 → 上下文爆掉，Agent 无法有效工作。

**方案**: Epic → Story 拆解，子 CR 独立走完整 Gate 链，上下文天然隔离。

**命名规则**: 数字后缀（CR-001-01/02/03），无上限，排序自然。

#### 新增工具

- **`scripts/create_sub_cr.py`**:
  - 创建子 CR 目录（从 CR-TEMPLATE 继承）
  - 自动更新父 CR 的 sub-crs.yml
  - 支持依赖链（`--depends-on`）
  - 查看子 CR 列表（`--list`）和完成状态（`--status`）

- **`orchestrator decompose`**:
  - 分析 CR 规模（token 估算、验收条件数量）
  - 超阈值（criteria>10 或 tokens>5000）给出拆解建议
  - 输出具体的 create_sub_cr 命令示例

- **`CR-TEMPLATE/sub-crs.yml`**: Epic 子任务清单模板（条件工件，非骨架必需）

#### 典型用法

```bash
# 1. 分析 CR 是否需要拆解
python3 scripts/skill_orchestrator.py decompose change-requests/CR-001

# 2. 创建子 CR
python3 scripts/create_sub_cr.py CR-001 --title "OAuth 2.0 集成"
python3 scripts/create_sub_cr.py CR-001 --title "JWT token 管理" --depends-on CR-001-01

# 3. 每个子 CR 独立走完整流程
python3 scripts/skill_orchestrator.py verb spec change-requests/CR-001-01
python3 scripts/skill_orchestrator.py verb dev  change-requests/CR-001-01
# ...

# 4. 查看 Epic 进度
python3 scripts/create_sub_cr.py CR-001 --status
```

#### 设计原则

- Epic 只走轻量 spec（高层验收标准）
- 子 CR 独立走完整 Gate 链，上下文天然隔离
- Gate 缓存（5.12.0）在子 CR 内自动生效

## [5.12.0] - 2026-06-28

### grill：填 DeliverHQ 输入端对齐空洞（借 Matt Pocock grilling）

DeliverHQ 的门禁保证"给定 spec，交付质量可控"，但无法保证"给定模糊想法，spec 质量可控"。最常见的失败不是"没写 spec"，而是**"需求本身没想清楚"**——然后垃圾进、(合规的)垃圾出。SpecGate 只检查 spec 格式完备性（有没有占位符），不检查 spec 是否建立在模糊需求上。

**grill 填的正是这个空洞**：在生成 acceptance-spec **之前**逐条拷问用户，把模糊想法逼成清晰需求。借鉴 Matt Pocock 的 grilling 技能（结构化澄清），但产出工件化。

### 改动

- **新增 `grill.py`**：需求澄清拷问脚本，产出 `request-clarifications.md`（Q&A 格式）。
- **spec 链改为 `grill*(条件) → spec → drift_check`**：
  - `grill` 放链首，在生成 spec **之前**拷问。
  - **条件步**：仅当 CR 有 `request.md` 时才跑；缺失则**跳过而非失败**（不强制每个 CR 都拷问，保住 fast-lane）。
  - Spec Agent 消费 `request-clarifications.md` 生成更精准的 acceptance-spec。
- **CR-TEMPLATE 加 `request-clarifications.md` 占位符**（非必需骨架文件，因为是条件工件）。
- **设计纪律**（仿 Pocock）：一次一问、每问给推荐答案、能查代码就查不问人、产出留痕。

### 哲学对齐

Pocock 反对"重流程接管"，但 grill 的本质是**"把需求澄清变成显式、可审计的步骤"**——这恰好是 DeliverHQ "工件化 + 门禁化" 哲学的**前端延伸**。不是放松控制，而是**把控制前移**。

### selftest

- 35/36 全绿（qualitygate 契约检查失败是 5.11.0 分支遗留问题，非本次引入）。
- token 预算仍 10962/11000（grill 和 clarifications 不在入口链，无膨胀）。

## [5.11.0] - 2026-06-26

### verify 动词串入 loop 可控性（goal_contract 双轨 + retry_guard 只读出口）

把已有的 loop 可控性三件套接进日常动词链,让"反 Goodhart + 收敛出口"成为 `verify` 的默认行为,而非要手动记得跑的旁路脚本:

- **`verify` 链改为 `goal_contract*(条件) → review → quality → anti_gaming`**:
  - `goal_contract` 放链首,在信任 review/quality 的指标**之前**先校验"metrics + invariants"双轨(防"删测试让测试绿"这类 Goodhart)。
  - 它是**条件步**:仅当 CR 有 `goal-contract.yml` 时才跑,缺失则**跳过而非失败**——不强制每个 CR 写目标契约,保住 fast-lane。
- **失败后只跑 `retry_guard` 只读 status**:展示重试收敛状态,但**绝不自动 record**——record 需人/Agent 给新假设(达上限转 needs_human)。守住"重试需人介入"的纪律。
- 不破坏既有契约:`goal_contract` 是非门禁辅助步(不进 FROZEN_GATES);动词集合仍是 5 个;`get_default_pipeline()` 未动。

### selftest
- `verb_layer_contract` 加固:断言 verify 链含 `goal_contract` + `anti_gaming`、且失败后只读 status 不自动 record。36/36 全绿。

## [5.10.0] - 2026-06-24

### 用户面动词收口（借鉴 OpenMole 的克制，不削门禁内核）

把"直面 54 个脚本"的认知负荷收口为 **5 个用户面动词**，兑现 `skill_orchestrator.py` 早已声明的
"thin harness orchestrates fat skills"——只动人机接口，不动 fail-closed 证据门禁机制：

- **5 个动词**：`spec`（specgate→drift_check）/ `design`（designgate→architecturegate）/
  `dev`（pre_dev→context→交接，停在写码前）/ `verify`（review→quality→反钻空子）/
  `archive`（writeback→规则成熟度）。用法 `skill_orchestrator.py verb <动词> <CR>`，`verbs` 列出链路。
- **派生自单一事实源**：动词的「门禁 step」从 `FROZEN_GATES` 派生，新增 `validate-verbs` 做机器校验——
  既不漂移、也不漏掉任何冻结门禁；非门禁辅助步骤显式登记，standalone 门禁文档化不丢失。
- **不反噬可观测性**：动词是**默认入口非唯一入口**（脚本仍可单独调用）；任一步 BLOCK 即停并
  **透传该脚本 verbatim 报告**（不二次概括）；修复 `execute_skill` 失败分支吞掉 stdout 的旧问题。
- **守住既有契约**：不触碰 `get_default_pipeline()`（自动链仍停在 dev handoff）；`verify` 失败不自动
  跑 retry_guard（重试需人给新假设）。

### selftest
- 新增契约 `verb_layer_contract`：真实执行 `validate_verbs()`，锁死动词集合 = {spec,design,dev,verify,archive}、
  动词↔FROZEN_GATES 一致、失败分支透传 stdout。现 34/36（另 2 项为既有失败，与本次无关）。

## [5.9.0] - 2026-06-23

### 治理债止血 + 借鉴 5 框架（Pocock / GSD / BMAD / Superpowers / Spec-Kit）

借鉴对照研究后落地一批"减债 + 加固差异化"的改动，全程不稀释 fail-closed 证据门禁内核：

**P0（止血地基）**
- **砍 Python 3.6 → 3.10+**：移除 6 处 `yaml.safe_dump(sort_keys=)` 的 try/except 3.6 回退（死代码）及版本声明（CHANGELOG/示例历史保留）。无框架背 3.6，是自加负担。
- **GSD 统一不变式**：AGENTS/SKILL 顶部引入 `done = 建出来的 = 计划的 = 决定的`，作为串起 PRD→spec→Review→Quality 的总判据。
- **plan_checker 加 GSD 写作约束**：`<verify>` 必须能判 pass/fail（拒 echo/print no-op）、`done`/`verify` 禁主观语言（looks correct）、`goal`/`action` 不内嵌大段代码。
- **SpecGate 加 `[NEEDS CLARIFICATION]`=0**（借 Spec-Kit）：起草期可标，放行前必须清零，与 `[TODO]` 同级阻断。
- **Gate 冻结 + 组合规则**：新增 `gate_composition_check.py`，冻结 11 道 Gate 基线（`FROZEN_GATES`），禁 Gate 套 Gate（白名单仅 `pre_dev_gate → permissiongate`），遏制版本版加 Gate 的治理债（借 Pocock 组合纪律）。

**P1（入口减负 + 砍膨胀）**
- **能力双轴分层**：新增 `capability_tiers.py`，能力按 `default_enabled` 派生 core（常驻）/on-demand（按需，零 per-turn 成本），core 有界（借 Pocock 双轴模型）。
- **砍 3 个化石能力**：`loop_mode.py`/`darwin_score.py`/`quality_ratchet.py` 移至 `_archived/`（与人在环、证据驱动、对抗式验证哲学冲突，且后两者是硬编码 stub），能力矩阵 46→43。
- **客观规模分档**：新增 `lane_advisor.py`，按 changed_files/ac_count/敏感域给 lane 建议（fast/standard/high-risk）或建议拆 CR（GSD 客观阈值 + BMAD Quick Flow）；`pre_dev_gate --suggest-lane` 调用，是 flag 非新命令。
- **SKILL.md progressive-disclosure 重构**（借 Pocock 阶梯）：314→约 230 行，10 gotchas/4 模式下沉到 `references/`，入口只留 step-tier。
- **入口链 token 预算**：新增 `token_budget.py`，度量每轮常驻入口链 token 并设上界（≤11000），把 token 经济变成可阻断指标。

### selftest
- 新增契约：`needs_clarification_contract` / `gate_composition_contract` / `capability_tiers_contract` / `lane_advisor_contract` / `token_budget_contract`。现 31/31；Python 3.10+。

## [5.8.0] - 2026-06-21

### 新增（前端/移动端证据驱动闭环 / 通用工程内核 + RN/Figma 可选适配）
- **架构确认门禁（第二道人工门禁）**：新增 `architecturegate.py` + `architecture-design.md`（模块拆分/数据流/接口/异常/设计分块到实现映射/直读计划）；接入 AGENTS 阶段链（Spec→Architecture→ArchitectureGate→Context→Dev）。
- **证据驱动编码 + 架构对齐报告**：新增 `architecture-alignment-report.md`；Dev Agent 按架构设计实施，缺证据/缺落点 block 而非硬写，missing 最多回流补全 5 轮。
- **直读审计 direct-read-audit**：新增模板（四元组 node_id→属性→原始值→代码映射）；UI 编码前产出，截图仅校准；designgate 在 C 端 warning-first 检查。
- **视觉还原审计 visual-auditor**：新增 `visual-audit-report.md`；编译通过≠还原正确，偏差清单回流 code-generator 修复。
- **移动端高保真门禁强化**：`designgate.py` 识别 Android/iOS/Flutter/RN/鸿蒙/小程序 → 强制 C 端高保真（含"后台"也不降级）；专项校验平台规范/多机型/深色模式/交互状态；`dir-graph.yaml` 补 `design_gate` 强制块。
- **编译验证多平台 bundle**：`verification-manifest.yml` 增 `platform_bundles`（iOS/Android/Harmony/RN bundle）；Quality Agent 明确"编译失败自动定位修复"职责。
- **RN/Figma 可选适配指南**：新增 `RN-FIGMA-ADAPTER-GUIDE.md`；核心门禁工具无关，可整体替换为其他技术栈。

### 修复
- `scan_legacy_structure.py`：`yaml.safe_dump(sort_keys=...)` 在 PyYAML(Python 3.6) 不支持 → 加 try/except 降级，修复 structure_governance_contract 在 3.6 环境失败。

### 说明
- 本版在 5.7.0（project structure governance）基础上合并 5.6.0 的文章框架前端/移动端闭环；通用内核进核心门禁，RN/Figma 落可选适配层。selftest 26/26；Python 3.6 兼容。

## [5.7.0] - 2026-06-21

### 新增
- **Project Structure Governance**：新增 `deliverhq init-project --profile fullstack-web`，初始化 AI 友好、人类易复查的项目目录结构与 DeliverHQ 治理空间。
- **Structure Profile**：新增 `structure-profiles/fullstack-web.yml` 与项目级 `STRUCTURE-PROFILE.yml`，声明 apps/packages/tests/config/infra/docs/DeliverHQ 的结构契约。
- **StructureGate**：新增 `scripts/structuregate.py`，检查必需目录、禁止顶层目录、测试/配置/源码放置规则和 `.env` 泄露。
- **Legacy Structure Scan**：新增 `scripts/scan_legacy_structure.py`，只读扫描老项目目录结构，生成 `structure-assessment-report.md` 与 `STRUCTURE-PROFILE.candidate.yml`。
- **Project structure docs**：新增 `docs/PROJECT-STRUCTURE-GOVERNANCE.md`，说明新项目 strict mode、老项目 progressive mode 和迁移策略。

### 变更
- `selftest.py` 增加 Project Structure Governance 契约测试，覆盖新项目 scaffold、StructureGate 正反例和老项目结构扫描。
- `doctor` / `selftest` 继续作为安装后验证入口。

### 设计边界
- 不生成业务代码。
- 不自动重构老项目目录。
- 不引入 GitNexus / Graphify / Dashboard / Dynamic Workflow。

## [5.6.0] - 2026-06-21

### 新增
- **Gate JSON evidence schema**：`gate_json_output.py` 成为最小 Gate evidence schema helper，并通过 `runtime_support.write_gate_evidence()` 集成。
- **ReviewGate 对抗式检查清单**：review 报告必须覆盖删测试、降阈值、绕 Gate、happy path only、边界遗漏等最小对抗检查。
- **dir-graph lint**：新增 `scripts/dir_graph_lint.py` 并接入 selftest，开始验证 `dir-graph.yaml` 机器契约。
- **四职能最小模式文档**：新增 `docs/FOUR-FUNCTION-MODE.md`，降低小团队理解多 Agent 流程的复杂度。
- **CLI 版本输出**：新增 `deliverhq --version` / `deliverhq version`，便于 GitHub npm 安装后确认版本。

### 变更
- **Workflow Router 规则去重**：新增 `routing_rules.py`，`workflow_router.py` 与 `eval_routing.py` 共用路由规则，降低评估与生产路径漂移。
- **Traceability 闭环增强**：ReviewGate 校验 AC → implementation/tests → changed files 的闭环，并支持 migration 文件映射。
- **错题本治理说明增强**：明确 `mistake-book.md` 中重复失败如何进入 `rules-candidates.md`，再由人工 promote/reject。

### 修复
- plan-only / no-modification 请求不再误触发完整 DeliverHQ 流程。
- DevPhase / worktree 子进程在 Windows 下的 UTF-8 输出处理更稳。
- selftest / gate contract 运行后不再污染示例 CR 的 evidence/state。

## [5.5.0] - 2026-06-18

### 新增（DeliverHQ Home 目录治理 / agent 无关，防产物散落）
- **Home 目录强制规则**：经 DeliverHQ 分析/治理的项目，所有产物强制收进 `<项目根>/DeliverHQ/`，严禁散落到根目录、根 docs、根 change-requests 或 skill 安装目录。
- **agent 无关的确定性落点**：新增 `scripts/deliverhq_home.py`，自动定位 DeliverHQ home（优先级：`--home` > 环境变量 `DELIVERHQ_HOME` > 向上找已有 `DeliverHQ/` > 项目根标志 `.git`/`package.json` 等 > 兜底 `cwd/DeliverHQ`）。不论 Hermes / Claude / Codex / Gemini 谁调、读不读文档、传不传参，产物都落进项目的 `DeliverHQ/`。
- `init_cr.py` 新增 `--home`；`scan_legacy.py` 的 `--out` 省略时自动定位落点（新增 `--home` / `--cr`）。修复全局安装（如 `~/.hermes/skills/deliverhq/`）时 CR/扫描产物散落到 skill 目录或当前目录的问题。
- `cr_state.py` 公共漏斗新增 warning-first 校验：8 个 Gate 经此漏斗，CR 不在 `DeliverHQ/` 内时告警并提示归位（不阻断 skill 自检）。
- 规则写入多处入口：SKILL.md（Hermes 唯一入口）顶部、AGENTS.md、dir-graph.yaml（`deliverhq_home` 契约），消除"相对谁"的路径歧义；SKILL.md 模式 3/4 命令显式 `DeliverHQ/` 前缀。
- selftest 仍 **22/22**；Python 3.6 兼容。

## [5.4.0] - 2026-06-18

### 新增（PRD 层 / 产品意图唯一来源）
- **PRD 层**：`docs/PRD.md`(产品意图唯一来源,薄、叙事、给人看全貌,仅人工维护,Agent 只读)。功能锚点 `[PRD-XXX]` 是 CR 的挂载点;单文件原则,大产品用锚点 ID 前缀分层。
- **PRD↔CR 派生链接**：`change-requests/CR-TEMPLATE/acceptance-spec.md` 顶部新增 `derived_from{prd_section, prd_hash}`,CR 是 PRD 的可执行切片。
- **PRD↔CR 对账**：`scripts/drift_check.py`。重算 PRD 锚点章节哈希(排除「关联 CR」行)与 CR 记录比对;confirmed 锚点不一致 → NEED_HUMAN_DECISION(改CR/改PRD/记差异),reverse-engineered 锚点仅警告(老项目放宽)。
- `scripts/specgate.py` 新增检查 9：PRD 链接与对账(warning-first,不破坏现有 8 项检查与 cr_state 联动)。
- selftest 仍 **22/22**;Python 3.6 兼容。

### 设计原则
- PRD 给人看意图(不写 ID/schema/Do-Not-Touch),acceptance-spec 给机器验;拆分是 Spec Agent 职责,SpecGate 只检查;不一致逼人对账而非静默阻断。

## [5.3.0] - 2026-06-16

### 新增（执行层 / Loop Engineering 场景化落地，去重不照搬）
- **证据补全 Loop**：`scripts/evidence_loop.py`。可恢复 loop——读 state.yml 恢复进度（无则 fail-closed），扫描 CR 缺哪些真实证据(spec/traceability/changed-files/manifest/test-plan)，列 gaps+next_action，写回 needs_human，写 evidence bundle。
- selftest 新增 `evidence_loop_contract`（无state→fail_closed / 缺证据→needs_human / 齐全→done），现 **22/22**。
- README 加"证据补全 Loop"小节；CAPABILITY-MATRIX 加 evidence_loop 行。

### 去重原则（审核第 4 份建议后）
- 第 4 份建议 90% 是已实现项（状态机/state.yml/证据门禁/fail-closed/retry/worktree/writeback 均已具备）。唯一真增量是"把抽象能力落成具体场景 loop"。
- 复用 cr_state / ReviewGate 证据口径 / retry_guard / write_gate_evidence，**不新增 Agent，不重命名现有状态机**（避免破坏 22 项 selftest 契约）。

## [5.2.0] - 2026-06-16

### 新增（执行层 / 借鉴 GSD，去重不照搬）
- **结构化 Plan + PlanChecker**：`plan.yml` 模板 + `scripts/plan_checker.py`。机检 task 粒度/verify/done/依赖/文件冲突/AC 覆盖，fail-closed；`--emit-waves` 派生 wave plan。
- **三层定位**写入 README：规范层(OpenSpec)/纪律层(Superpowers)/执行层(GSD)。
- `state.yml` 补 `goal` / `current_plan` / `completed_steps` 字段（向后兼容）。
- selftest 新增 `plan_checker_contract`（6 项正反例），现 **21/21**。
- 新增 `PLAN-GUIDE.md`。

### 去重原则
- Worker = 现有 Dev Agent；Verifier = 现有 ReviewGate/QualityGate。**不新增平行角色**，只补 PlanChecker 这一真缺口。

## [5.1.2] - 2026-06-16

### 新增
- 补齐 GitHub 发布所需元数据：`LICENSE`(MIT)、`.gitignore`、`package.json` 的 `repository` / `homepage` / `bugs` / `author` 字段。
- 新增本 `CHANGELOG.md`。

### 说明
- 纯打包/分发层改动，DeliverHQ 框架门禁脚本未变（`skill/VERSION.yml` 维持 5.0.0）。
- skill selftest 仍为 20/20。

## [5.1.0] - 2026-06-16

### 新增
- **多 Agent 安装支持**：`init --target claude|hermes|codex|gemini|generic`。
  - 文件夹型（claude/hermes）：整套复制到对应 skills 目录，靠 SKILL.md frontmatter 发现。
  - 扁平型（codex/gemini/generic）：核心放 `.deliverhq/`，向 `AGENTS.md`/`GEMINI.md`/`DELIVERHQ.md` 注入幂等指针段。
- `doctor` 自动探测多种安装位置。

## [5.0.0] - 2026-06-16

### 新增
- 首个可 `npx deliverhq init` 安装的版本（Claude Code）。
- SKILL.md 补 YAML frontmatter；空目录加 `.gitkeep` 修复 npm 打包丢目录。
# Unreleased

### Added

- `deliverhq bootstrap`：证据化老项目入场，默认只读，复用 Legacy Scan，apply 仅创建候选治理文件。
- route 输出 required/skipped Gates、成本区间、估算因素与置信度。
- Brownfield plan 的 read/write、复用搜索和破坏性变更证据契约。
- Context Handoff 的来源 SHA-256、两阶段窗口、已排除方案和 next action 校验。

### Changed

- Scout / Repo Harness 从 roadmap 提升为 experimental integrated。
- ContextWindowGate 和 PlanChecker 能力说明与实际契约同步。
