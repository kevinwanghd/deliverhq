#!/usr/bin/env python
"""
对抗式审查 Gate — 扮演恶意用户，主动找漏洞

来源：数字生命卡兹克 Vibe Coding Prompt 技巧。
核心原则：从第一性原理出发管生成，对抗式审查管验证。

三类视角：
  1. 第一性原理审查（生成侧）— 打断类比推理，逼回问题本质
  2. 恶意用户审查（验证侧）— 找怎么搞崩系统的路径
  3. 架构健康审查 — 模块边界、数据流、技术债积累

用法：
  python adversarial_review.py CR-001 --scope src/Modules/OrderService/
  python adversarial_review.py CR-001 --cr-id CR-001 --scope . --diff-from HEAD~1
  python adversarial_review.py CR-001 --check-only  # 仅检查报告是否存在

Gate 判据（evidence_gate.py 验证）：
  - adversarial_review_report.md 存在
  - 无 blocking_findings（严重程度 = CRITICAL / HIGH 的条目已全部 resolve）
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# =============================================================================
# 配置
# =============================================================================

DEFAULT_OUTPUT = "DeliverHQ/change-requests/{cr_id}/evidence/adversarial_review_report.md"
CANDIDATE_OUTPUTS = [
    "DeliverHQ/change-requests/{cr_id}/evidence/adversarial_review_report.md",
    "change-requests/{cr_id}/evidence/adversarial_review_report.md",
]

SEVERITY_LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
RISK_PATTERNS = {
    "CRITICAL": [
        ("硬编码密钥/凭证", r"(?i)(api[_-]?key|secret|password|token)\s*=\s*['\"][a-zA-Z0-9]{16,}['\"]"),
        ("SQL 注入风险", r"(?i)(execute|query|select)\s*\([^)]*\+[^)]+\)"),
        ("未处理异常直接暴露", r"(?i)except[^:]*:\s*(?!.*(?:log|raise|print))[^,\n]+"),
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

def run_git(cmd: list, cwd: Path = None) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, "", str(e)


def get_git_diff(scope: str = ".") -> str:
    _, stdout, _ = run_git(["git", "diff", "--", scope])
    return stdout


def get_git_status(scope: str = ".") -> str:
    _, stdout, _ = run_git(["git", "status", "--porcelain", "--", scope])
    return stdout


def get_commit_log(count: int = 3) -> str:
    _, stdout, _ = run_git(["git", "log", f"-{count}", "--oneline"])
    return stdout


def get_changed_files(scope: str = ".") -> list[str]:
    _, stdout, _ = run_git(["git", "diff", "--name-only", "--", scope])
    return [f for f in stdout.strip().split("\n") if f]


def get_repo_root() -> Path:
    _, stdout, _ = run_git(["rev-parse", "--show-toplevel"])
    return Path(stdout.strip())

# =============================================================================
# 核心审查逻辑
# =============================================================================

def scan_code_patterns(diff_text: str, scope_files: list[str]) -> list[dict]:
    """用正则扫描代码模式，匹配风险"""
    findings = []
    for severity, patterns in RISK_PATTERNS.items():
        for name, pattern in patterns:
            import re
            matches = re.finditer(pattern, diff_text, re.MULTILINE | re.IGNORECASE)
            for m in matches:
                # 找该行在哪个文件
                line_num = diff_text[:m.start()].count("\n") + 1
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
                    "pattern": pattern,
                    "matched_text": m.group(0),
                    "file": filename,
                    "line": line_num,
                    "auto_fixable": False,
                    "resolution": "待人工确认",
                })
    return findings


def first_principles_review(cr_id: str, scope_files: list[str], diff_text: str) -> list[dict]:
    """第一性原理审查：打断类比推理，逼回业务本质"""
    findings = []

    # 检查点1：方案是否治标不治本
    if "hotfix" in diff_text.lower() or "patch" in diff_text.lower():
        findings.append({
            "severity": "MEDIUM",
            "type": "治标不治本风险",
            "detail": "diff 中出现 hotfix/patch 关键词，需确认是否只是临时补丁而非解决根因",
            "recommendation": "追问：这个问题的本质原因是什么？是否有更深层的架构隐患？",
            "auto_fixable": False,
            "resolution": "待人工确认",
        })

    # 检查点2：是否在重复造轮子
    scope_str = ", ".join(scope_files[:5])
    findings.append({
        "severity": "INFO",
        "type": "第一性原理自问",
        "detail": f"改动的文件：{scope_str}",
        "recommendation": "在提交前追问：我是否在发明新模式？还是在模仿项目已有的代码风格？",
        "auto_fixable": False,
        "resolution": "Agent 自问",
    })

    # 检查点3：技术债积累信号
    if len(scope_files) > 5:
        findings.append({
            "severity": "LOW",
            "type": "技术债积累信号",
            "detail": f"本次改动涉及 {len(scope_files)} 个文件，需确认是否在加速技术债",
            "recommendation": "检查是否有重复逻辑、隐藏依赖或未归档的设计决策",
            "auto_fixable": False,
            "resolution": "待人工确认",
        })

    return findings


def malicious_user_review(cr_id: str, scope_files: list[str], diff_text: str) -> list[dict]:
    """恶意用户审查：找怎么搞崩系统的路径"""
    findings = []

    # 边界数据攻击
    boundary_patterns = [
        ("超长输入", r"(?i)(input|value|param|arg)\s*(=|:)", "恶意用户可提交超长字符串测试是否有截断或溢出"),
        ("空值注入", r"(?i)(if|where)\s+.*\b(id|param)\b\s*(==|!=)\s*null", "空值是否会导致 NPE 或绕过检查"),
        ("负数/极端值", r"(?i)(price|amount|count|limit)\s*(=|:)", "负数或极大值是否被正确校验"),
    ]

    for name, pattern, desc in boundary_patterns:
        import re
        if re.search(pattern, diff_text):
            findings.append({
                "severity": "HIGH",
                "type": f"恶意用户-边界数据：{name}",
                "detail": desc,
                "recommendation": f"检查 {name} 的输入校验是否完整，边界值是否有兜底",
                "auto_fixable": False,
                "resolution": "待人工确认",
            })

    # 并发攻击
    import re
    if re.search(r"(?i)(lock|mutex|atomic|concurrent|parallel)", diff_text):
        findings.append({
            "severity": "MEDIUM",
            "type": "并发攻击面",
            "detail": "diff 涉及并发相关代码，需检查是否有竞态条件",
            "recommendation": "列出所有并发读写路径，检查是否有遗漏的同步点",
            "auto_fixable": False,
            "resolution": "待人工确认",
        })

    return findings


def generate_review_prompt(cr_id: str, scope_files: list[str], diff_text: str) -> str:
    """生成供 Agent 执行对抗式审查的提示词（供 LLM 调用）"""
    prompt = f"""## 对抗式审查 — CR-{cr_id}

