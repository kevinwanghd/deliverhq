# DeliverHQ v4.5 - Skill 构建指南

> 本文档指导其他 Agent 平台根据 DeliverHQ 框架文件**自动生成 skill**

## 📦 包内容说明

解压 `deliverhq-v4.5-portable.tar.gz` 后得到：

```
DeliverHQ/
├── docs/skill-definition.md          # ⭐ Skill 定义规格（新 agent 读这个生成 skill）
├── docs/skill-prompts.md              # ⭐ Skill 的核心 Prompt 模板
├── AGENTS.md                          # 9 个 Agent 的行为规则
├── dir-graph.yaml                     # 权限与路径规范
├── scripts/                           # 10 个 Python 自动化脚本
├── change-requests/CR-TEMPLATE/       # CR 文档模板（20 个文件）
└── ... (其他 47 个文件)
```

**核心文件**：
- `docs/skill-definition.md` — Skill 的功能定义、触发条件、执行流程
- `docs/skill-prompts.md` — Skill 内部调用的完整 Prompt

## 🎯 Skill 生成流程（给新 Agent 的指令）

### Step 1: 读取 Skill 定义
```bash
# 新 Agent 执行
cat DeliverHQ/docs/skill-definition.md
cat DeliverHQ/docs/skill-prompts.md
```

这两个文件包含：
- Skill 名称：`deliverhq`
- 触发关键词：`扫描项目`、`开发新项目`、`DeliverHQ`
- 执行逻辑：2 种模式（新项目 / 老项目）
- 完整的 System Prompt

### Step 2: 生成 Skill
新 Agent 根据 `skill-definition.md` 自动生成 skill，包含：

**Skill 元数据**：
```yaml
name: deliverhq
version: 4.3
description: 多 Agent 协作的文档驱动开发治理框架
triggers:
  - "扫描项目"
  - "开发新项目"
  - "启用 DeliverHQ"
  - "DeliverHQ 治理"
```

**Skill 逻辑**：
```python
def deliverhq_skill(mode, project_path):
    """
    mode: "new-project" 或 "scan-legacy"
    project_path: 项目根目录
    """
    
    # 1. 在项目根目录创建 DeliverHQ/ 文件夹
    create_directory(f"{project_path}/DeliverHQ")
    
    # 2. 复制模板文件（47 个）
    copy_template_files(source="DeliverHQ/", dest=f"{project_path}/DeliverHQ/")
    
    # 3. 根据模式执行不同逻辑
    if mode == "new-project":
        # 新项目：生成初始文档框架
        initialize_new_project(project_path)
    else:
        # 老项目：扫描生成报告
        scan_legacy_project(project_path)
    
    # 4. 激活文档约束
    activate_governance(project_path)
    
    return "DeliverHQ 已部署，文档约束已生效"
```

### Step 3: Skill 自检
生成的 skill 必须能执行：
```bash
python {project_path}/DeliverHQ/scripts/check_skeleton.py {project_path}/DeliverHQ
# 预期输出：✅ 目录: 8/8, 文件: 47/47
```

## 🚀 Skill 使用场景

### 场景 1: 开发新项目

**用户输入**：
```
"启用 DeliverHQ 治理，我要开发一个新的电商系统"
```

**Skill 执行流程**：
```
1. 检测到关键词 "启用 DeliverHQ"
   ↓
2. 询问用户
   - 项目名称？
   - 技术栈？（React/Vue/.NET/Spring/...）
   - 项目根目录路径？（默认当前目录）
   ↓
3. 在项目根目录创建 DeliverHQ/ 文件夹
   ├── AGENTS.md
   ├── dir-graph.yaml
   ├── docs/
   ├── change-requests/CR-TEMPLATE/
   ├── scripts/
   └── ... (47 个文件)
   ↓
4. 自动配置项目信息
   - dir-graph.yaml > workspace.name = "电商系统"
   - docs/CONTEXT.md > Tech Stack = "React + .NET"
   ↓
5. 生成初始 CR-000（项目初始化）
   python scripts/init_cr.py CR-000 "项目初始化" "系统"
   ↓
6. 提示用户
   "✅ DeliverHQ 已部署到 {项目根目录}/DeliverHQ/
   
   📋 下一步：
   1. 填写 CR-000/request.md（项目需求）
   2. 让 AI 生成 acceptance-spec.md
   3. 运行 SpecGate 检查：python DeliverHQ/scripts/specgate.py ...
   4. 开始开发（AI 会自动检查文档完备性）
   
   ⚠️ 从现在开始，所有开发必须遵循 DeliverHQ 规则：
   - 文档不完备 = 不开发
   - 必须通过 Gate 检查才能进入下一阶段"
```

