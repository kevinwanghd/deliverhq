#!/usr/bin/env python3
"""
Reviewer Agent — 独立 Session 审查

来源：Nexad Agent Harness 实践。

核心原则：
  - Reviewer Agent 从独立 Session 启动
  - 只拿 SpecGate 的结构化输出（spec-output.json）
  - 不拿 Main Agent 的推理 Context

Context 隔离的根因：
  Nexad 发现 Self-evaluation 失效不是因为「同一个模型」，
  而是因为「同一个 Context」——Main Agent 在同一 Context 中会「合理化」掉问题。

用法：
  python reviewer_agent.py CR-001
  python reviewer_agent.py CR-001 --output evidence/adversarial_review_report.md
  python reviewer_agent.py CR-001 --check-only  # 仅验证报告是否存在且 verdict=PASS
"""

import argparse
import json
import subprocess
import sys
import hashlib
import re
from datetime import datetime
from pathlib import Path

# =============================================================================
# 配置
# =============================================================================

DEFAULT_SPEC_OUTPUT = "spec-output.json"
DEFAULT_EVIDENCE_DIR = "evidence"
DEFAULT_REPORT = "evidence/adversarial_review_report.md"

# 严重程度映射（用于 verdict 计算）
SEVERITY_LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]

# governance.config.yml 中的 RL 红线
RL_CRITICAL_LINES = [
    ("RL-C01", "编译必须通过", "bazel build / flutter build / npm run build 退出码 0 是唯一判据"),
    ("RL-C02", "未按阶段执行", "后一阶段输入必须等于前一阶段产出，禁止跳过阶段"),
    ("RL-C03", "先看后写", "禁止在未读懂现有代码模式前发明新写法"),
    ("RL-C04", "先模仿后发明", "禁止 AI 发明新模式，必须模仿项目已有的代码风格"),
    ("RL-C05", "禁止修改受保护路径", "dir-graph.yaml 中定义的 protected_paths 未批准不得修改"),
    ("RL-C06", "git commit 必须同步执行", "git commit 后 git log -1 hash 更新是唯一成功证据"),
    ("RL-C07", "对抗式审查后才能提交", "有 blocking_findings 必须解决"),
]

# 风险模式（来自 adversarial_review.py，保持兼容）
RISK_PATTERNS = {
    "CRITICAL": [
        ("硬编码密钥/凭证", r"(?i)(api[_-]?key|secret|password|token)\s*=\s*['\"][a-zA-Z0-9]{16,}['\"]"),
        ("SQL 注入风险", r"(?i)(execute|query|select)\s*\([^)]*\+[^)]+\)"),
        ("未处理异常直接暴露", r"(?i)except[^:]*:\s*(?!.*(?:log|raise|print))[^\n]+"),
        ("未授权访问路径", r"(?i)(admin|superuser|root)\s*(==|!=)\s*(?!.*role|.*check)"),
        ("危险系统调用", r"(?i)(eval|exec|__import__|subprocess.*shell\s*=\s*True)"),
    ],
    "HIGH": [
        ("硬编码业务 ID", r"(?i)(magic|hardcode|objectid)\s*=\s*['\"][a-f0-9]{20,}['\"]"),
        ("空 catch 块静默吞异常", r"(?i)except[^:]*:\s*(pass|...)\s*(#.*)?$"),
        ("时间逻辑硬编码", r"(?i)(if|when)\s+.*\b(now|today|datetime)\b.*\b(==|!=|>=|<=)\b"),
        ("并发竞态条件", r"(?i)(lock|mutex|semaphore|threading)\s+.*?(?<!await)"),
        ("内存泄漏隐患", r"(?i)(global|cache|dict\.setdefault)\s+.*?(?<!del)"),
        ("日志脱漏关键字段", r"(?i)log\.(info|warn|error)\s*\([^)]*\)(?!.*(?:user_id|session|request_id))"),
    ],
    "MEDIUM": [
        ("过于宽泛的异常捕获", r"except\s+Exception\s*:\s*pass"),
        ("生产环境硬编码判断", r"(?i)if\s+env\s*==\s*['\"]production['\"]"),
        ("缺少超时控制", r"(?i)(requests|http)\.(get|post)\([^)]*(?!timeout)"),
        ("循环内远程调用", r"(?i)for\s+.*:\s*(?<!await).*\.(get|post|send|publish)"),
        ("敏感数据未脱敏日志", r"(?i)(password|phone|email|id_card)\s+in\s+log"),
    ],
}