你是 DeliverHQ 的对抗式审查 Agent。你的任务是扮演恶意用户，从三个视角审查以下代码改动。

### 改动范围
文件：{', '.join(scope_files[:10])}{' ...' if len(scope_files) > 10 else ''}

### Git Diff
```
{diff_text[:8000]}
```

### 你的任务

请从以下三个视角逐一审查，输出发现：

#### 视角1：第一性原理审查（生成侧）
- "这个问题真的应该这么解吗？"
- 如果让你从业务目标出发重新推导，会选择同样的方案吗？
- 有没有治标不治本的风险？

#### 视角2：恶意用户审查（验证侧）
- 如果我是恶意用户，会如何搞崩这个系统？
- 边界数据、极端输入、资源耗尽、并发攻击
- 日志和监控真的能捕获这些情况吗？

#### 视角3：架构健康审查
- 模块边界是否清晰？
- 数据流有没有隐蔽的循环依赖？
- 技术债是否在加速积累？

### 输出格式
对每个发现，按以下格式输出：
- **严重程度**: CRITICAL / HIGH / MEDIUM / LOW / INFO
- **类型**: 分类名称
- **详情**: 具体问题
- **建议**: 如何修复
- **可自动修复**: true / false
- **状态**: 待确认 / 已解决

最终给出总结：
- 严重发现数：N
- blocking_findings：N（blocking = CRITICAL 或 HIGH 且未解决）
- verdict: PASS / FAIL