**文档约束激活**：
- AI 每次开发前自动运行：`python DeliverHQ/scripts/pre_dev_gate.py <CR-ID>`
- 如果返回 `BLOCKED` → AI 拒绝开发，提示补全文档

### 场景 2: 扫描老项目

**用户输入**：
```
"用 DeliverHQ 扫描这个老项目，评估代码质量"
```

**Skill 执行流程**：
```
1. 检测到关键词 "扫描" + "DeliverHQ"
   ↓
2. 在项目根目录创建 DeliverHQ/ 文件夹（同场景 1）
   ↓
3. 执行 Scan Agent 逻辑
   - 读取项目源码（../src/**）
   - 分析代码结构、复杂度、技术债
   - 生成两个报告：
     * DeliverHQ/docs/reports/code-health-report.md
     * DeliverHQ/docs/reports/legacy-scan-report.md
   ↓
4. 提取项目信息自动填充
   - docs/CONTEXT.md（从 package.json/.csproj 等推断技术栈）
   - docs/architecture.md（从代码结构推断架构模式）
   - docs/interfaces.md（扫描 API 端点）
   ↓
5. 生成改造建议
   "扫描完成！发现以下问题：
   
   📊 代码健康度：65/100
   - 技术债：12 处高优先级
   - 代码复杂度：3 个方法超过 200 行
   - 测试覆盖率：42%（目标 80%）
   
   📋 建议创建的 CR：
   1. CR-001: 重构 UserService（复杂度过高）
   2. CR-002: 补充单元测试（覆盖率不足）
   3. CR-003: 修复 SQL 注入漏洞（安全问题）
   
   详细报告见：DeliverHQ/docs/reports/
   
   ⚠️ 从现在开始，DeliverHQ 治理生效：
   - 所有新开发必须创建 CR（使用 init_cr.py）
   - 文档不完备不能开发"
```

**文档约束激活**：
- 同场景 1，AI 在开发前强制检查文档

## 📝 Skill 定义规格（skill-definition.md）

新 Agent 需要根据这个规格生成 skill：

```yaml
# Skill 基本信息
name: deliverhq
version: 4.3
description: |
  多 Agent 协作的文档驱动开发治理框架。
  在项目根目录生成 DeliverHQ/ 文件夹，包含 47 个治理文件。
  强制执行"文档不完备 = 不开发"规则，通过 5 个 Gate 检查保证质量。

# 触发条件
triggers:
  keywords:
    - "启用 DeliverHQ"
    - "DeliverHQ 治理"
    - "开发新项目"
    - "扫描项目"
    - "生成治理文档"
  patterns:
    - "用.*DeliverHQ.*扫描"
    - "DeliverHQ.*新项目"

# 执行模式
modes:
  new-project:
    description: 为新项目生成初始文档框架
    steps:
      - 询问项目信息（名称、技术栈）
      - 在项目根目录创建 DeliverHQ/
      - 复制 47 个模板文件
      - 自动配置 dir-graph.yaml 和 CONTEXT.md
      - 生成初始 CR-000
      - 激活文档约束
    
  scan-legacy:
    description: 扫描老项目生成质量报告
    steps:
      - 在项目根目录创建 DeliverHQ/
      - 复制 47 个模板文件
      - 执行 Scan Agent（读取源码）
      - 生成 code-health-report.md
      - 生成 legacy-scan-report.md
      - 推断项目信息填充 CONTEXT.md
      - 激活文档约束

# 核心行为规则
behaviors:
  fail-closed: true  # 文档不完备强制阻断开发
  auto-gate-check: true  # 开发前自动运行 pre_dev_gate.py
  phase-transition-gate: true  # 阶段切换必须通过 Gate

# 文件操作权限
file-operations:
  create:
    - "{project_root}/DeliverHQ/**"
  read:
    - "{project_root}/**"  # 扫描时需要读取整个项目
  write:
    - "{project_root}/DeliverHQ/**"
  protected:  # 不得修改（除非明确批准）
    - "{project_root}/configs/**"
    - "{project_root}/secrets/**"

# 依赖检查
dependencies:
  python: ">=3.7"
  commands:
    - python3
    - tar
    - git  # 可选，用于 traceability

# 验收标准
acceptance:
  - "运行 check_skeleton.py 输出 ✅ 47/47"
  - "dir-graph.yaml 中 workspace.name 不为空"
  - "docs/CONTEXT.md 已填充项目信息"
  - "AI 能自动运行 pre_dev_gate.py"
```

