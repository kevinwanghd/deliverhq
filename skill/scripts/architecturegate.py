#!/usr/bin/env python3
"""
ArchitectureGate - 架构设计完备性检查（第二道人工门禁）
编码前必须有 architecture-design.md 且经人工确认，对齐文章「架构确认」环节。
通用工程内核，技术栈无关。
"""

import sys
import re
from pathlib import Path

from cr_state import update_gate_from_result
from runtime_support import configure_console

configure_console()

class Color:
    GREEN = '\033[92m'; YELLOW = '\033[93m'; RED = '\033[91m'; BLUE = '\033[94m'; END = '\033[0m'

TEMPLATE_VAR = re.compile(r'\{\{[^}]+\}\}')


def _has_section(text, heading):
    return heading in text


def _has_human_confirmation(text):
    for line in text.splitlines():
        if '人工确认' not in line or '已确认' not in line:
            continue
        if '未确认' in line or '{{' in line or '}}' in line:
            continue
        match = re.search(r'已确认（([^）]+)）', line)
        if not match:
            continue
        confirmation = match.group(1).strip()
        if confirmation and '确认人' not in confirmation and '日期' not in confirmation:
            return True
    return False


def check_architecturegate(cr_path):
    print(f"{Color.BLUE}=== ArchitectureGate 检查 ==={Color.END}\n")
    arch = Path(cr_path) / "architecture-design.md"
    blockers = []
    warnings = []

    if not arch.exists():
        print(f"{Color.RED}✗ 缺少 architecture-design.md{Color.END}")
        update_gate_from_result(
            Path(cr_path), 'architecture', False,
            blockers=["缺少 architecture-design.md（编码前必须架构确认）"],
            state_after_pass='design', current_phase='architecture',
            current_owner='design-agent', next_required_gate='architecture')
        return False, ["缺少 architecture-design.md"]

    text = arch.read_text(encoding='utf-8')

    required = [
        ('## 1. 模块拆分', '模块拆分与目录结构'),
        ('## 2. 数据流', '数据流与状态管理'),
        ('## 3. 接口封装', '接口封装与依赖'),
        ('## 4. 异常处理', '异常处理与验证策略'),
        ('## 5. 设计分块到实现映射', '设计分块到实现映射'),
    ]
    for pat, name in required:
        if pat not in text:
            blockers.append(f"缺少章节: {name}")

    # 残留模板变量
    if TEMPLATE_VAR.search(text):
        blockers.append("architecture-design.md 含未替换模板变量 {{}}")

    # 人工确认（warning-first：未确认提示，不直接 block，由人推进）
    if not _has_human_confirmation(text):
        warnings.append("架构设计尚未人工确认（建议人工确认后再进入开发）")

    passed = not blockers
    print(f"\n{Color.BLUE}=== ArchitectureGate 结果 ==={Color.END}")
    if blockers:
        print(f"{Color.RED}❌ BLOCKED{Color.END}")
        for i, b in enumerate(blockers, 1):
            print(f"  {i}. {b}")
    else:
        if warnings:
            print(f"{Color.YELLOW}⚠️  PASS WITH WARNINGS{Color.END}")
            for i, w in enumerate(warnings, 1):
                print(f"  {i}. {w}")
        print(f"{Color.GREEN}✅ PASS{Color.END}")

    update_gate_from_result(
        Path(cr_path), 'architecture', passed,
        blockers=blockers, warnings=warnings,
        state_after_pass='design', current_phase='architecture',
        current_owner='design-agent',
        next_required_gate=('architecture' if not passed else 'context'))
    return passed, blockers


def main():
    if len(sys.argv) < 2:
        print("用法: python architecturegate.py <path/to/CR-XXX>")
        sys.exit(1)
    passed, _ = check_architecturegate(sys.argv[1])
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
