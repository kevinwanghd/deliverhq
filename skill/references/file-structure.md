# DeliverHQ 文件结构（47 核心文件）

## 目录布局

```
DeliverHQ/                          # 治理根目录
├── SKILL.md                        # ★ 极短入口（Agent 首先读取）
├── CLAUDE.md                       # 薄工具入口（Claude Code 专用）
├── AGENTS.md                       # Agent 行为规则
├── dir-graph.yaml                  # 机器契约（权限/路径/Agent 定义）
├── README.md                       # 人类阅读的说明文档
├── .ai-instructions                # 强制入口指令
├── MIGRATION.md                    # 迁移到其他平台指南
├── ROLLBACK.md                     # 回滚操作指南
│
├── docs/                           # 组织记忆（baseline knowledge）
│   ├── CONTEXT.md                  # 项目上下文（模板，Skill 自动填充）
│   ├── architecture.md             # 系统架构
│   ├── interfaces.md               # 接口契约
│   ├── data-model.md               # 数据模型
│   ├── rules.md                    # 规则表（带成熟度）
│   ├── decisions.md                # 设计决策记录
│   ├── mistake-book.md             # 错题本
│   ├── verification.md             # 验收标准
│   └── reports/                    # 扫描报告
│       ├── code-health-report.md   # 代码健康度
│       └── legacy-scan-report.md   # 老项目扫描
│
├── change-requests/                # 活跃交付
│   └── CR-TEMPLATE/               # ★ 模板（复制使用）
│       ├── request.md              # 需求输入
│       ├── acceptance-spec.md      # 验收规格
│       ├── context-summary.md      # 上下文摘要
│       ├── implementation-plan.md  # 实施计划
│       ├── test-plan.md            # 测试计划
│       ├── quality-report.md       # 质量报告
│       ├── writeback-report.md     # 归档报告
│       ├── human-decisions.md      # 人工决策
│       ├── traceability.yml        # 需求→代码映射
│       ├── exceptions.yml          # 规则豁免
│       ├── specgate-report.md      # Gate 报告
│       ├── designgate-report.md
│       ├── context-window-report.md
│       ├── qualitygate-report.md
│       ├── writeback-gate-report.md
│       └── design/                 # 设计产物
│           ├── lo-fi-spec.md
│           ├── hi-fi-spec.md
│           ├── prototype.html
│           ├── design-decisions.md
│           └── assets/README.md
│
├── delivery/                       # 已交付归档（按月）
│   └── YYYY-MM/CR-XXX/
│
├── _archived/                      # 历史归档（只读）
│
├── references/                     # 详细参考文档
│   ├── modes.md                    # 工作模式详解
│   ├── gates.md                    # Gate 门禁详解
│   ├── gotchas.md                  # 踩坑清单
│   └── file-structure.md           # 本文件
│
├── evals/                          # 路由评估案例
│   └── skill-routing-cases.md
│
└── scripts/                        # 治理脚本（11 个）
    ├── init_cr.py                  # 初始化 CR
    ├── check_skeleton.py           # 骨架完整性检查
    ├── selftest.py                 # 一键自检
    ├── pre_dev_gate.py             # 开发前门禁
    ├── specgate.py                 # SpecGate
    ├── designgate.py               # DesignGate
    ├── context_window_check.py     # ContextWindowGate
    ├── qualitygate.py              # QualityGate
    ├── writeback_gate.py           # WritebackGate
    ├── update_rule_maturity.py     # 规则成熟度更新
    └── update_mistake_book.py      # 错题本更新
```

## 文件分类

### 入口文件（Agent 启动时读取）
| 优先级 | 文件 | 何时读取 |
|---|---|---|
| 1 | SKILL.md | 首次加载 Skill 时 |
| 2 | AGENTS.md | 执行任何操作前 |
| 3 | dir-graph.yaml | 需要权限/路径信息时 |
| 4 | docs/CONTEXT.md | 需要项目背景时 |

### 组织记忆文件（持续更新）
| 文件 | 更新时机 | 更新者 |
|---|---|---|
| rules.md | 每次交付后 | Writeback Agent |
| decisions.md | 有架构决策时 | Writeback Agent |
| mistake-book.md | QualityGate 失败时 | Quality Agent |
| architecture.md | 架构变更时 | Writeback Agent |
| interfaces.md | 接口变更时 | Writeback Agent |
| data-model.md | 数据模型变更时 | Writeback Agent |

### CR 文档（每个 CR 独立）
| 阶段 | 文件 | 产出者 |
|---|---|---|
| Spec | acceptance-spec.md | Spec Agent |
| Design | design/* | Design Agent |
| Context | context-summary.md | Context Agent |
| Dev | implementation-plan.md | Dev Agent |
| Test | test-plan.md | Test Agent |
| Quality | quality-report.md | Quality Agent |
| Writeback | writeback-report.md | Writeback Agent |

### 脚本文件（治理自动化）
所有脚本使用 `Path(__file__).parent.parent` 定位 DeliverHQ 根目录，不依赖 cwd。

---

## 按需加载策略

**不要一次读取所有 47 个文件！** 按当前任务只加载必要文件：

| 任务 | 需要读取 |
|---|---|
| 创建 CR | SKILL.md → init_cr.py |
| 写验收规格 | acceptance-spec.md + request.md + rules.md |
| 开发代码 | implementation-plan.md + context-summary.md |
| 运行 Gate | 对应 Gate 脚本 + 检查对象文件 |
| 归档 CR | writeback-report.md + traceability.yml |
