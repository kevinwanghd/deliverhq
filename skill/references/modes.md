# DeliverHQ 工作模式详解

## 模式 1：新项目初始化

### 触发条件
- 用户说"给项目启用 DeliverHQ"
- 用户说"新建项目，用 DeliverHQ"

### 执行步骤

```
1. 推断项目名（目录名 / 用户指定）
2. 扫描技术栈（package.json / pom.xml / *.csproj / requirements.txt）
3. 生成 DeliverHQ/ 治理目录（含门禁脚本、组织记忆模板、CR 模板等）
4. 自动替换 {{占位符}}：
   - {{项目名称}} → 实际项目名
   - {{技术栈}} → 扫描结果
   - {{项目路径}} → 实际源码路径
5. 创建 CR-000（初始 CR）
6. 提示用户填写 request.md
```

### 自动推断规则

| 文件 | 推断结果 |
|---|---|
| `package.json` | Node.js + 具体框架（Next.js / Express / Nest.js） |
| `pom.xml` | Java + Maven（Spring Boot / Quarkus） |
| `*.csproj` | C# + .NET（ASP.NET Core） |
| `requirements.txt` / `pyproject.toml` | Python（Django / Flask / FastAPI） |
| `go.mod` | Go（Gin / Echo / Fiber） |
| `Cargo.toml` | Rust |

### 输出
```
✅ DeliverHQ 已就绪
   项目：MyProject
   技术栈：Node.js + Next.js 14 + PostgreSQL
   首个 CR：change-requests/CR-000/
   下一步：填写 CR-000/request.md
```

---

## 模式 2：扫描老项目

### 触发条件
- 用户说"扫描这个项目"
- 用户说"评估代码健康度"
- 用户说"看看技术债"

### 执行步骤

```
1. 推断项目信息（同模式 1）
2. 生成 DeliverHQ/ 目录
3. 运行 Scan Agent：
   a. 扫描代码结构
   b. 分析复杂度
   c. 检测技术债
   d. 评估测试覆盖率
4. 生成报告：
   - docs/reports/code-health-report.md
   - docs/reports/legacy-scan-report.md
5. 输出健康度评分和改进建议
```

### 输出
```
📊 代码健康度：72/100
   技术债：18 项
   测试覆盖率：45%
   改进建议：12 条
   
   详细报告：DeliverHQ/docs/reports/code-health-report.md
   下一步：创建 CR 修复高优先级问题
```

---

## 模式 3：创建/推进 CR

### 触发条件
- 用户说"创建一个 CR"
- 用户说"新建需求：xxx"
- 用户说"推进 CR-001 到下一阶段"

### CR 生命周期

```
request.md → acceptance-spec.md → [design/*] → implementation-plan.md → 代码 → test-plan.md → quality-report.md → writeback-report.md → 归档
```

### 创建 CR

```bash
python scripts/init_cr.py CR-001 "需求名称" "提出人"
```

### 推进 CR

每个阶段完成后运行对应 Gate：

| 阶段 | Gate | 命令 |
|---|---|---|
| Spec | SpecGate | `python scripts/specgate.py <path>` |
| Design | DesignGate | `python scripts/designgate.py <path>` |
| Context | ContextWindowGate | `python scripts/context_window_check.py <path>` |
| Dev | pre_dev_gate | `python scripts/pre_dev_gate.py <CR-ID>` |
| Quality | QualityGate | `python scripts/qualitygate.py <path>` |
| Writeback | WritebackGate | `python scripts/writeback_gate.py <path>` |

---

## 模式 4：Gate 检查

### 触发条件
- 用户说"检查能不能开发"
- 用户说"运行 QualityGate"
- AI 自动在阶段切换时运行

### Gate 结果

**PASS**：进入下一阶段
```
✅ SpecGate PASS
   验收条件：8 个（全部明确）
   模糊点：0 个
   可进入 Design/Dev 阶段
```

**BLOCKED**：必须修复后重试
```
❌ SpecGate BLOCKED
   1. 包含模板变量 {{XXX}}
   2. 模糊点未全部解决（2 个 pending）
   
   → 必须修复后重新运行 SpecGate
```

---

## 模式选择决策树

```
用户请求
  ├── 涉及项目源码修改？
  │   ├── 是 → DeliverHQ 已安装？
  │   │   ├── 是 → 模式 3（创建/推进 CR）
  │   │   └── 否 → 模式 1（新项目）或 模式 2（老项目）
  │   └── 否 → 不启用 DeliverHQ
  └── 评估/扫描请求？
      ├── 是 → 模式 2（扫描）
      └── 否 → 不启用 DeliverHQ
```
