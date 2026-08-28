#!/usr/bin/env python3
"""
Phase Docs Validator - 验证当前阶段所需的文档是否都存在。

按 AGENTS.md 的《按阶段加载文档》规则检查：
- Spec 阶段：AGENTS.md, dir-graph.yaml, docs/CONTEXT.md
- Design 阶段：+ acceptance-spec.md
- Dev 阶段：+ context-summary.md + implementation-plan.md
- Test 阶段：+ test-plan.md
- Quality 阶段：+ quality-report.md + docs/rules.md
- Writeback 阶段：+ writeback-report.md + docs/verification.md
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# DeliverHQ 根目录（脚本在 skill/scripts/ 下）
SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common import Color


# 按阶段定义必需文档（相对于 CR 目录或 DeliverHQ 根目录）
PHASE_REQUIREMENTS: Dict[str, Dict[str, List[Tuple[str, str]]]] = {
    "spec": {
        "CR 内": [
            ("request.md", "需求描述"),
        ],
        "skill 根": [
            ("AGENTS.md", "行为规则"),
            ("dir-graph.yaml", "权限与路径"),
            ("docs/CONTEXT.md", "项目上下文"),
        ],
    },
    "design": {
        "CR 内": [
            ("acceptance-spec.md", "验收规格"),
        ],
    },
    "dev": {
        "CR 内": [
            ("context-summary.md", "上下文摘要"),
            ("implementation-plan.md", "实施计划"),
        ],
    },
    "test": {
        "CR 内": [
            ("test-plan.md", "测试计划"),
        ],
    },
    "quality": {
        "CR 内": [
            ("quality-report.md", "质量报告"),
        ],
        "skill 根": [
            ("docs/rules.md", "规则文档"),
        ],
    },
    "writeback": {
        "CR 内": [
            ("writeback-report.md", "交付报告"),
        ],
        "skill 根": [
            ("docs/verification.md", "验证指南"),
        ],
    },
}


def _resolve_paths(cr_path: Path, scope: str) -> Tuple[Path, List[Tuple[str, str]]]:
    """根据作用域解析基准路径和文件列表。"""
    if scope == "CR 内":
        return cr_path, PHASE_REQUIREMENTS.get("common", {}).get(scope, [])
    return SKILL_ROOT, PHASE_REQUIREMENTS.get("common", {}).get(scope, [])


def validate_phase_docs(cr_path: Path, phase: str) -> Tuple[bool, List[str], List[str]]:
    """验证 CR 当前阶段所需的文档是否存在。

    返回: (是否全部通过, 阻塞项列表, 警告项列表)
    """
    cr_path = Path(cr_path).resolve()
    blockers: List[str] = []
    warnings: List[str] = []

    if phase not in PHASE_REQUIREMENTS:
        warnings.append(f"未知阶段: {phase}，跳过文档验证")
        return True, blockers, warnings

    requirements = PHASE_REQUIREMENTS[phase]

    # 按作用域分组检查
    for scope, files in requirements.items():
        if scope == "CR 内":
            base = cr_path
        else:
            base = SKILL_ROOT

        for file_path, description in files:
            full_path = base / file_path
            if not full_path.exists():
                blockers.append(f"[{phase}/{scope}] 缺少 {description} ({file_path})")

    return len(blockers) == 0, blockers, warnings


def print_phase_report(cr_path: Path, phase: str, passed: bool, blockers: List[str], warnings: List[str]):
    """打印阶段文档验证报告。"""
    cr_id = Path(cr_path).name

    print(f"{Color.BLUE}=== Phase Docs 验证报告 ==={Color.END}")
    print(f"CR: {cr_id}")
    print(f"当前阶段: {phase}")
    print()

    if not blockers and not warnings:
        print(f"{Color.GREEN}✅ 所有必需文档存在{Color.END}")
        return

    for warning in warnings:
        print(f"{Color.YELLOW}⚠ {warning}{Color.END}")

    if blockers:
        print(f"{Color.RED}❌ 发现 {len(blockers)} 个问题:{Color.END}")
        for i, blocker in enumerate(blockers, 1):
            print(f"  {i}. {blocker}")
        print()
        print(f"{Color.YELLOW}提示: 按照 AGENTS.md 的《按阶段加载文档》规则，")
        print(f"       当前阶段 ({phase}) 需要上述文档才能正确加载上下文。{Color.END}")


def main():
    parser = argparse.ArgumentParser(description="验证 CR 当前阶段所需的文档是否存在")
    parser.add_argument("cr_path", help="CR 目录路径")
    parser.add_argument(
        "--phase",
        help="CR 当前阶段 (spec/design/dev/test/quality/writeback)，不指定则从 state.yml 读取",
    )
    parser.add_argument(
        "--check-next",
        action="store_true",
        help="同时检查下一阶段需要的文档（预览用）",
    )

    args = parser.parse_args()
    cr_path = Path(args.cr_path)

    # 尝试从 state.yml 读取当前阶段
    phase = args.phase
    if not phase:
        state_file = cr_path / "state.yml"
        if state_file.exists():
            try:
                import yaml
                with open(state_file, encoding="utf-8") as f:
                    state = yaml.safe_load(f)
                phase = state.get("current_phase", "spec")
            except Exception:
                pass

    if not phase:
        print(f"{Color.YELLOW}⚠ 无法确定 CR 阶段，使用 --phase 指定{Color.END}")
        phase = "spec"

    passed, blockers, warnings = validate_phase_docs(cr_path, phase)
    print_phase_report(cr_path, phase, passed, blockers, warnings)

    # 可选：检查下一阶段
    if args.check_next:
        next_phases = {
            "spec": "design",
            "design": "dev",
            "dev": "test",
            "test": "quality",
            "quality": "writeback",
        }
        next_phase = next_phases.get(phase)
        if next_phase:
            print()
            print(f"{Color.BLUE}[下一阶段预览: {next_phase}]{Color.END}")
            next_passed, next_blockers, next_warnings = validate_phase_docs(cr_path, next_phase)
            if next_blockers:
                print(f"  缺少 {len(next_blockers)} 个文档（进入前需要准备）:")
                for blocker in next_blockers:
                    print(f"    - {blocker}")
            else:
                print(f"{Color.GREEN}  ✓ 下一阶段所需文档已就绪{Color.END}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
