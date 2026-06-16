#!/usr/bin/env python3
"""
WritebackGate - 交付归档完整性检查
验证知识已沉淀到组织记忆，CR 已归档
"""

import sys
from pathlib import Path
import subprocess
import os

from cr_state import update_gate_from_result
from runtime_support import configure_console

# 定位 DeliverHQ 根目录（脚本在 DeliverHQ/scripts/ 下）
DELIVERHQ_ROOT = Path(__file__).parent.parent
configure_console()

class Color:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'


def detect_rules_writeback_intent(report_text):
    """Infer whether the writeback report claims new rules were produced."""
    lowered = report_text.lower()
    no_rules_markers = [
        "本次无新规则",
        "无新规则",
        "no new rules",
    ]
    has_rules_markers = [
        "docs/rules-candidates.md",
        "rules-candidates.md",
        "新增规则候选",
        "更新规则候选",
        "candidate rule",
        "proposed rule",
    ]

    if any(marker in lowered for marker in no_rules_markers):
        return "none"
    if any(marker in lowered for marker in has_rules_markers):
        return "candidate"
    return "unknown"


def candidate_rules_ready(candidate_path):
    """Validate that the candidate rules file exists and is not still template-only."""
    if not candidate_path.exists():
        return False, "docs/rules-candidates.md 不存在"

    content = candidate_path.read_text(encoding='utf-8')
    active_section = content.split("## Active Candidates", 1)[1] if "## Active Candidates" in content else content
    invalid_markers = [
        "<short title>",
        "CR-XXX",
        "<review finding, repeated bug, or quality failure>",
        "<rule text>",
        "<where this applies>",
    ]
    if any(marker in active_section for marker in invalid_markers):
        return False, "docs/rules-candidates.md 仍包含模板占位符"
    if "## Candidate Rule:" not in active_section:
        return False, "docs/rules-candidates.md 缺少候选规则条目"
    return True, ""