# =============================================================================
# 工具函数
# =============================================================================

def load_tier_config() -> dict:
    """从 governance.config.yml 加载 tier 配置"""
    import yaml
    config_path = Path(__file__).parent.parent.parent / "governance.config.yml"
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        tiers = config.get("delivery_tiers", [])
        return {t["id"]: t for t in tiers}
    except Exception:
        return {}


def run_git(cmd: list, cwd: Path = None) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, "", str(e)


def get_repo_root(cr_dir: Path) -> Path:
    rc, out, _ = run_git(["git", "rev-parse", "--show-toplevel"], cwd=cr_dir)
    if rc == 0:
        return Path(out.strip())
    return cr_dir


def get_git_diff(repo_root: Path, scope: str = ".") -> str:
    _, stdout, _ = run_git(["git", "diff", "--", scope], cwd=repo_root)
    return stdout


def get_git_status(repo_root: Path, scope: str = ".") -> str:
    _, stdout, _ = run_git(["git", "status", "--porcelain", "--", scope], cwd=repo_root)
    return stdout


def get_changed_files(repo_root: Path, scope: str = ".") -> list[str]:
    _, stdout, _ = run_git(["git", "diff", "--name-only", "--", scope], cwd=repo_root)
    return [f for f in stdout.strip().split("\n") if f]


def compute_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_spec_output(spec_path: Path) -> dict | None:
    if not spec_path.exists():
        return None
    try:
        return json.loads(spec_path.read_text(encoding="utf-8"))
    except Exception:
        return None


# =============================================================================
# 核心审查逻辑
# =============================================================================

def scan_code_patterns(diff_text: str) -> list[dict]:
    """用正则扫描代码模式，匹配风险"""
    findings = []
    for severity, patterns in RISK_PATTERNS.items():
        for name, pattern in patterns:
            matches = re.finditer(pattern, diff_text, re.MULTILINE | re.IGNORECASE)
            for m in matches:
                line_num = diff_text[:m.start()].count("\n") + 1
                # 找该行在哪个文件
                context_lines = diff_text[:m.start()].split("\n")
                filename = "unknown"
                for fl in reversed(context_lines):
                    if fl.startswith("+++ b/"):
                        filename = fl[6:]
                        break
                    elif fl.startswith("diff --git"):
                        parts = fl.split(" b/")
                        if len(parts) > 1:
                            filename = parts[1].split(" ")[0]
                        break
                findings.append({
                    "severity": severity,
                    "type": name,
                    "matched_text": m.group(0),
                    "file": filename,
                    "line": line_num,
                    "auto_fixable": False,
                    "resolution": "待确认",
                })
    return findings