## 🔧 Skill Prompt 模板（skill-prompts.md）

新 Agent 生成 skill 时，内置以下 System Prompt：

### Prompt 1: 新项目模式
```markdown
你是 DeliverHQ 治理框架的部署 Agent。用户要求为新项目启用 DeliverHQ。

执行步骤：
1. 询问用户：
   - 项目名称？
   - 技术栈？（语言、框架、数据库）
   - 项目根目录路径？（默认当前目录）

2. 在 {project_root} 创建 DeliverHQ/ 文件夹，复制以下 47 个文件：
   [文件清单见 check_skeleton.py REQUIRED_FILES]

3. 配置项目信息：
   - dir-graph.yaml > workspace.name = "{项目名称}"
   - dir-graph.yaml > protected_paths = ["{项目敏感路径}"]
   - docs/CONTEXT.md > 填充技术栈、架构模式

4. 生成初始 CR：
   python DeliverHQ/scripts/init_cr.py CR-000 "项目初始化" "系统"

5. 验证部署：
   python DeliverHQ/scripts/check_skeleton.py DeliverHQ
   预期输出：✅ 目录: 8/8, 文件: 47/47

6. 告知用户：
   "✅ DeliverHQ 已部署到 {project_root}/DeliverHQ/
   
   📋 下一步：
   1. 填写 CR-000/request.md
   2. 让 AI 生成 acceptance-spec.md
   3. 运行 SpecGate 检查后开始开发
   
   ⚠️ 从现在起，所有开发必须遵循规则：
   - 文档不完备 = 不开发
   - 开发前运行 pre_dev_gate.py
   - 阶段切换必须通过 Gate 检查"

重要提醒：
- 不要跳过任何文件（必须 47 个全部创建）
- dir-graph.yaml 的路径必须用相对路径（../ 开头）
- 清空 docs/decisions.md 和 docs/mistake-book.md 的历史数据
```

### Prompt 2: 扫描老项目模式
```markdown
你是 DeliverHQ 治理框架的 Scan Agent。用户要求扫描老项目生成质量报告。

执行步骤：
1. 在 {project_root} 创建 DeliverHQ/ 文件夹，复制 47 个文件

2. 推断项目信息：
   - 读取 package.json / pom.xml / .csproj / requirements.txt
   - 推断技术栈、框架版本
   - 填充 docs/CONTEXT.md

3. 扫描源码：
   - 统计代码行数、文件数、模块数
   - 分析圈复杂度（单个方法 > 10 为高）
   - 检测代码坏味道（方法过长、类过大、重复代码）
   - 扫描安全问题（SQL 注入、XSS、硬编码密钥）
   - 统计测试覆盖率（如果有测试报告）

4. 生成报告：
   - DeliverHQ/docs/reports/code-health-report.md
     * 整体评分（0-100）
     * 问题列表（按优先级排序）
     * 改进建议
   
   - DeliverHQ/docs/reports/legacy-scan-report.md
     * 技术债清单
     * 架构问题分析
     * 建议的 CR 列表

5. 验证部署：同新项目模式

6. 告知用户：
   "✅ 扫描完成！
   
   📊 代码健康度：{score}/100
   
   发现的问题：
   - 高优先级：{count} 个（必须修复）
   - 中优先级：{count} 个（建议修复）
   - 低优先级：{count} 个（可延后）
   
   详细报告：
   - DeliverHQ/docs/reports/code-health-report.md
   - DeliverHQ/docs/reports/legacy-scan-report.md
   
   建议创建的 CR：
   {生成的 CR 列表}
   
   ⚠️ DeliverHQ 治理已生效：
   - 后续开发必须创建 CR（使用 init_cr.py）
   - 文档不完备不能开发"

扫描规则：
- 只读取源码，不修改任何文件
- 报告格式必须是 Markdown
- 问题必须标注文件路径和行号
- 评分算法：100 - (高优问题 * 5 + 中优问题 * 2 + 低优问题 * 0.5)
```

