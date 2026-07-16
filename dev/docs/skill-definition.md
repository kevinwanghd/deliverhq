# DeliverHQ Skill 定义规格

> 新 Agent 根据此规格自动生成 `deliver-hq` skill

## Skill 元数据

```yaml
name: deliver-hq
version: 4.3
type: governance-framework
category: development-workflow
description: |
  多 Agent 协作的文档驱动开发治理框架。
  在项目根目录生成 DeliverHQ/ 治理文件夹，强制执行"文档不完备 = 不开发"规则。
author: DeliverHQ Project
license: MIT
```

## 触发条件

### 关键词触发
```yaml
keywords:
  - "启用 DeliverHQ"
  - "DeliverHQ 治理"
  - "开发新项目"
  - "扫描项目"
  - "生成治理文档"
  - "DeliverHQ 扫描"
  - "初始化 DeliverHQ"
```

### 模式匹配触发
```yaml
patterns:
  - "用.*DeliverHQ.*扫描.*项目"
  - "DeliverHQ.*新项目"
  - "启动.*DeliverHQ.*治理"
  - "生成.*文档体系"
```

### 上下文触发
```yaml
context:
  - 用户明确提到需要项目治理
  - 用户询问如何保证代码质量
  - 用户要求多 Agent 协作开发
```

## 执行模式

### 模式 1: 新项目（new-project）

**触发条件**：
- 用户说"开发新项目"
- 用户说"启用 DeliverHQ"且项目为空或刚初始化

**执行流程**：
```yaml
steps:
  1_collect_info:
    action: 询问用户
    questions:
      - 项目名称？
      - 技术栈？（框架、语言、数据库）
      - 项目根目录？（默认当前目录）
      - 是否有初始需求？（可选）
    
  2_create_structure:
    action: 在项目根目录创建 DeliverHQ/ 文件夹
    files: 47 个（见 check_skeleton.py 的 REQUIRED_FILES）
    source: 从解压的 DeliverHQ/ 模板复制
    
  3_configure:
    action: 自动配置项目信息
    files:
      - dir-graph.yaml:
          workspace.name: "{用户输入的项目名}"
          protected_paths: [自动推断敏感路径]
          agents.dev-agent.writes: [推断源码目录]
      
      - docs/CONTEXT.md:
          Overview: "{用户输入的项目描述}"
          Tech Stack: "{用户输入的技术栈}"
          Architecture Pattern: [根据技术栈推断]
      
      - docs/decisions.md: 清空历史，保留表头
      - docs/mistake-book.md: 清空历史，保留表头
    
  4_init_cr:
    action: 生成初始 CR
    command: python DeliverHQ/scripts/init_cr.py CR-000 "项目初始化" "系统"
    
  5_verify:
    action: 验证部署完整性
    command: python DeliverHQ/scripts/check_skeleton.py DeliverHQ
    expected: "✅ 目录: 8/8, 文件: 47/47"
    
  6_activate_governance:
    action: 激活文档约束
    effect: |
      从此刻起，AI 所有开发任务前必须运行 pre_dev_gate.py
      文档不完备 → BLOCKED → 拒绝开发
    
  7_notify_user:
    action: 输出完成提示
    message: |
      ✅ DeliverHQ 已部署到 {project_root}/DeliverHQ/
      
      📋 接下来的步骤：
      1. 填写 DeliverHQ/change-requests/CR-000/request.md（初始需求）
      2. 让 AI 生成 acceptance-spec.md（验收规格）
      3. 运行 SpecGate 检查：python DeliverHQ/scripts/specgate.py ...
      4. 开始开发（AI 会自动检查文档）
      
      ⚠️ 从现在开始，所有开发必须遵循 DeliverHQ 规则：
      - 文档不完备 = 不开发
      - 开发前自动运行 pre_dev_gate.py
      - 阶段切换必须通过 Gate 检查
      
      📚 详细文档：
      - DeliverHQ/README.md — 使用指南
      - DeliverHQ/AGENTS.md — 行为规则
```

### 模式 2: 扫描老项目（scan-legacy）

**触发条件**：
- 用户说"扫描项目"
- 用户说"用 DeliverHQ 扫描"
- 项目已有源码