def check_rl_compliance(diff_text: str, spec: dict, changed_files: list[str]) -> list[dict]:
    """检查 RL 红线合规性"""
    findings = []
    
    # RL-C01: 编译必须通过 → 检查是否改动了编译相关文件但没提 build 步骤
    build_related = [f for f in changed_files if any(x in f for x in [".csproj", ".sln", "CMakeLists.txt", "pubspec.yaml", "package.json", "BUILD"])]
    if build_related and "build" not in diff_text.lower():
        findings.append({
            "severity": "HIGH",
            "type": "RL-C01 编译合规",
            "detail": f"改动了构建配置文件 {build_related}，但 spec 未提及编译验证",
            "recommendation": "spec-output.json 应包含编译验证命令和预期结果",
            "auto_fixable": False,
            "resolution": "待确认",
        })

    # RL-C03: 先看后写 → 检查是否改动了新路径
    new_files = [f for f in changed_files if f in spec.get("diff_summary", {}).get("new_files", [])]
    if new_files and not any("read" in diff_text.lower() or "existing" in diff_text.lower() for _ in [1]):
        findings.append({
            "severity": "MEDIUM",
            "type": "RL-C03 先看后写",
            "detail": f"新增了文件 {new_files}，需确认是否先读懂了现有模式再写",
            "recommendation": "新增文件应参照项目已有代码风格",
            "auto_fixable": False,
            "resolution": "待确认",
        })

    # RL-C04: 先模仿后发明 → 检查是否有不寻常的架构变化
    arch_related = [f for f in changed_files if any(x in f for x in ["Architecture", "Design", "Service", "Manager"])]
    if arch_related and len(arch_related) > 2:
        findings.append({
            "severity": "LOW",
            "type": "RL-C04 先模仿后发明",
            "detail": f"改动了 {len(arch_related)} 个架构相关文件，需确认是否在发明新模式",
            "recommendation": "大范围架构改动应参照项目现有模式",
            "auto_fixable": False,
            "resolution": "待确认",
        })

    # 不可逆性检查
    irreversible = spec.get("implementation", {}).get("self_assessment", {}).get("irreversible", False)
    if irreversible:
        findings.append({
            "severity": "HIGH",
            "type": "不可逆决策审查",
            "detail": "spec 标记此变更具有不可逆性，需额外审查",
            "recommendation": "不可逆变更必须有回滚方案和人工确认",
            "auto_fixable": False,
            "resolution": "待确认",
        })

    return findings


def first_principles_review(diff_text: str, spec: dict, changed_files: list[str]) -> list[dict]:
    """第一性原理审查"""
    findings = []

    # 检查是否治标不治本
    if "hotfix" in diff_text.lower() or "patch" in diff_text.lower():
        findings.append({
            "severity": "MEDIUM",
            "type": "治标不治本风险",
            "detail": "diff 中出现 hotfix/patch 关键词，需确认是否只是临时补丁而非解决根因",
            "recommendation": "追问：这个问题的本质原因是什么？是否有更深层的架构隐患？",
            "auto_fixable": False,
            "resolution": "待确认",
        })

    # 检查需求与实现是否对齐
    reqs = spec.get("requirements", [])
    if reqs:
        req_text = " ".join(r.get("text", "") for r in reqs)
        # 简单检查：diff 中的关键词是否与需求相关
        diff_words = set(re.findall(r'\b[a-zA-Z]{5,}\b', diff_text.lower()))
        req_words = set(re.findall(r'\b[a-zA-Z]{5,}\b', req_text.lower()))
        overlap = diff_words & req_words
        if len(overlap) < 3:
            findings.append({
                "severity": "INFO",
                "type": "需求-实现对齐",
                "detail": "diff 中的关键词与需求文本重叠较少，可能存在范围漂移",
                "recommendation": "确认 diff 范围是否严格对齐需求范围",
                "auto_fixable": False,
                "resolution": "待确认",
            })

    return findings


def malicious_user_review(diff_text: str, spec: dict, changed_files: list[str]) -> list[dict]:
    """恶意用户审查"""
    findings = []

    boundary_patterns = [
        ("超长输入风险", r"(?i)(input|value|param|arg)\s*(=|:)", "恶意用户可提交超长字符串测试是否有截断或溢出"),
        ("空值注入", r"(?i)(if|where)\s+.*\b(id|param)\b\s*(==|!=)\s*null", "空值是否会导致 NPE 或绕过检查"),
        ("负数/极端值", r"(?i)(price|amount|count|limit)\s*(=|:)", "负数或极大值是否被正确校验"),
    ]

    for name, pattern, desc in boundary_patterns:
        if re.search(pattern, diff_text):
            findings.append({
                "severity": "HIGH",
                "type": f"恶意用户-边界数据：{name}",
                "detail": desc,
                "recommendation": f"检查 {name} 的输入校验是否完整",
                "auto_fixable": False,
                "resolution": "待确认",
            })

    # 并发攻击面
    if re.search(r"(?i)(lock|mutex|atomic|concurrent|parallel)", diff_text):
        findings.append({
            "severity": "MEDIUM",
            "type": "并发攻击面",
            "detail": "diff 涉及并发相关代码，需检查是否有竞态条件",
            "recommendation": "列出所有并发读写路径，检查是否有遗漏的同步点",
            "auto_fixable": False,
            "resolution": "待确认",
        })

    return findings