### Prompt 3: 开发前检查（内置到所有开发任务）
```markdown
在开始任何代码开发前，你必须运行：

```bash
python DeliverHQ/scripts/pre_dev_gate.py {CR-ID}
```

如果输出 `BLOCKED`，原因可能是：
- acceptance-spec.md 不存在
- acceptance-spec.md 包含 [待确认] 占位符
- acceptance-spec.md 包含 {{模板变量}}

你必须：
1. 停止开发
2. 提示用户："文档不完备，无法开始开发"
3. 告知缺失的内容（从 pre_dev_gate.py 的输出获取）
4. 等待用户补全文档或让 Spec Agent 生成

如果输出 `READY`：
- 可以开始开发
- 但仍需遵守 dir-graph.yaml 的权限规则
- 不得修改 protected_paths 中的文件

这个检查是强制的，不可跳过。
```

## ✅ Skill 验收标准（新 Agent 自检）

生成的 skill 必须通过以下测试：

### 测试 1: 新项目部署
```bash
# 模拟用户输入
"启用 DeliverHQ，新建一个 Todo 应用，技术栈 React + Node.js"

# 预期行为
1. skill 被触发
2. 在当前目录创建 DeliverHQ/
3. 复制 47 个文件
4. dir-graph.yaml 中 workspace.name = "Todo应用"
5. docs/CONTEXT.md 中 Tech Stack = "React + Node.js"
6. 生成 CR-000/
7. 输出提示信息（包含"⚠️ 文档不完备 = 不开发"）

# 验证
python DeliverHQ/scripts/check_skeleton.py DeliverHQ
# 输出：✅ 47/47
```

### 测试 2: 老项目扫描
```bash
# 模拟用户输入
"用 DeliverHQ 扫描这个老项目"

# 预期行为
1. skill 被触发
2. 在当前目录创建 DeliverHQ/
3. 复制 47 个文件
4. 读取项目源码（src/**）
5. 生成 code-health-report.md（包含评分）
6. 生成 legacy-scan-report.md（包含问题列表）
7. 输出扫描结果摘要

# 验证
ls DeliverHQ/docs/reports/
# 输出：code-health-report.md  legacy-scan-report.md
```

### 测试 3: 文档约束生效
```bash
# 模拟用户输入（在已部署 DeliverHQ 的项目中）
"开始开发 CR-001"

# 预期行为
1. AI 自动运行：python DeliverHQ/scripts/pre_dev_gate.py CR-001
2. 如果 CR-001/acceptance-spec.md 不存在 → 输出 BLOCKED
3. AI 拒绝开发，提示："文档不完备，请先生成 acceptance-spec.md"

# 验证
AI 不应该写任何代码，必须先提示补全文档
```

## 📚 新 Agent 需要读取的文件（按顺序）

```
1. docs/skill-definition.md      # Skill 的功能规格
2. docs/skill-prompts.md          # Skill 的内置 Prompt
3. AGENTS.md                      # 9 个 Agent 的行为规则
4. scripts/check_skeleton.py      # 获取 47 个文件清单
5. change-requests/CR-TEMPLATE/   # 了解 CR 文档结构
```

## 🎯 给新 Agent 的简要指令

```
1. 解压 deliverhq-v4.5-portable.tar.gz
2. 读取 DeliverHQ/docs/skill-definition.md
3. 读取 DeliverHQ/docs/skill-prompts.md
4. 根据以上规格生成名为 "deliver-hq" 的 skill
5. Skill 必须实现两种模式：
   - new-project: 为新项目生成文档框架
   - scan-legacy: 扫描老项目生成质量报告
6. Skill 部署后，在项目根目录生成 DeliverHQ/ 文件夹（47 个文件）
7. 从部署完成开始，AI 所有开发前必须运行 pre_dev_gate.py
8. 文档不完备 → AI 拒绝开发
```

---

**重要提示**：
- 这不是让新 Agent 直接使用现成的 skill
- 而是让新 Agent **根据规格文档自己生成 skill**
- 生成的 skill 在不同平台可能实现方式不同，但行为必须一致
