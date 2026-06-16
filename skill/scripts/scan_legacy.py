#!/usr/bin/env python3
"""
scan_legacy.py —— 老项目逆向扫描（目标2 的客观层引擎）

职责：扫描老项目源码，用**客观数据**填写 reverse-spec-candidates.yml 的客观层，
并由客观风险信号推导 review_required —— 不依赖 AI 的主观置信度。

关键设计（对抗"AI 自信但错了"的盲区）：
  review_required 由以下客观信号触发，AI 无权降级：
    - test_coverage == none        （无测试 = 没人验证过它该干嘛）
    - sensitive_domain 非空         （auth/payment/data/permission/...）
    - complexity == high
    - change_frequency == high      （来自 git 历史，频繁改动 = 不稳定）

本脚本只填客观层与 review_required；推断层（inferred_behavior 等）留给 AI 后续填写。

跨平台：纯 pathlib + 标准库；git 不可用时优雅降级（change_frequency=unknown）。
Python 3.6 兼容。

用法：
  python scan_legacy.py <项目源码目录> [--out <输出yml>] [--report <报告md>]
  python scan_legacy.py /path/to/legacy/src --out change-requests/CR-XXX/reverse-spec-candidates.yml
"""

import argparse
import ast
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("需要 PyYAML：pip install PyYAML")
    sys.exit(2)


# ── 敏感域关键词（模块路径/文件名命中即标记）──────────────────────
SENSITIVE_DOMAINS = {
    "auth": ["auth", "login", "session", "token", "oauth", "credential", "signin", "signup"],
    "payment": ["payment", "billing", "invoice", "charge", "refund", "checkout", "wallet"],
    "data": ["database", "migration", "schema", "repository", "dao", "orm"],
    "permission": ["permission", "acl", "role", "rbac", "authorize", "access_control"],
    "crypto": ["crypto", "encrypt", "decrypt", "hash", "secret", "cipher", "signature"],
    "external": ["webhook", "external", "third_party", "integration", "api_client"],
}

# 支持的源码扩展名 -> 技术栈
EXT_LANG = {
    ".py": "python", ".js": "node", ".ts": "node", ".jsx": "node", ".tsx": "node",
    ".java": "java", ".go": "go", ".rb": "ruby", ".php": "php",
    ".cs": "dotnet", ".rs": "rust", ".kt": "kotlin",
}

SKIP_DIRS = {".git", "__pycache__", "node_modules", "venv", ".venv", "dist",
             "build", "target", ".idea", ".vscode", "vendor", ".tox", "coverage"}

# 复杂度阈值（基于分支/嵌套近似圈复杂度）
COMPLEXITY_HIGH = 15
COMPLEXITY_MED = 8


def detect_tech_stack(root):
    """统计源码扩展名，返回主技术栈。"""
    counts = {}
    for path in root.rglob("*"):
        if path.is_dir() or any(p in SKIP_DIRS for p in path.parts):
            continue
        lang = EXT_LANG.get(path.suffix.lower())
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return "unknown", counts
    primary = max(counts, key=counts.get)
    return primary, counts


def find_source_files(root, lang):
    """收集主技术栈的源码文件（排除测试文件本身）。"""
    exts = [e for e, l in EXT_LANG.items() if l == lang]
    files = []
    for path in root.rglob("*"):
        if path.is_dir() or any(p in SKIP_DIRS for p in path.parts):
            continue
        if path.suffix.lower() in exts and not _is_test_file(path):
            files.append(path)
    return files


def _is_test_file(path):
    name = path.name.lower()
    parts = [p.lower() for p in path.parts]
    return (name.startswith("test_") or name.endswith("_test.py")
            or ".test." in name or ".spec." in name
            or "test" in parts or "tests" in parts or "__tests__" in parts)


def find_test_files(root):
    """收集所有测试文件，返回其文本内容拼接（用于覆盖判断）。"""
    tests = []
    for path in root.rglob("*"):
        if path.is_dir() or any(p in SKIP_DIRS for p in path.parts):
            continue
        if _is_test_file(path) and path.suffix.lower() in EXT_LANG:
            tests.append(path)
    return tests


def estimate_py_complexity(tree):
    """近似圈复杂度：分支/循环/布尔运算/异常处理节点计数。"""
    score = 1
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler,
                             ast.With, ast.Assert)):
            score += 1
        elif isinstance(node, ast.BoolOp):
            score += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            score += 1
    return score