def generate_review_prompt(spec: dict, diff_text: str, changed_files: list[str]) -> str:
    """生成供独立 Reviewer Agent 执行的审查提示词"""

    cr_id = spec.get("cr_id", "unknown")
    background = spec.get("background", {})
    impl = spec.get("implementation", {})
    governance = spec.get("governance", {})

    prompt = f"""## 独立审查 — {cr_id}

你是 DeliverHQ 的 Reviewer Agent。你从**独立的 Session**启动，只拿以下输入，不访问 Main Agent 的对话历史。

### 你的输入（仅这些）
1. spec-output.json（业务目标和实现摘要）
2. git diff（代码改动）
3. governance rules（治理红线）

---

### CR 元数据

- **CR ID**: {cr_id}
- **标题**: {background.get('title', 'N/A')}
- **背景**: {background.get('why', 'N/A')}
- **来源**: {', '.join(background.get('derived_from', [])) or 'N/A'}
- **实现思路**: {impl.get('approach', 'N/A')}
- **Delivery Tier**: {governance.get('tier', '未声明')}

---

### 改动文件

{', '.join(changed_files[:20])}{' ...' if len(changed_files) > 20 else ''}

---

### Git Diff（前 6000 字符）

```
{diff_text[:6000]}
```

---

### Governance Rules（RL 红线）

{chr(10).join(f"- **{rl_id}**: {title} — {desc}" for rl_id, title, desc in RL_CRITICAL_LINES)}

---

### 你的任务

从**三个独立视角**审查，不参考 Main Agent 的任何推理过程：

#### 视角 1：第一性原理审查（生成侧）
- "这个问题真的应该这么解吗？"
- 从业务目标出发重新推导，会选择同样的方案吗？
- 有没有治标不治本的风险？

#### 视角 2：恶意用户审查（验证侧）
- 如果我是恶意用户，会如何搞崩这个系统？
- 边界数据、极端输入、资源耗尽、并发攻击
- 日志和监控真的能捕获这些情况吗？

#### 视角 3：RL 红线合规审查
- 是否触碰了任何 RL-Critical 红线？
- 不可逆决策是否有足够的保护？

---

### 输出格式

对每个发现，按以下格式输出：

```
### [严重程度] 类型名称

- **详情**: 具体问题
- **文件**: 文件路径（如有）
- **建议**: 如何修复
- **可自动修复**: true / false
- **状态**: 待确认 / 已解决
```

最终给出总结：
- **严重发现数（CRITICAL/HIGH）**: N
- **blocking_findings**: N（blocking = CRITICAL 或 HIGH 且未解决）
- **verdict**: PASS / FAIL

**只有 blocking_findings = 0 才算 PASS**。"""
    return prompt


def compute_verdict(all_findings: list[dict]) -> tuple[str, int, list[dict]]:
    """计算 verdict"""
    blocking = [f for f in all_findings 
                if f.get("severity") in ("CRITICAL", "HIGH") 
                and f.get("resolution") == "待确认"]
    verdict = "PASS" if len(blocking) == 0 else "FAIL"
    return verdict, len(blocking), blocking


