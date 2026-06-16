# Gotchas — 真实踩坑经验

> 从 DeliverHQ 实际使用中提炼的失败案例和反模式。这些不是模型本来就知道的通用建议，而是真实踩坑后的教训。

## 🔴 P0：必须避免的坑

### 1. 脚本路径依赖 cwd

**问题**：脚本依赖当前工作目录 (cwd)，从不同目录调用会失败。

**失败案例**：
```bash
# 在项目根目录调用
$ python DeliverHQ/scripts/check_skeleton.py .
❌ 失败：找不到 CLAUDE.md

# 在 DeliverHQ/ 目录内调用
$ cd DeliverHQ && python scripts/check_skeleton.py .
✅ 成功
```

**根本原因**：脚本用 `os.getcwd()` 或相对路径 `./docs`。

**正确做法**：
```python
from pathlib import Path

# ✅ 所有脚本开头必须加这一行
DELIVERHQ_ROOT = Path(__file__).parent.parent

# ✅ 然后用 DELIVERHQ_ROOT 拼接路径
docs_dir = DELIVERHQ_ROOT / "docs"
context_file = DELIVERHQ_ROOT / "docs" / "CONTEXT.md"
```

**影响范围**：10 个脚本全部需要修复。

---

### 2. update_rule_maturity.py 硬编码路径

**问题**：规则成熟度更新脚本硬编码 `"DeliverHQ/delivery"` 路径。

**失败案例**：
```python
# ❌ 错误代码
delivery_dir = "DeliverHQ/delivery"  # 硬编码
```

如果用户把 DeliverHQ 重命名为 `governance/`，脚本会失败。

**正确做法**：
```python
# ✅ 使用相对路径
DELIVERHQ_ROOT = Path(__file__).parent.parent
delivery_dir = DELIVERHQ_ROOT / "delivery"
```

**教训**：任何路径都不要硬编码，必须基于 `__file__` 动态计算。

---

### 3. Windows 下 python3 不存在

**问题**：文档和示例用 `python3`，但 Windows 默认只有 `python`。

**失败案例**：
```bash
# Linux/Mac
$ python3 scripts/check_skeleton.py DeliverHQ
✅ 成功

# Windows
$ python3 scripts/check_skeleton.py DeliverHQ
❌ 'python3' 不是内部或外部命令
```

**正确做法**：
- 文档优先写 `python`
- 或提示 Windows 用户：`python -m pip install python-launcher`
- 或在 README 说明：Windows 用 `python`，Linux/Mac 用 `python3`

**影响文件**：README.md, QUICK-START.md, 所有示例。

---

### 4. SpecGate 误判"待确认"

**问题**：把说明文字里的"待确认"误判为未解决项。

**失败案例**：
```markdown
## 模糊点与待确认项
| 问题 | 状态 |
|---|---|
| IP 地理位置是否解析 | 已解决（不在本期） |

说明：所有"待确认"占位符已全部解决。
```

**错误检查逻辑**：
```python
# ❌ 简单字符串匹配
if "待确认" in content:
    errors.append("包含待确认占位符")
```

**正确做法**：
```python
# ✅ 只检查表格状态列
unresolved_patterns = [
    r'\|\s*待确认\s*\|',
    r'\|\s*待解决\s*\|',
    r'\|\s*open\s*\|',
    r'\|\s*pending\s*\|',
]
for pattern in unresolved_patterns:
    if re.search(pattern, content, re.IGNORECASE):
        errors.append(f"表格状态列包含未解决项：{pattern}")
```

**教训**：不要用简单字符串匹配，要用正则匹配结构化位置。

---

### 5. 模板变量误判

**问题**：把合法代码示例里的 `{{}}` 误判为模板变量。

**失败案例**：
```markdown
## 示例代码
\`\`\`python
data = {"{{key}}": "{{value}}"}  # 合法的 Python 代码
\`\`\`
```

**错误检查逻辑**：
```python
# ❌ 不区分代码块和文本
if "{{" in content:
    errors.append("包含模板变量")
```

**正确做法**：
```python
# ✅ 只检查 Markdown 文本区域，排除代码块
lines = content.split('\n')
in_code_block = False
for line in lines:
    if line.strip().startswith('```'):
        in_code_block = not in_code_block
    if not in_code_block and '{{' in line:
        errors.append(f"文本区域包含模板变量：{line}")
```

**教训**：检查 Markdown 时，必须区分代码块和文本。

---

### 6. 直接修改 CR-TEMPLATE

**问题**：用户直接修改 `CR-TEMPLATE/`，导致后续 CR 继承错误。

**失败案例**：
```bash
# 用户直接改 CR-TEMPLATE
$ vim change-requests/CR-TEMPLATE/request.md
# 把示例改成具体需求

# 后续创建 CR-002
$ python scripts/init_cr.py CR-002 "新需求" "PM"
# CR-002 继承了错误的 CR-TEMPLATE 内容
```

**正确做法**：
1. `CR-TEMPLATE/` 是只读模板，不得直接修改
2. 用 `init_cr.py` 复制 → 修改副本
3. 在 `README.md` 明确提示：⚠️ 不要直接修改 CR-TEMPLATE

**教训**：模板文件需要明确标注"只读"，并在文档中反复提示。

---

### 7. DeliverHQ 覆盖项目根 docs

**问题**：DeliverHQ 的 `docs/` 被误认为可以覆盖项目根目录的 `docs/`。

**失败案例**：
```
project/
├── docs/                  # 项目权威工程约定
│   ├── architecture.md
│   └── api-spec.md
└── DeliverHQ/
    └── docs/              # 治理记忆
        ├── CONTEXT.md
        └── rules.md