def check_git_merged(cr_path):
    """检查代码是否已合并（简化版：检查是否有未提交变更）"""
    try:
        # 从 DeliverHQ 根目录定位项目根目录
        PROJECT_ROOT = DELIVERHQ_ROOT.parent
        result = subprocess.run(
            ['git', '-C', str(PROJECT_ROOT), 'status', '--porcelain'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=5
        )
        uncommitted = result.stdout.strip()
        return len(uncommitted) == 0, uncommitted
    except:
        return None, "git 检查失败"

def check_writeback_gate(cr_path):
    """WritebackGate 检查"""
    print(f"{Color.BLUE}=== WritebackGate 检查 ==={Color.END}\n")

    writeback_path = Path(cr_path) / "writeback-report.md"

    if not writeback_path.exists():
        print(f"{Color.RED}✗ writeback-report.md 不存在{Color.END}")
        update_gate_from_result(
            Path(cr_path),
            'writeback',
            False,
            blockers=['缺少 writeback-report.md，Writeback Agent 未执行'],
            state_after_pass='archived',
            current_phase='writeback',
            current_owner='writeback-agent',
            next_required_gate='writeback',
            next_action='生成 writeback-report.md 后重新运行 WritebackGate',
        )
        return False, ["缺少 writeback-report.md，Writeback Agent 未执行"]

    blockers = []
    warnings = []

    # 检查 1: writeback-report.md 完整性
    content = writeback_path.read_text(encoding='utf-8')

    required_sections = ['## 归档日期', '## 代码变更', '## 文档更新', '## 知识沉淀', '## 可追溯性']
    missing_sections = [sec for sec in required_sections if sec not in content]

    if missing_sections:
        print(f"{Color.RED}✗ writeback-report.md 缺少必需章节: {missing_sections}{Color.END}")
        blockers.append(f"缺少章节: {', '.join(missing_sections)}")
    else:
        print(f"{Color.GREEN}✓ writeback-report.md 结构完整{Color.END}")

    if '{{' in content:
        print(f"{Color.RED}✗ writeback-report.md 包含未替换模板变量{Color.END}")
        blockers.append("包含模板变量，未填充实际内容")
    else:
        print(f"{Color.GREEN}✓ 无模板变量{Color.END}")

    # 检查 2: 代码归档（Git 状态）
    print(f"\n{Color.BLUE}[代码归档]{Color.END}")
    if os.environ.get('DELIVERHQ_SELFTEST', '0') == '1':
        print(f"{Color.BLUE}ℹ selftest/dry-run 模式跳过 Git 工作区干净检查{Color.END}")
        git_clean, uncommitted = True, ""
    else:
        git_clean, uncommitted = check_git_merged(cr_path)
    if git_clean is None:
        print(f"{Color.YELLOW}⚠ 无法检查 Git 状态{Color.END}")
        warnings.append("Git 状态检查失败")
    elif git_clean:
        print(f"{Color.GREEN}✓ 工作区干净（无未提交变更）{Color.END}")
    else:
        print(f"{Color.YELLOW}⚠ 存在未提交变更{Color.END}")
        warnings.append("存在未提交文件，确认是否已归档")

    # 检查 3: 文档更新
    print(f"\n{Color.BLUE}[文档更新]{Color.END}")
    deliverhq_docs = DELIVERHQ_ROOT / 'docs'
    rules_path = deliverhq_docs / 'rules.md'
    candidate_rules_path = deliverhq_docs / 'rules-candidates.md'
    deprecated_rules_path = deliverhq_docs / 'rules-deprecated.md'
    doc_files = {
        'architecture.md': deliverhq_docs / 'architecture.md',
        'interfaces.md': deliverhq_docs / 'interfaces.md',
        'data-model.md': deliverhq_docs / 'data-model.md',
        'rules.md': rules_path,
        'rules-candidates.md': candidate_rules_path,
        'rules-deprecated.md': deprecated_rules_path,
        'decisions.md': deliverhq_docs / 'decisions.md',
    }

    for doc_name, doc_path in doc_files.items():
        if doc_path.exists():
            print(f"  {Color.GREEN}✓{Color.END} {doc_name} 存在")
        else:
            print(f"  {Color.YELLOW}⚠{Color.END} {doc_name} 缺失")

    rules_intent = detect_rules_writeback_intent(content)
    if rules_intent == "candidate":
        ready, reason = candidate_rules_ready(candidate_rules_path)
        if ready:
            print(f"  {Color.GREEN}✓{Color.END} 已检测到有效的规则候选写回")
        else:
            print(f"  {Color.RED}✗{Color.END} {reason}")
            blockers.append(reason)
    elif rules_intent == "unknown":
        warnings.append("writeback-report.md 未明确说明是否产生规则候选")
    else:
        print(f"  {Color.GREEN}✓{Color.END} 报告已明确声明本次无新规则")

    # 检查 4: 可追溯性
    print(f"\n{Color.BLUE}[可追溯性]{Color.END}")
    trace_path = Path(cr_path) / "traceability.yml"
    if trace_path.exists():
        trace_content = trace_path.read_text(encoding='utf-8')
        if 'CR-TEMPLATE' in trace_content or '{{' in trace_content:
            print(f"{Color.RED}✗ traceability.yml 未更新（仍为模板）{Color.END}")
            blockers.append("traceability.yml 未填充实际内容")
        else:
            print(f"{Color.GREEN}✓ traceability.yml 已更新{Color.END}")
    else:
        print(f"{Color.YELLOW}⚠ traceability.yml 缺失{Color.END}")
        warnings.append("建议维护 traceability.yml")

    # 检查 5: CR 归档
    print(f"\n{Color.BLUE}[CR 归档]{Color.END}")
    cr_id = Path(cr_path).name
    delivery_path = DELIVERHQ_ROOT / 'delivery'

    # 检查是否已归档到 delivery/
    if delivery_path.exists():
        archived_cr = list(delivery_path.rglob(cr_id))
        if archived_cr:
            print(f"{Color.GREEN}✓ CR 已归档到 delivery/{Color.END}")
        else:
            print(f"{Color.YELLOW}⚠ CR 尚未归档到 delivery/{Color.END}")
            warnings.append("完成后需归档到 delivery/YYYY-MM/")
    else:
        print(f"{Color.YELLOW}⚠ delivery/ 目录不存在{Color.END}")

    # 汇总结果
    print(f"\n{Color.BLUE}=== WritebackGate 结果 ==={Color.END}")
    if blockers:
        print(f"{Color.RED}❌ BLOCKED{Color.END}")
        for i, b in enumerate(blockers, 1):
            print(f"  {i}. {b}")
        print(f"\n{Color.RED}⛔ 反馈 Writeback Agent 补充归档{Color.END}")
        update_gate_from_result(
            Path(cr_path),
            'writeback',
            False,
            blockers=blockers,
            state_after_pass='archived',
            current_phase='writeback',
            current_owner='writeback-agent',
            next_required_gate='writeback',
            artifacts=['writeback-report.md', 'docs/rules-candidates.md'],
            warnings=warnings,
            next_action='补齐候选规则写回或明确声明本次无新规则后重新运行 WritebackGate',
        )
        return False, blockers

    if warnings:
        print(f"{Color.YELLOW}⚠️  PASS WITH WARNINGS{Color.END}")
        for i, w in enumerate(warnings, 1):
            print(f"  {i}. {w}")

    print(f"{Color.GREEN}✅ PASS - 交付完成，CR 可关闭{Color.END}")
    update_gate_from_result(
        Path(cr_path),
        'writeback',
        True,
        blockers=[],
        state_after_pass='archived',
        current_phase='writeback',
        current_owner='writeback-agent',
        next_required_gate=None,
        artifacts=['writeback-report.md', 'docs/rules-candidates.md'],
        warnings=warnings,
        next_action='进入归档流程',
    )
    return True, []

def main():
    if len(sys.argv) < 2:
        print("用法: python writeback_gate.py <path/to/CR-XXX>")
        sys.exit(1)

    cr_path = sys.argv[1]
    passed, blockers = check_writeback_gate(cr_path)

    sys.exit(0 if passed else 1)

if __name__ == "__main__":
    main()