def generate_report(
    cr_id: str,
    spec: dict,
    changed_files: list[str],
    diff_text: str,
    pattern_findings: list[dict],
    rl_findings: list[dict],
    fp_findings: list[dict],
    malicious_findings: list[dict],
    tier: str,
) -> str:
    """生成审查报告"""

    all_findings = pattern_findings + rl_findings + fp_findings + malicious_findings
    by_severity = {s: [] for s in SEVERITY_LEVELS}
    for f in all_findings:
        sev = f.get("severity", "INFO")
        if sev in by_severity:
            by_severity[sev].append(f)

    verdict, blocking_count, _ = compute_verdict(all_findings)

    background = spec.get("background", {})
    impl = spec.get("implementation", {})
    sha = compute_sha256(diff_text)

    lines = [
        f"# 对抗式审查报告 — {cr_id}",
        "",
        f"> 生成时间：{datetime.now().isoformat()}",
        "> 来源：Nexad Agent Harness 实践 — 独立 Session 审查",
        "> Reviewer Agent 只拿 spec-output.json，不访问 Main Agent Context",
        "",
        "---",
        "",
        "## 元数据",
        "",
        f"- **CR**: {cr_id}",
        f"- **标题**: {background.get('title', 'N/A')}",
        f"- **背景**: {background.get('why', 'N/A')}",
        f"- **Delivery Tier**: {tier}",
        f"- **审查文件数**: {len(changed_files)}",
        f"- **审查范围**: {', '.join(changed_files[:10])}{' ...' if len(changed_files) > 10 else ''}",
        f"- **Diff SHA256**: {sha[:16]}...",
        "",
        "---",
        "",
        "## 审查结论",
        "",
        f"- **verdict**: {verdict}",
        f"verdict: {verdict}  <!-- evidence_gate 解析 -->",
        f"- **blocking_findings**: {blocking_count}（CRITICAL + HIGH 未解决）",
        f"- **严重发现总数**: {len(by_severity['CRITICAL']) + len(by_severity['HIGH'])}",
        f"- **中低风险发现**: {len(by_severity['MEDIUM']) + len(by_severity['LOW']) + len(by_severity['INFO'])}",
        "",
        "---",
        "",
        "## 严重发现（CRITICAL / HIGH）",
        "",
    ]

    for f in by_severity["CRITICAL"] + by_severity["HIGH"]:
        lines.extend([
            f"### {f['type']}  [ {f['severity']} ]",
            "",
            f"- **详情**: {f.get('detail', f.get('matched_text', 'N/A'))}",
            f"- **文件**: {f.get('file', 'N/A')}",
            f"- **建议**: {f.get('recommendation', '待确认')}",
            f"- **可自动修复**: {f.get('auto_fixable', False)}",
            f"- **状态**: {f.get('resolution', '待确认')}",
            "",
        ])

    if len(by_severity["CRITICAL"]) + len(by_severity["HIGH"]) == 0:
        lines.append("*（无严重发现）*\n")

    lines.extend([
        "---",
        "## 中低风险发现（MEDIUM / LOW / INFO）",
        "",
    ])

    for sev in ["MEDIUM", "LOW", "INFO"]:
        if by_severity[sev]:
            lines.append(f"### {sev} 级别\n")
            for f in by_severity[sev]:
                lines.extend([
                    f"- **{f['type']}**: {f.get('detail', f.get('matched_text', ''))[:200]}",
                    f"  - 状态：{f.get('resolution', '待确认')}",
                    "",
                ])

    if not any(by_severity[s] for s in ["MEDIUM", "LOW", "INFO"]):
        lines.append("*（无中低风险发现）*\n")

    # 附录：自动扫描
    if pattern_findings or rl_findings:
        lines.extend([
            "---",
            "## 附录：自动扫描发现",
            "",
        ])
        if pattern_findings:
            lines.append("**代码风险模式匹配**：")
            for f in pattern_findings:
                lines.append(f"  - [{f['severity']}] {f['type']} — `{f.get('matched_text', '')[:80]}` @ {f.get('file', '?')}")
            lines.append("")
        if rl_findings:
            lines.append("**RL 红线合规**：")
            for f in rl_findings:
                lines.append(f"  - [{f['severity']}] {f['type']}: {f.get('detail', '')[:100]}")
            lines.append("")

    lines.extend([
        "---",
        "## Nexad 实践映射",
        "",
        f"| 发现 | 对应 Nexad 实践 | 严重性 |",
        f"|------|----------------|--------|",
    ])

    # Nexad 映射
    nexad_map = {
        "不可逆决策审查": ("Marketing Agent Harness", "不可逆性决定严格度"),
        "RL-C01 编译合规": ("RL-C01 编译必须通过", "Self-evaluation 失效"),
        "RL-C03 先看后写": ("RL-C03 先看后写", "Main Agent 合理化问题"),
        "并发攻击面": ("Marketing Agent Harness", "Bug × 真实金钱"),
    }

    for f in by_severity["CRITICAL"] + by_severity["HIGH"]:
        mapped = nexad_map.get(f["type"], ("—", "—"))
        lines.append(f"| {f['type']} | {mapped[0]} | {f['severity']} |")

    lines.extend([
        "",
        "---",
        "",
        f"*本报告由 reviewer_agent.py 生成（独立 Session）| {datetime.now().isoformat()}*",
    ])

    return "\n".join(lines)