**执行流程**：
```yaml
steps:
  1_create_structure:
    action: 在项目根目录创建 DeliverHQ/ 文件夹
    files: 47 个（同新项目模式）
    
  2_infer_project_info:
    action: 推断项目信息
    sources:
      - package.json → Node.js 项目
      - pom.xml → Java Maven 项目
      - requirements.txt → Python 项目
      - *.csproj → .NET 项目
      - go.mod → Go 项目
    output:
      - 技术栈
      - 框架版本
      - 依赖包列表
    fill: docs/CONTEXT.md
    
  3_scan_codebase:
    action: 扫描源码
    metrics:
      - 代码行数（总行数、有效行数、注释行数）
      - 文件统计（文件数、模块数）
      - 圈复杂度（单方法、平均值）
      - 代码坏味道（方法过长、类过大、重复代码）
      - 安全问题（SQL 注入、XSS、硬编码密钥）
      - 测试覆盖率（如有报告）
    
  4_generate_reports:
    action: 生成两个报告
    files:
      - docs/reports/code-health-report.md:
          sections:
            - 整体评分（0-100）
            - 问题分类（高/中/低优先级）
            - 问题详情（文件路径 + 行号）
            - 改进建议
          scoring: 100 - (高优 * 5 + 中优 * 2 + 低优 * 0.5)
      
      - docs/reports/legacy-scan-report.md:
          sections:
            - 技术债清单
            - 架构问题分析
            - 依赖风险（过时的包、安全漏洞）
            - 建议的 CR 列表
    
  5_suggest_crs:
    action: 根据扫描结果生成 CR 建议
    rules:
      - 圈复杂度 > 15 → 建议重构 CR
      - 测试覆盖率 < 50% → 建议补充测试 CR
      - 发现安全漏洞 → 建议修复安全问题 CR
      - 代码重复率 > 20% → 建议消除重复 CR
    
  6_verify:
    action: 验证部署完整性（同新项目模式）
    
  7_activate_governance:
    action: 激活文档约束（同新项目模式）
    
  8_notify_user:
    action: 输出扫描结果
    message: |
      ✅ 扫描完成！
      
      📊 代码健康度：{score}/100
      
      发现的问题：
      - 🔴 高优先级：{count} 个（必须修复）
      - 🟡 中优先级：{count} 个（建议修复）
      - 🟢 低优先级：{count} 个（可延后）
      
      详细报告：
      - DeliverHQ/docs/reports/code-health-report.md
      - DeliverHQ/docs/reports/legacy-scan-report.md
      
      📋 建议创建的 CR：
      1. CR-001: {建议标题}
      2. CR-002: {建议标题}
      ...
      
      ⚠️ DeliverHQ 治理已生效：
      - 后续开发必须创建 CR（使用 init_cr.py）
      - 文档不完备不能开发
      - 所有改动需通过 Gate 检查
```

## 核心行为规则

### 规则 1: Fail-Closed（文档不完备 = 阻断开发）

```yaml
rule: document-gate
enforcement: mandatory
trigger: AI 接收到任何开发任务（编写代码、修改文件）
behavior:
  pre_check:
    command: python DeliverHQ/scripts/pre_dev_gate.py {CR-ID}
    if_blocked:
      action: 拒绝开发
      message: |
        ⛔ 文档不完备，无法开始开发
        
        缺失的内容：
        {从 pre_dev_gate.py 输出提取}
        
        请先：
        1. 完善 acceptance-spec.md
        2. 删除所有 [待确认] 占位符
        3. 替换所有 {{模板变量}}
        4. 重新运行 pre_dev_gate.py 验证
      no_code: true
    if_ready:
      action: 允许开发
      continue: true
```

### 规则 2: Gate 检查强制