def complexity_label(score):
    if score >= COMPLEXITY_HIGH:
        return "high"
    if score >= COMPLEXITY_MED:
        return "medium"
    return "low"


def detect_sensitive_domain(path):
    """根据路径/文件名命中敏感域关键词。"""
    text = str(path).lower()
    hits = []
    for domain, kws in SENSITIVE_DOMAINS.items():
        if any(kw in text for kw in kws):
            hits.append(domain)
    return hits


def test_coverage_for(module_name, test_files_text):
    """粗粒度覆盖判断：测试文本里是否提及模块/函数名。

    返回 none|partial（无法精确测 full，保守标 partial）。
    """
    if not test_files_text:
        return "none"
    if module_name and module_name.lower() in test_files_text.lower():
        return "partial"
    return "none"


def git_change_frequency(root, file_path):
    """用 git log 统计文件改动次数 -> 频率标签。git 不可用则 unknown。"""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "log", "--oneline", "--", str(file_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=15,
        )
        if result.returncode != 0:
            return "unknown"
        commits = len([l for l in result.stdout.splitlines() if l.strip()])
        if commits == 0:
            return "unknown"
        if commits >= 10:
            return "high"
        if commits >= 4:
            return "medium"
        return "low"
    except Exception:
        return "unknown"


def derive_review_required(risk_signals, contradicting_tests):
    """核心：由客观信号推导 review_required（AI 无权降级）。"""
    reasons = []
    if risk_signals["test_coverage"] == "none":
        reasons.append("无测试覆盖")
    if risk_signals["sensitive_domain"]:
        reasons.append("%s 敏感域" % "/".join(risk_signals["sensitive_domain"]))
    if risk_signals["complexity"] == "high":
        reasons.append("高复杂度")
    if risk_signals["change_frequency"] == "high":
        reasons.append("高频改动")
    if contradicting_tests:
        reasons.append("与现有测试矛盾")
    return (len(reasons) > 0), reasons


def build_candidate(idx, path, root, test_text):
    """为单个源码文件构造一个候选条目（仅填客观层 + review_required）。"""
    rel = path.relative_to(root)
    module = path.stem
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        loc = len([l for l in text.splitlines() if l.strip()])
    except Exception:
        loc = 0

    # 复杂度（仅 Python 用 AST，其它语言用行数近似）
    complexity = "unknown"
    functions = []
    if path.suffix.lower() == ".py":
        try:
            tree = ast.parse(text)
            complexity = complexity_label(estimate_py_complexity(tree))
            functions = [n.name for n in ast.walk(tree)
                         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))][:10]
        except Exception:
            complexity = "unknown"
    else:
        if loc > 300:
            complexity = "high"
        elif loc > 120:
            complexity = "medium"
        elif loc > 0:
            complexity = "low"

    risk_signals = {
        "test_coverage": test_coverage_for(module, test_text),
        "complexity": complexity,
        "sensitive_domain": detect_sensitive_domain(path),
        "change_frequency": git_change_frequency(root, rel),
        "loc": loc,
    }
    review_required, reasons = derive_review_required(risk_signals, [])

    return {
        "id": "RC-%03d" % idx,
        "title": "模块 %s 的行为" % module,
        "source": {
            "files": [str(rel).replace("\\", "/")],
            "functions": functions,
            "module": module,
        },
        "risk_signals": risk_signals,
        "inferred_behavior": "{{AI 待填：从代码推断该模块的行为}}",
        "confidence": "low",
        "assumptions": [],
        "evidence": {"supporting_tests": [], "contradicting_tests": []},
        "review_required": review_required,
        "review_reason": reasons,
        "human_decision": {
            "status": "unconfirmed",
            "is_real_requirement": None,
            "decided_by": "",
            "date": "",
            "note": "",
        },
        "becomes_acceptance_criteria": None,
    }