```

用户以为 `DeliverHQ/docs/architecture.md` 可以替代 `project/docs/architecture.md`。

**正确理解**：
- `project/docs/` — 权威工程约定（如 OpenAPI、架构设计）
- `DeliverHQ/docs/` — 治理记忆（规则、决策、错题本）
- 两者互补，不覆盖

**教训**：在 `DeliverHQ/CLAUDE.md` 开头明确说明范围边界。

---

### 8. 纯后端项目被强制 DesignGate

**问题**：后端 API 项目也被要求提供高保真设计稿。

**失败案例**：
```bash
$ python scripts/designgate.py change-requests/CR-001
❌ BLOCKED: 缺少 design/hi-fi-spec.md
```

但 CR-001 是纯后端 API，没有 UI。

**正确做法**：
1. 在 `design/metadata.yml` 添加 `ui_type` 字段：
```yaml
ui_type: none  # none / b-end / c-end
```

2. DesignGate 检查逻辑：
```python
if metadata.get('ui_type') == 'none':
    print("✅ 纯后端项目，跳过 DesignGate")
    sys.exit(0)
```

**教训**：门禁规则要支持例外场景，不能"一刀切"。

---

### 9. QualityGate 自动写入副作用

**问题**：QualityGate 失败时自动写 `mistake-book.md`，用户未预期。

**失败案例**：
```bash
$ python scripts/qualitygate.py CR-001
❌ QualityGate BLOCKED
ℹ️  已自动记录到 docs/mistake-book.md

# 用户查看 mistake-book.md
$ git diff docs/mistake-book.md
+ | 2026-06-12 | 单元测试覆盖率 78% | P0 要求 ≥ 80% | CR-001 |
```

用户不知道 QualityGate 会自动修改文件。

**正确做法**：
```python
# ✅ 通过环境变量控制
if os.environ.get('DELIVERHQ_AUTO_MISTAKE_BOOK', '1') == '1':
    # 自动记录
    print(f"ℹ️  已自动记录到 docs/mistake-book.md")
    print(f"   （设置 DELIVERHQ_AUTO_MISTAKE_BOOK=0 可禁用自动记录）")
else:
    # 仅提示
    print(f"💡 建议手动记录到 docs/mistake-book.md")
```

**教训**：有副作用的操作，必须明确提示 + 提供开关。

---

### 10. 过度治理：小任务也启动完整流程

**问题**：改一个 README 错别字也启动完整 CR 流程。

**失败案例**：
```bash
用户："改一下 README 的错别字"
AI："好的，我先创建 CR-001..."
用户："不用这么重，直接改就行"
```

**正确判断**：
以下任务不强制启用 DeliverHQ：
- 只读分析、简单解释
- 文档错别字修复
- 一次性临时脚本
- 不涉及项目源码的任务
- 用户明确说"不要启动 DeliverHQ 流程"

**教训**：Skill 要有边界意识，不要"万物皆流程"。

---

## 🟡 P1：应该注意的坑

### 11. CR-EXAMPLE 模板占位符残留

**问题**：CR-EXAMPLE 本应是"完整示例"，但包含 `{{ServiceName}}` 占位符。

**失败案例**：
```markdown
## 文件清单
| 文件 | 类型 |
|---|---|
| `{{ServiceName}}.cs` | 新增 |
```

**正确做法**：
- CR-EXAMPLE：完整示例（如 `LoginLogService.cs`）
- CR-TEMPLATE：模板占位符（如 `{{ServiceName}}.cs`）

**教训**：EXAMPLE 和 TEMPLATE 职责要清晰。

---

### 12. context_window_check.py 硬编码英文表头

**问题**：检查脚本假设表头是英文，不支持中文项目。

**失败案例**：
```markdown
## 当前阶段
Implementation（开发中）

## 已完成阶段
### 需求分析（已完成）
```

检查脚本只认 "Current Phase" 和 "Completed Phases"。

**正确做法**：
```python
# ✅ 同时支持中英文表头
CURRENT_PHASE_PATTERNS = [
    "## Current Phase",
    "## 当前阶段",
]
```

**教训**：国际化项目，不要硬编码语言。

---

### 13. 一次性加载 47 个文件

**问题**：AI 上来就读取 DeliverHQ 全部 47 个文件，上下文爆炸。

**正确做法**：
按需加载：
- 开发前：`AGENTS.md`, `dir-graph.yaml`, `docs/CONTEXT.md`, `docs/rules.md`
- 设计阶段：+ `docs/architecture.md`, `docs/decisions.md`
- 质量检查：+ `docs/mistake-book.md`

**教训**：不要盲目"全量加载"。

---

## 🟢 P2：可以优化的坑

### 14. check_skeleton.py 只检查文件数量

**问题**：骨架检查通过，但文件内容可能是旧项目残留。

**v4.5 改进**：增加语义污染检查。

---

### 15. 缺少 selftest.py

**问题**：没有一键自检脚本，用户不知道 DeliverHQ 是否正常。

**v4.5 改进**：新增 `scripts/selftest.py`。

---

## 📊 统计

- **P0 坑**：10 个（必须避免）
- **P1 坑**：3 个（应该注意）
- **P2 坑**：2 个（可以优化）

---

**版本**：v4.5  
**来源**：OPTIMIZATION_2026-06-12.md 真实失败案例提炼  
**一句话**：这些坑来自真实踩坑，不是 AI 本来就知道的通用建议。