```yaml
rule: phase-gate
enforcement: mandatory
gates:
  - name: SpecGate
    trigger: Spec Agent 完成 acceptance-spec.md
    command: python scripts/specgate.py {acceptance-spec-path}
    pass_criteria:
      - 无 [待确认] 占位符
      - 场景数量 ≥ 3
      - 无模板变量残留
    blocked_next: Design Agent, Context Agent
  
  - name: DesignGate
    trigger: Design Agent 完成设计稿
    command: python scripts/designgate.py {cr-path}
    pass_criteria:
      - C 端 UI 必须有高保真设计稿
      - B 端 UI 至少有低保真线框图
    blocked_next: Context Agent
  
  - name: ContextWindowGate
    trigger: Context Agent 完成 context-summary.md
    command: python scripts/context_window_check.py {context-summary-path}
    pass_criteria:
      - 包含 4 个必需章节
      - 上下文不超过 2 个阶段全文
    blocked_next: Dev Agent
  
  - name: QualityGate
    trigger: Quality Agent 完成 quality-report.md
    command: python scripts/qualitygate.py {cr-path}
    pass_criteria:
      - P0 通过率 100%
      - 测试覆盖率 ≥ 80%
      - 无 Critical 级别告警
    blocked_next: Writeback Agent
    on_failure: 自动调用 update_mistake_book.py 记录错误
  
  - name: WritebackGate
    trigger: Writeback Agent 完成知识沉淀
    command: python scripts/writeback_gate.py {cr-path}
    pass_criteria:
      - traceability.yml 完整
      - git status 干净
      - 组织记忆已更新
    blocked_next: Memory Agent（归档）
```

### 规则 3: Agent 职责边界

```yaml
rule: agent-permissions
enforcement: mandatory
agents:
  spec-agent:
    reads: [request.md, docs/CONTEXT.md, docs/architecture.md]
    writes: [acceptance-spec.md, specgate-report.md]
    handoff: 通过 SpecGate 交接给 Design/Context Agent
  
  design-agent:
    reads: [acceptance-spec.md, request.md]
    writes: [design/*, designgate-report.md]
    handoff: 通过 DesignGate 交接给 Context Agent
  
  context-agent:
    reads: [acceptance-spec.md, design/*, 上一个 CR 的 context-summary.md]
    writes: [context-summary.md, context-window-report.md]
    handoff: 通过 ContextWindowGate 交接给 Dev Agent
  
  dev-agent:
    reads: [acceptance-spec.md, context-summary.md, design/*, docs/*, 项目源码]
    writes: [项目源码, implementation-plan.md, traceability.yml]
    forbidden: [protected_paths（见 dir-graph.yaml）]
    handoff: 编译通过 + 单元测试通过 → Test Agent
  
  test-agent:
    reads: [acceptance-spec.md, implementation-plan.md, 项目源码]
    writes: [test-plan.md, 测试代码]
    handoff: 测试通过 → Quality Agent
  
  quality-agent:
    reads: [所有 CR 文档, 项目源码, 测试报告]
    writes: [quality-report.md, qualitygate-report.md]
    handoff: 通过 QualityGate → Writeback Agent
  
  writeback-agent:
    reads: [所有 CR 文档, docs/*]
    writes: [writeback-report.md, writeback-gate-report.md, docs/architecture.md, docs/decisions.md, traceability.yml]
    handoff: 通过 WritebackGate → Memory Agent
  
  memory-agent:
    reads: [所有 CR 文档, docs/rules.md, delivery/历史]
    writes: [delivery/YYYY-MM/CR-XXX/（归档目标）]
    action: 运行 update_rule_maturity.py 更新规则成熟度
  
  scan-agent:
    reads: [整个项目源码, Git 历史]
    writes: [docs/reports/code-health-report.md, docs/reports/legacy-scan-report.md]
    no_handoff: 扫描完成后不交接，用户决定后续 CR
```

## 文件操作规范

### 创建权限
```yaml
create:
  - "{project_root}/DeliverHQ/**"  # skill 部署时创建
  - "{project_root}/DeliverHQ/change-requests/CR-*/**"  # init_cr.py 创建
  - "{project_root}/DeliverHQ/delivery/**"  # Memory Agent 归档时创建
```

### 读取权限
```yaml
read:
  - "{project_root}/**"  # 扫描模式需读取整个项目
  - 具体 Agent 的读取范围见"Agent 职责边界"
```

### 写入权限
```yaml
write:
  - "{project_root}/DeliverHQ/**"  # 所有 Agent 只能写 DeliverHQ 内
  - "{project_root}/src/**"  # Dev Agent 可写源码（具体路径见 dir-graph.yaml）
```

### 保护路径
```yaml
protected:
  - "{project_root}/configs/**"  # 配置文件需明确批准
  - "{project_root}/secrets/**"  # 密钥文件禁止修改
  - "{project_root}/.env"  # 环境变量
  - 其他项目特定路径（由 dir-graph.yaml 定义）
```

