#!/usr/bin/env python3
"""
ContextWindowGate - 上下文窗口纪律检查
验证滑动窗口机制：最多 2 个阶段全文，阶段切换必须更新 context-summary.md
"""

import sys
from pathlib import Path
import re

from cr_state import update_gate_from_result
from runtime_support import configure_console

class Color:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'

configure_console()

def get_file_size_kb(path):
    """获取文件大小（KB）"""
    if not Path(path).exists():
        return 0
    return Path(path).stat().st_size / 1024

def check_context_window(cr_path):
    """检查上下文窗口纪律"""
    print(f"{Color.BLUE}=== ContextWindowGate 检查 ==={Color.END}\n")

    summary_path = Path(cr_path) / "context-summary.md"

    blockers = []
    warnings = []

    # 检查 1: context-summary.md 存在性
    if not summary_path.exists():
        # 判断是否已进入需要摘要的阶段
        impl_plan = Path(cr_path) / "implementation-plan.md"
        if impl_plan.exists():
            print(f"{Color.RED}✗ 已进入 Dev 阶段但缺少 context-summary.md{Color.END}")
            blockers.append("阶段切换时必须创建 context-summary.md")
            update_gate_from_result(
                Path(cr_path),
                'context',
                False,
                blockers=blockers,
                state_after_pass='dev',
                current_phase='context',
                current_owner='context-agent',
                next_required_gate='context',
            )
            return False, blockers, {}
        else:
            print(f"{Color.GREEN}✓ 尚未进入 Dev 阶段，暂不需要 context-summary.md{Color.END}")
            update_gate_from_result(
                Path(cr_path),
                'context',
                True,
                blockers=[],
                state_after_pass='dev',
                current_phase='context',
                current_owner='context-agent',
                next_required_gate='pre_dev',
            )
            return True, [], {}

    # 检查 2: 摘要内容完整性
    content = summary_path.read_text(encoding='utf-8')

    # 支持中英文表头
    required_sections = [
        '## Current Phase', '## Completed Phases', '## Key Decisions', '## Loaded Context',  # 英文
        '## 当前阶段', '## 已完成阶段', '## 关键决策', '## 加载的上下文'  # 中文
    ]

    # 至少匹配一种语言的表头
    found_sections = [sec for sec in required_sections if sec in content]

    # 检查是否至少有一套完整的表头（英文4个或中文4个）
    has_english = all(sec in content for sec in required_sections[:4])
    has_chinese = all(sec in content for sec in required_sections[4:])

    if not (has_english or has_chinese):
        missing = required_sections[:4] if not has_english else required_sections[4:]
        print(f"{Color.RED}✗ context-summary.md 缺少必需章节（中英文均不完整）{Color.END}")
        blockers.append(f"缺少章节，需要英文章节: {', '.join(required_sections[:4])} 或中文章节")
    else:
        lang = "英文" if has_english else "中文"
        print(f"{Color.GREEN}✓ context-summary.md 结构完整（{lang}）{Color.END}")

    # 检查 3: 当前阶段标注
    if '{{' in content:
        print(f"{Color.RED}✗ context-summary.md 包含未替换模板变量{Color.END}")
        blockers.append("包含模板变量，未填充实际内容")
    else:
        print(f"{Color.GREEN}✓ 无模板变量{Color.END}")

    # 检查 4: 上下文负载估算
    context_files = {
        'acceptance-spec.md': get_file_size_kb(Path(cr_path) / 'acceptance-spec.md'),
        'implementation-plan.md': get_file_size_kb(Path(cr_path) / 'implementation-plan.md'),
        'test-plan.md': get_file_size_kb(Path(cr_path) / 'test-plan.md'),
        'design/': sum(f.stat().st_size for f in (Path(cr_path) / 'design').glob('*') if f.is_file()) / 1024 if (Path(cr_path) / 'design').exists() else 0,
        'context-summary.md': get_file_size_kb(summary_path),
    }

    total_context = sum(context_files.values())
    full_context_count = sum(1 for size in context_files.values() if size > 1)  # 大于 1KB 视为全文

    print(f"\n{Color.BLUE}[上下文负载]{Color.END}")
    for file, size in context_files.items():
        if size > 0:
            status = "全文" if size > 1 else "摘要"
            print(f"  {file}: {size:.1f} KB ({status})")

    print(f"\n  总上下文: {total_context:.1f} KB")
    print(f"  全文阶段数: {full_context_count}")

    if total_context > 500:
        print(f"{Color.YELLOW}⚠ 上下文接近 500 KB 阈值{Color.END}")
        warnings.append("建议进一步压缩已完成阶段")

    if full_context_count > 2:
        print(f"{Color.YELLOW}⚠ 超过 2 个阶段全文（建议压缩）{Color.END}")
        warnings.append("滑动窗口建议最多 2 个阶段全文")

    # 汇总结果
    print(f"\n{Color.BLUE}=== ContextWindowGate 结果 ==={Color.END}")
    if blockers:
        print(f"{Color.RED}❌ BLOCKED{Color.END}")
        for i, b in enumerate(blockers, 1):
            print(f"  {i}. {b}")
        update_gate_from_result(
            Path(cr_path),
            'context',
            False,
            blockers=blockers,
            state_after_pass='dev',
            current_phase='context',
            current_owner='context-agent',
            next_required_gate='context',
            warnings=warnings,
            next_action='补充 context-summary.md 后重新运行 ContextWindowGate',
        )
        return False, blockers, context_files

    if warnings:
        print(f"{Color.YELLOW}⚠️  PASS WITH WARNINGS{Color.END}")
        for i, w in enumerate(warnings, 1):
            print(f"  {i}. {w}")

    print(f"{Color.GREEN}✅ PASS{Color.END}")
    update_gate_from_result(
        Path(cr_path),
        'context',
        True,
        blockers=[],
        state_after_pass='dev',
        current_phase='context',
        current_owner='context-agent',
        next_required_gate='pre_dev',
        warnings=warnings,
        next_action='进入 PreDevGate',
    )
    return True, [], context_files

def main():
    if len(sys.argv) < 2:
        print("用法: python context_window_check.py <path/to/CR-XXX>")
        sys.exit(1)

    cr_path = sys.argv[1]
    passed, blockers, context_info = check_context_window(cr_path)

    sys.exit(0 if passed else 1)

if __name__ == "__main__":
    main()