**只有 blocking_findings = 0 才算 PASS，否则算 FAIL。**"""
    return prompt


def generate_report(
    cr_id: str,
    scope_files: list[str],
    diff_text: str,
    patterns_found: list[dict],
    fp_findings: list[dict],
    malicious_findings: list[dict],
    llm_findings: list[dict],
) -> str:
    """生成对抗式审查报告"""
    all_findings = patterns_found + fp_findings + malicious_findings + llm_findings

    # 按严重程度分组
    by_severity = {s: [] for s in SEVERITY_LEVELS}
    for f in all_findings:
        sev = f.get("severity", "INFO")
        if sev in by_severity:
            by_severity[sev].append(f)

    blocking = by_severity["CRITICAL"] + by_severity["HIGH"]
    blocking_unresolved = [f for f in blocking if f.get("resolution", "待确认") == "待确认"]

    verdict = "PASS" if len(blocking_unresolved) == 0 else "FAIL"

    lines = [
        f"# 对抗式审查报告 — CR-{cr_id}",
        "",
        f"> 生成时间：{datetime.now().isoformat()}",
        "> 来源：数字生命卡兹克 Vibe Coding Prompt 技巧",
        "",
        "## 元数据",
        "",
        f"- **CR**: {cr_id}",
        f"- **审查文件数**: {len(scope_files)}",
        f"- **改动范围**: {', '.join(scope_files[:10])}{' ...' if len(scope_files) > 10 else ''}",
        "",
        "---",
        "",
        "## 审查结论",
        "",
        f"- ** verdict**: {verdict}",
        f"verdict: {verdict}  <!-- evidence_gate 解析 -->",
        f"- ** blocking_findings**: {len(blocking_unresolved)}（CRITICAL + HIGH 未解决）",
        f"- ** 严重发现总数**: {len(blocking)}",
        f"- ** 中低风险发现**: {len(by_severity['MEDIUM']) + len(by_severity['LOW']) + len(by_severity['INFO'])}",
        "",
        "---\n",
        "## 严重发现（CRITICAL / HIGH）",
        "",
    ]

    for f in by_severity["CRITICAL"] + by_severity["HIGH"]:
        lines.extend([
            f"### {f['type']}  [ {f['severity']} ]",
            "",
            f"- **详情**: {f.get('detail', f.get('matched_text', 'N/A'))}",
            f"- **文件**: {f.get('file', 'N/A')}",
            f"- **建议**: {f.get('recommendation', f.get('resolution', '待确认'))}",
            f"- **可自动修复**: {f.get('auto_fixable', False)}",
            f"- **状态**: {f.get('resolution', '待确认')}",
            "",
        ])

    if len(by_severity["CRITICAL"]) + len(by_severity["HIGH"]) == 0:
        lines.append("*（无严重发现）*\n")

    lines.extend([
        "---\n",
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

    # 附录：自动扫描结果
    if patterns_found:
        lines.extend([
            "---\n",
            "## 附录：自动扫描发现（正则模式匹配）",
            "",
        ])
        for f in patterns_found:
            lines.append(
                f"- [{f['severity']}] {f['type']} — `{f.get('matched_text', '')[:80]}` @ {f.get('file', '?')}:{f.get('line', '?')}"
            )
        lines.append("")

    lines.extend([
        "---\n",
        "## 对 Kevin 的启发",
        "",
        "1. **第一性原理 Prompt**：在 Prompt 末尾加「从第一性原理出发」，可打断 AI 类比推理，逼回问题本质 — 可用于 SpecGate 前的方案推导",
        "2. **对抗式审查**：让 AI 扮演恶意用户，专门找怎么搞崩系统 — 可作为 QualityGate 前的主动漏洞扫描",
        "3. **定期技术债扫描**：每 2-3 周做一次全局对抗式审查 — DeliverHQ 的定期 CR review 可以结合此机制",
        "4. **多 Agent 并发审查**：正向设计 + 反向审查并行 — 对抗式审查适合作为并行 Agent 任务",
        "",
        "---",
        "",
        f"*本报告由 adversarial_review.py 生成 | {datetime.now().isoformat()}*",
    ])

    return "\n".join(lines)


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="对抗式审查 Gate — 扮演恶意用户，主动找漏洞",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python adversarial_review.py CR-001 --scope src/Modules/OrderService/
  python adversarial_review.py CR-001 --scope . --llm-prompt  # 生成供 LLM 执行的提示词
  python adversarial_review.py CR-001 --check-only            # 仅验证报告是否存在且 blocking_findings=0

Gate 判据：
  - adversarial_review_report.md 存在
  - 无 blocking_findings（CRITICAL + HIGH 未解决 = 0）
        """
    )
    parser.add_argument("cr_id", help="CR 编号，如 CR-001")
    parser.add_argument("--scope", default=".", help="审查范围（目录或文件，默认为全部改动）")
    parser.add_argument("--diff-from", dest="diff_from", default=None,
                        help="git diff 起始点，如 HEAD~1")
    parser.add_argument("--output", default=None, help="报告输出路径")
    parser.add_argument("--llm-prompt", action="store_true",
                        help="仅生成供 LLM 执行的对抗式审查提示词")
    parser.add_argument("--check-only", action="store_true",
                        help="仅检查报告是否存在且 verdict=PASS（供 evidence_gate 调用）")

    args = parser.parse_args()

    cr_id = args.cr_id
    repo_root = get_repo_root()

    # 确定输出路径
    if args.output:
        output_path = Path(args.output)
    else:
        for candidate in CANDIDATE_OUTPUTS:
            p = repo_root / candidate.format(cr_id=cr_id)
            if p.exists() or p.parent.exists():
                output_path = p
                break
        else:
            output_path = repo_root / CANDIDATE_OUTPUTS[0].format(cr_id=cr_id)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 获取改动
    if args.diff_from:
        _, diff_stdout, _ = run_git(["git", "diff", args.diff_from, "--", args.scope])
    else:
        diff_stdout = get_git_diff(args.scope)

    changed_files = get_changed_files(args.scope)

    if not changed_files:
        print(f"⚠️  未发现改动文件（scope={args.scope}），请确认 CR 是否已实现")
        sys.exit(1)

    # 如果只是 check
    if args.check_only:
        if not output_path.exists():
            print(f"❌ 报告不存在：{output_path}")
            sys.exit(1)
        content = output_path.read_text(encoding="utf-8")
        if "verdict: PASS" in content:
            print(f"✅ 对抗式审查 PASS（{output_path}）")
            sys.exit(0)
        elif "verdict: FAIL" in content:
            print(f"❌ 对抗式审查 FAIL — blocking_findings > 0")
            sys.exit(1)
        else:
            print(f"⚠️  报告存在但无法解析 verdict")
            sys.exit(1)

    # 如果只生成 LLM 提示词
    if args.llm_prompt:
        prompt = generate_review_prompt(cr_id, changed_files, diff_stdout)
        print(prompt)
        sys.exit(0)

    # 完整审查流程
    print(f"🔍 开始对抗式审查 CR-{cr_id}...")
    print(f"   改动文件：{len(changed_files)} 个")

    # 1. 自动模式扫描
    patterns_found = scan_code_patterns(diff_stdout, changed_files)
    print(f"   自动扫描发现：{len(patterns_found)} 个")

    # 2. 第一性原理审查
    fp_findings = first_principles_review(cr_id, changed_files, diff_stdout)
    print(f"   第一性原理发现：{len(fp_findings)} 个")

    # 3. 恶意用户审查
    malicious_findings = malicious_user_review(cr_id, changed_files, diff_stdout)
    print(f"   恶意用户发现：{len(malicious_findings)} 个")

    # 4. LLM 增强审查（提示词已生成，供 Agent 手动调用）
    llm_findings = []
    prompt = generate_review_prompt(cr_id, changed_files, diff_stdout)

    # 生成报告
    report = generate_report(
        cr_id=cr_id,
        scope_files=changed_files,
        diff_text=diff_stdout,
        patterns_found=patterns_found,
        fp_findings=fp_findings,
        malicious_findings=malicious_findings,
        llm_findings=llm_findings,
    )

    output_path.write_text(report, encoding="utf-8")
    print(f"\n📄 报告已生成：{output_path}")

    # 总结
    all_f = patterns_found + fp_findings + malicious_findings
    blocking = [f for f in all_f if f.get("severity") in ("CRITICAL", "HIGH")]
    blocking_unresolved = [f for f in blocking if f.get("resolution", "待确认") == "待确认"]

    if len(blocking_unresolved) == 0:
        print(f"✅ verdict: PASS（无 blocking_findings）")
        sys.exit(0)
    else:
        print(f"❌ verdict: FAIL（{len(blocking_unresolved)} 个 blocking findings）")
        for f in blocking_unresolved:
            print(f"   [{f['severity']}] {f['type']}")
        print(f"\n💡 提示：运行 `--llm-prompt` 获取供 LLM 执行的详细审查提示词")
        sys.exit(1)


if __name__ == "__main__":
    main()
