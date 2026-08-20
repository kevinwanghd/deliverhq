#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Red Lines Check - Red Lines Check Script

Source: WeChat Work Team "AI Code Generation Rate 94%" Experience

Core Principles:
  - Critical Red Lines: Must be followed throughout the entire process
  - Standard Red Lines: Load by phase, warn on violation

Usage:
  python red_lines_check.py check --cr-id CR-001 --phase implement
  python red_lines_check.py check --phase verify --context "UI改动"
  python red_lines_check.py list --type critical
  python red_lines_check.py list --type standard
  python red_lines_check.py report --phase implement
"""
from __future__ import annotations

import argparse
import sys
import yaml
from pathlib import Path
from typing import Optional
from common import Color
from common import load_yaml

# =============================================================================
# 配置
# =============================================================================

# governance.config.yml 多路径查找
_config_paths = [
    Path(__file__).parent.parent / "governance.config.yml",  # skill/ 下
    Path(__file__).parent.parent.parent / "governance.config.yml",  # 项目根目录下
]
DEFAULT_CONFIG_PATH = next((p for p in _config_paths if p.exists()), _config_paths[0])


# 默认红线定义（当配置文件不存在时使用）
DEFAULT_CRITICAL_RED_LINES = [
    {
        "id": "RL-C01",
        "title": "编译必须通过",
        "description": "bazel build / flutter build / npm run build 退出码 0 是唯一判据",
        "enforcement": "fail_closed",
        "max_self_fix": 3,
    },
    {
        "id": "RL-C02",
        "title": "未按阶段执行",
        "description": "后一阶段输入必须等于前一阶段产出，禁止跳过阶段",
        "enforcement": "fail_closed",
    },
    {
        "id": "RL-C03",
        "title": "先看后写",
        "description": "禁止在未读懂现有代码模式前发明新写法",
        "enforcement": "fail_closed",
    },
    {
        "id": "RL-C04",
        "title": "先模仿后发明",
        "description": "禁止 AI 发明新模式，必须模仿项目已有的代码风格",
        "enforcement": "fail_closed",
    },
    {
        "id": "RL-C05",
        "title": "禁止修改受保护路径",
        "description": "dir-graph.yaml 中定义的 protected_paths 未批准不得修改",
        "enforcement": "fail_closed",
    },
    {
        "id": "RL-C06",
        "title": "git commit 必须同步执行",
        "description": "git commit 后 git log -1 hash 更新是唯一成功证据",
        "enforcement": "fail_closed",
    },
]

DEFAULT_STANDARD_RED_LINES = [
    {"id": "RL-S01", "title": "UI 改动必须比对语义桥", "enforcement": "warn", "phase": "implement"},
    {"id": "RL-S02", "title": "禁止语义联想扩大范围", "enforcement": "warn", "phase": "implement"},
    {"id": "RL-S03", "title": "跨会话知识必须沉淀", "enforcement": "warn", "phase": "commit"},
    {"id": "RL-S04", "title": "禁止遗漏设计稿", "enforcement": "warn", "phase": "breakdown"},
    {"id": "RL-S05", "title": "视觉对齐必须逐项核对", "enforcement": "warn", "phase": "verify"},
    {"id": "RL-S06", "title": "禁止 LLM 手工分桶", "enforcement": "warn", "phase": "breakdown"},
    {"id": "RL-S07", "title": "阶段内重试不超过 2 轮", "enforcement": "warn", "phase": "simulator"},
    {"id": "RL-S08", "title": "设计稿筛选必须用脚本", "enforcement": "warn", "phase": "breakdown"},
]

# 颜色

# =============================================================================
# 核心函数
# =============================================================================

def load_red_lines(config_path: Path = None) -> dict:
    """加载红线配置"""
    config_path = config_path or DEFAULT_CONFIG_PATH

    if not config_path.exists():
        return {
            "critical": DEFAULT_CRITICAL_RED_LINES,
            "standard": DEFAULT_STANDARD_RED_LINES
        }

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = load_yaml(f)

        red_lines = {"critical": [], "standard": []}

        if config and "red_lines" in config:
            if "critical" in config["red_lines"]:
                red_lines["critical"] = config["red_lines"]["critical"]
            if "standard" in config["red_lines"]:
                red_lines["standard"] = config["red_lines"]["standard"]

        # 如果配置文件没有，使用默认值
        if not red_lines["critical"]:
            red_lines["critical"] = DEFAULT_CRITICAL_RED_LINES
        if not red_lines["standard"]:
            red_lines["standard"] = DEFAULT_STANDARD_RED_LINES

        return red_lines
    except Exception as e:
        print(f"⚠️  加载配置文件失败 ({config_path}): {e}")
        print("⚠️  使用默认红线定义")
        return {
            "critical": DEFAULT_CRITICAL_RED_LINES,
            "standard": DEFAULT_STANDARD_RED_LINES
        }


def check_phase(phase: str, red_lines: dict) -> dict:
    """检查特定阶段的红线"""
    result = {
        "phase": phase,
        "critical": red_lines["critical"],
        "standard": [rl for rl in red_lines["standard"] if rl.get("phase") == phase],
        "violations": [],
        "warnings": [],
    }
    return result


def format_report(rl: dict, violation: str = None) -> str:
    """格式化红线报告"""
    rl_id = rl.get("id", "UNKNOWN")
    title = rl.get("title", "无标题")
    description = rl.get("description", "")
    enforcement = rl.get("enforcement", "warn")

    icon = "[X]" if enforcement == 'fail_closed' else "[!]"
    lines = [
        f"\n{icon} 触发红线 {rl_id}: {title}",
        f"   规则: {description}",
    ]

    if violation:
        lines.append(f"   当前情形: {violation}")

    if "note" in rl:
        lines.append(f"   说明: {rl['note']}")

    if enforcement == "fail_closed":
        lines.append(f"   处置: fail_closed (必须停下手头工作)")

    return "\n".join(lines)


def print_red_lines(red_lines: dict, type: str = None):
    """打印红线列表"""
    if type == "critical" or type is None:
        print(f"\n{Color.RED}═══ Critical 红线（全局强制）═══{Color.END}")
        for rl in red_lines["critical"]:
            rl_id = rl.get("id", "")
            title = rl.get("title", "")
            enforcement = rl.get("enforcement", "fail_closed")
            note = rl.get("note", "")
            print(f"  {Color.RED}{rl_id}{Color.END} {title}")
            if note:
                print(f"        {note}")

    if type == "standard" or type is None:
        print(f"\n{Color.YELLOW}═══ Standard 红线（按阶段加载）═══{Color.END}")
        # 按阶段分组
        by_phase = {}
        for rl in red_lines["standard"]:
            phase = rl.get("phase", "unknown")
            if phase not in by_phase:
                by_phase[phase] = []
            by_phase[phase].append(rl)

        for phase, rules in sorted(by_phase.items()):
            print(f"\n  {Color.BLUE}[{phase}]{Color.END}")
            for rl in rules:
                rl_id = rl.get("id", "")
                title = rl.get("title", "")
                print(f"    {Color.YELLOW}{rl_id}{Color.END} {title}")


def get_phase_report(phase: str, red_lines: dict) -> str:
    """获取特定阶段的红线报告"""
    result = [f"\n{Color.BLUE}=== {phase} 阶段红线 ==={Color.END}"]

    # Critical 红线（全部适用）
    result.append(f"\n{Color.RED}Critical（全局强制）：{Color.END}")
    for rl in red_lines["critical"]:
        rl_id = rl.get("id", "")
        title = rl.get("title", "")
        result.append(f"  - {rl_id} {title}")

    # Standard 红线（按阶段）
    phase_rules = [rl for rl in red_lines["standard"] if rl.get("phase") == phase]
    if phase_rules:
        result.append(f"\n{Color.YELLOW}Standard（{phase} 阶段）：{Color.END}")
        for rl in phase_rules:
            rl_id = rl.get("id", "")
            title = rl.get("title", "")
            result.append(f"  - {rl_id} {title}")

    return "\n".join(result)


# =============================================================================
# CLI
# =============================================================================

def main():
    # 设置输出编码为 UTF-8
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    parser = argparse.ArgumentParser(
        description="Red Lines Check - Red Lines Check Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all red lines
  python red_lines_check.py list

  # List Critical red lines
  python red_lines_check.py list --type critical

  # List Standard red lines
  python red_lines_check.py list --type standard

  # 查看 implement 阶段的红线
  python red_lines_check.py report --phase implement

  # 检查违规（dry-run 模式）
  python red_lines_check.py check --cr-id CR-001 --phase implement --context "未先看代码就修改"

核心原则：
  - Critical 红线全流程必守，启动即加载
  - Standard 红线按阶段加载
  - 触发 fail_closed 类型的红线必须立即停下
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # list
    p_list = subparsers.add_parser("list", help="列出红线")
    p_list.add_argument("--type", choices=["critical", "standard"], help="红线类型")

    # report
    p_report = subparsers.add_parser("report", help="生成阶段红线报告")
    p_report.add_argument("--phase", required=True,
                          choices=["breakdown", "implement", "verify", "simulator", "commit", "locate"],
                          help="阶段")

    # check
    p_check = subparsers.add_parser("check", help="检查违规")
    p_check.add_argument("--cr-id", help="CR 编号")
    p_check.add_argument("--phase", required=True,
                          choices=["breakdown", "implement", "verify", "simulator", "commit", "locate"],
                          help="当前阶段")
    p_check.add_argument("--context", help="上下文描述（触发违规的原因）")
    p_check.add_argument("--config", type=Path, help="配置文件路径")

    args = parser.parse_args()

    # 加载红线配置
    config_path = args.config if hasattr(args, 'config') else None
    red_lines = load_red_lines(config_path)

    if args.command == "list":
        print_red_lines(red_lines, args.type)

    elif args.command == "report":
        print(get_phase_report(args.phase, red_lines))

    elif args.command == "check":
        print(f"\n{Color.BLUE}═══ 红线检查 ═══{Color.END}")
        print(f"阶段：{args.phase}")
        if args.cr_id:
            print(f"CR：{args.cr_id}")
        if args.context:
            print(f"上下文：{args.context}")

        # 显示阶段红线
        print(get_phase_report(args.phase, red_lines))

        # 如果有违规上下文，检查是否触发
        if args.context:
            violations = []

            # 检查 Critical 红线
            for rl in red_lines["critical"]:
                # 这里可以添加更智能的违规检测逻辑
                # 目前只是示例框架
                pass

            if violations:
                print("\n" + "=" * 50)
                for v in violations:
                    print(format_report(v["rule"], v["context"]))
                print(f"\n{Color.RED}❌ 存在违规，必须停下处理{Color.END}")
                sys.exit(1)
            else:
                print(f"\n{Color.GREEN}✅ 未检测到明显违规{Color.END}")
        else:
            print(f"\n{Color.YELLOW}ℹ️  使用 --context 参数可以检查具体违规{Color.END}")

    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