# =============================================================================
# CLI
# =============================================================================

def find_spec_output(cr_dir: Path) -> Path | None:
    """查找 spec-output.json"""
    candidates = [
        cr_dir / "spec-output.json",
        cr_dir.parent / "spec-output.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def find_cr_dir(cr_id: str) -> Path | None:
    """查找 CR 目录"""
    repo = Path.cwd()
    candidates = [
        repo / "DeliverHQ" / "change-requests" / cr_id,
        repo / "change-requests" / cr_id,
        repo / cr_id,
    ]
    for p in candidates:
        if p.exists() and p.is_dir():
            return p
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Reviewer Agent — 独立 Session 审查",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Nexad 核心原则：Reviewer Agent 从独立 Session 启动，只拿 SpecGate 结构化输出。

用法：
  python reviewer_agent.py CR-001
  python reviewer_agent.py CR-001 --output evidence/adversarial_review_report.md
  python reviewer_agent.py CR-001 --check-only  # 仅验证报告是否存在且 verdict=PASS

前置条件：
  CR 目录下必须有 spec-output.json（由 SpecGate 生成）
        """
    )
    parser.add_argument("cr_id", help="CR 编号，如 CR-001")
    parser.add_argument("--output", default=DEFAULT_REPORT, help="报告输出路径")
    parser.add_argument("--scope", default=".", help="审查范围（git diff scope）")
    parser.add_argument("--check-only", action="store_true",
                        help="仅验证报告是否存在且 verdict=PASS")
    parser.add_argument("--skip-scan", action="store_true",
                        help="跳过正则扫描，只做 RL 合规和第一性原理检查")

    args = parser.parse_args()

    cr_id = args.cr_id

    # 查找 CR 目录
    cr_dir = find_cr_dir(cr_id)
    if not cr_dir:
        print(f"❌ 未找到 CR 目录：{cr_id}")
        print(f"搜索路径：")
        for p in [
            Path.cwd() / "DeliverHQ" / "change-requests" / cr_id,
            Path.cwd() / "change-requests" / cr_id,
            Path.cwd() / cr_id,
        ]:
            print(f"  - {p} ({'存在' if p.exists() else '不存在'})")
        sys.exit(1)

    repo_root = get_repo_root(cr_dir)

    # 加载 tier 配置
    tier_config = load_tier_config()
    tier = spec.get("governance", {}).get("tier", "T2")
    tier_info = tier_config.get(tier, tier_config.get("T2", {}))
    check_depth = tier_info.get("check_depth", {"adversarial_review": "full", "risk_scan": "standard", "llm_review": False})

    # check-only 模式
    if args.check_only:
        report_path = cr_dir / args.output
        if not report_path.exists():
            print(f"❌ 报告不存在：{report_path}")
            sys.exit(1)
        content = report_path.read_text(encoding="utf-8")
        # 解析 verdict
        m = re.search(r"verdict[*_]*\s*:\s*(PASS|FAIL)", content, re.IGNORECASE)
        if m and m.group(1) == "PASS":
            print(f"✅ Reviewer Agent PASS（{report_path}）")
            # 检查 blocking
            block_m = re.search(r"blocking_findings[*_]*\s*:\s*(\d+)", content, re.IGNORECASE)
            if block_m:
                blocking = int(block_m.group(1))
                if blocking > 0:
                    print(f"⚠️  但有 {blocking} 个未解决的 blocking findings")
            sys.exit(0)
        elif m and m.group(1) == "FAIL":
            print(f"❌ Reviewer Agent FAIL — blocking_findings > 0")
            # 列出 blocking
            blockings = re.findall(r"###\s+\[.*?\]\s+(.*?)\s+\[.*?\]", content)
            if blockings:
                print(f"   blocking findings:")
                for b in blockings[:5]:
                    print(f"   - {b.strip()}")
            sys.exit(1)
        else:
            print(f"⚠️  报告存在但无法解析 verdict")
            sys.exit(1)

    # 加载 spec-output.json
    spec_path = find_spec_output(cr_dir)
    if not spec_path:
        print(f"❌ 未找到 spec-output.json（CR 目录下需有 SpecGate 产物）")
        print(f"  请先运行 SpecGate 生成 spec-output.json")
        sys.exit(1)

    spec = load_spec_output(spec_path)
    if not spec:
        print(f"❌ spec-output.json 解析失败")
        sys.exit(1)

    print(f"🔍 Reviewer Agent 开始审查 {cr_id}...")
    print(f"   spec-output: {spec_path}")
    print(f"   repo root: {repo_root}")

    # 获取 diff
    diff_text = get_git_diff(repo_root, args.scope)
    changed_files = get_changed_files(repo_root, args.scope)

    if not changed_files:
        print(f"⚠️  未发现改动文件（scope={args.scope}），请确认 CR 是否已实现")
        sys.exit(1)

    tier = spec.get("governance", {}).get("tier", "T2")
    print(f"   改动文件：{len(changed_files)} 个")
    print(f"   Delivery Tier: {tier}")

    # 审查（按 tier check_depth 控制深度）
    adversarial_depth = check_depth.get("adversarial_review", "full")
    risk_depth = check_depth.get("risk_scan", "standard")

    # T3 不做对抗式审查
    if adversarial_depth == "none":
        print(f"   对抗式审查：跳过（Tier={tier}，check_depth=none）")
        pattern_findings = []
        rl_findings = []
        fp_findings = []
        malicious_findings = []
    else:
        # risk_scan 深度
        if risk_depth in ("none", "basic") or args.skip_scan:
            print(f"   风险模式扫描：跳过（Tier={tier}，check_depth={risk_depth}）")
            pattern_findings = []
        else:
            pattern_findings = scan_code_patterns(diff_text)
            print(f"   风险模式扫描：{len(pattern_findings)} 个")

        # RL 红线（RL-C01 永远检查）
        rl_findings = check_rl_compliance(diff_text, spec, changed_files)
        print(f"   RL 红线检查：{len(rl_findings)} 个")

        # adversarial_review 深度
        if adversarial_depth == "fast":
            print(f"   第一性原理审查：跳过（Tier={tier}，check_depth=fast）")
            fp_findings = []
            malicious_findings = []
        else:
            fp_findings = first_principles_review(diff_text, spec, changed_files)
            print(f"   第一性原理审查：{len(fp_findings)} 个")

            malicious_findings = malicious_user_review(diff_text, spec, changed_files)
            print(f"   恶意用户审查：{len(malicious_findings)} 个")

    # 生成报告
    report = generate_report(
        cr_id=cr_id,
        spec=spec,
        changed_files=changed_files,
        diff_text=diff_text,
        pattern_findings=pattern_findings,
        rl_findings=rl_findings,
        fp_findings=fp_findings,
        malicious_findings=malicious_findings,
        tier=tier,
    )

    # 写报告
    report_path = cr_dir / args.output
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"\n📄 报告已生成：{report_path}")

    # verdict 摘要
    all_f = pattern_findings + rl_findings + fp_findings + malicious_findings
    verdict, blocking, _ = compute_verdict(all_f)
    print(f"\n{'✅' if verdict == 'PASS' else '❌'} verdict: {verdict}")
    print(f"   blocking_findings: {blocking}")
    print(f"   总发现: {len(all_f)}")

    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