## 依赖检查

### 必需依赖
```yaml
required:
  python:
    version: ">=3.7"
    check: python3 --version
  
  commands:
    - python3
    - tar  # 解压 portable.tar.gz
    
optional:
  git:
    purpose: traceability.yml 需要 git 信息
    check: git --version
```

### Skill 自检
```yaml
self_check:
  - name: 文件完整性
    command: python DeliverHQ/scripts/check_skeleton.py DeliverHQ
    expected: "✅ 目录: 8/8, 文件: 47/47"
  
  - name: 配置有效性
    checks:
      - dir-graph.yaml 中 workspace.name 不为空
      - docs/CONTEXT.md 已填充项目信息
      - protected_paths 已配置
  
  - name: 脚本可执行
    checks:
      - python scripts/pre_dev_gate.py --help 不报错
      - python scripts/specgate.py --help 不报错
```

## 验收标准

### 新项目模式验收
```yaml
acceptance:
  - DeliverHQ/ 文件夹存在于项目根目录
  - check_skeleton.py 输出 ✅ 47/47
  - dir-graph.yaml 中 workspace.name 已填充
  - docs/CONTEXT.md 已填充技术栈
  - CR-000/ 已生成（包含 20 个模板文件）
  - AI 在开发时会自动运行 pre_dev_gate.py
  - 文档不完备时 AI 拒绝开发
```

### 扫描模式验收
```yaml
acceptance:
  - DeliverHQ/ 文件夹存在
  - check_skeleton.py 输出 ✅ 47/47
  - docs/reports/code-health-report.md 存在且包含评分
  - docs/reports/legacy-scan-report.md 存在且包含问题列表
  - docs/CONTEXT.md 已推断技术栈
  - 输出了建议的 CR 列表
  - AI 后续开发会自动运行 pre_dev_gate.py
```

## Skill 元能力

### 能力 1: 自适应配置
```yaml
capability: auto-configure
description: 根据项目类型自动推断配置
rules:
  - 检测到 package.json → Node.js 项目
    - dir-graph.yaml > agents.dev-agent.writes = ['../src/**', '../lib/**']
    - protected_paths += ['../node_modules/**']
  
  - 检测到 *.csproj → .NET 项目
    - dir-graph.yaml > agents.dev-agent.writes = ['../**/*.cs']
    - protected_paths += ['../bin/**', '../obj/**']
  
  - 检测到 pom.xml → Java 项目
    - dir-graph.yaml > agents.dev-agent.writes = ['../src/**']
    - protected_paths += ['../target/**']
```

### 能力 2: 智能扫描
```yaml
capability: smart-scan
description: 根据项目规模自适应扫描深度
rules:
  - 文件数 < 100 → 全量扫描
  - 文件数 100-1000 → 扫描核心模块
  - 文件数 > 1000 → 采样扫描（10%）+ 热点分析
```

### 能力 3: 增量部署
```yaml
capability: incremental-deploy
description: 检测到已有 DeliverHQ/ 时不覆盖
rules:
  - 如果 DeliverHQ/ 已存在：
    - 提示用户："检测到已有 DeliverHQ，是否覆盖？"
    - 覆盖：备份旧版本到 DeliverHQ/_backup-{timestamp}/
    - 不覆盖：仅更新 scripts/ 和 change-requests/CR-TEMPLATE/
```

## 错误处理

### 常见错误
```yaml
errors:
  - code: E001
    message: "Python 版本过低"
    check: python3 --version < 3.7
    solution: "请升级到 Python 3.7+"
  
  - code: E002
    message: "项目根目录不存在"
    check: 用户输入的 project_root 不存在
    solution: "请确认路径或创建目录"
  
  - code: E003
    message: "文件复制失败"
    check: 复制 47 个文件时出错
    solution: "检查磁盘空间和权限"
  
  - code: E004
    message: "Gate 检查失败"
    check: pre_dev_gate.py 返回 BLOCKED
    solution: "补全文档后重试"
```

---

**注意事项**：
- 此规格是平台无关的，新 Agent 根据自身能力实现
- 关键是行为一致性，而非实现细节
- Skill 生成后必须通过"验收标准"测试