def write_report(report_path, project_name, root, tech_stack, lang_counts, candidates):
    """生成人类可读的 Markdown 报告（只读视图）。"""
    total = len(candidates)
    need_review = [c for c in candidates if c["review_required"]]
    sensitive = [c for c in candidates if c["risk_signals"]["sensitive_domain"]]
    no_test = [c for c in candidates if c["risk_signals"]["test_coverage"] == "none"]

    lines = []
    lines.append("# 老项目逆向扫描报告")
    lines.append("")
    lines.append("> 由 scan_legacy.py 生成（客观数据）。推断层与裁决层待 AI/人工补充。")
    lines.append("")
    lines.append("## 执行信息")
    lines.append("- 项目：%s" % project_name)
    lines.append("- 扫描根目录：%s" % root)
    lines.append("- 主技术栈：%s" % tech_stack)
    lines.append("- 语言分布：%s" % ", ".join("%s=%d" % (k, v) for k, v in sorted(lang_counts.items())))
    lines.append("- 扫描时间：%s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("")
    lines.append("## 风险概览")
    lines.append("")
    lines.append("| 指标 | 数量 | 占比 |")
    lines.append("|---|---|---|")
    pct = lambda n: ("%.0f%%" % (100.0 * n / total)) if total else "0%"
    lines.append("| 候选条目总数 | %d | 100%% |" % total)
    lines.append("| **需人工确认** (review_required) | %d | %s |" % (len(need_review), pct(len(need_review))))
    lines.append("| 敏感域模块 | %d | %s |" % (len(sensitive), pct(len(sensitive))))
    lines.append("| 无测试覆盖 | %d | %s |" % (len(no_test), pct(len(no_test))))
    lines.append("")
    lines.append("## 需人工确认的高风险模块")
    lines.append("")
    if need_review:
        lines.append("| ID | 模块 | 风险原因 | 测试 | 复杂度 |")
        lines.append("|---|---|---|---|---|")
        for c in need_review:
            rs = c["risk_signals"]
            lines.append("| %s | %s | %s | %s | %s |" % (
                c["id"], c["source"]["module"],
                "；".join(c["review_reason"]),
                rs["test_coverage"], rs["complexity"]))
    else:
        lines.append("（无）")
    lines.append("")
    lines.append("## 下一步")
    lines.append("")
    lines.append("1. AI 为每个候选填写推断层（inferred_behavior / assumptions / evidence）")
    lines.append("2. 人工逐条裁决 review_required 条目（confirm/modify/reject），回答 is_real_requirement")
    lines.append("3. 运行 ReverseSpecGate 确认无 unconfirmed 高风险条目")
    lines.append("4. 运行 reverse_to_spec.py 转化为 acceptance-spec.md + traceability.yml")
    lines.append("")
    lines.append("**报告由客观数据驱动；review_required 不可由 AI 主观降级。**")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="老项目逆向扫描（填客观层 + 推导 review_required）")
    parser.add_argument("scan_root", help="老项目源码目录")
    parser.add_argument("--out", default="reverse-spec-candidates.yml", help="输出 YAML 路径")
    parser.add_argument("--report", default=None, help="可选：Markdown 报告路径")
    parser.add_argument("--max-files", type=int, default=200, help="最多扫描文件数（防超大仓库）")
    args = parser.parse_args()

    root = Path(args.scan_root).resolve()
    if not root.exists():
        print("扫描目录不存在：%s" % root)
        sys.exit(1)

    tech_stack, lang_counts = detect_tech_stack(root)
    if tech_stack == "unknown":
        print("未识别到支持的源码文件，无法扫描。")
        sys.exit(1)

    print("主技术栈：%s" % tech_stack)
    source_files = find_source_files(root, tech_stack)[: args.max_files]
    test_files = find_test_files(root)
    test_text = ""
    for tf in test_files:
        try:
            test_text += tf.read_text(encoding="utf-8", errors="ignore") + "\n"
        except Exception:
            pass

    print("源码文件：%d  测试文件：%d" % (len(source_files), len(test_files)))

    candidates = []
    for i, sf in enumerate(source_files, 1):
        candidates.append(build_candidate(i, sf, root, test_text))

    doc = {
        "schema": "deliverhq-reverse-spec",
        "version": 1,
        "project": {
            "name": root.name,
            "scanned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "scan_root": str(root),
            "tech_stack": tech_stack,
        },
        "candidates": candidates,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        try:
            yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False)
        except TypeError:
            yaml.safe_dump(doc, f, allow_unicode=True)

    need_review = sum(1 for c in candidates if c["review_required"])
    print("已生成 %d 个候选，其中 %d 个需人工确认 -> %s" % (len(candidates), need_review, out_path))

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        write_report(report_path, root.name, root, tech_stack, lang_counts, candidates)
        print("报告 -> %s" % report_path)


if __name__ == "__main__":
    main()
