#!/usr/bin/env python3
"""
Gate JSON Output - 统一 Gate 输出格式

所有 Gate 除了人类可读输出，还要输出机器可读 JSON
方便 Agent、CI、Dashboard 继续消费
"""

from dataclasses import dataclass, asdict
from typing import List, Optional
from enum import Enum
import json


class GateResult(Enum):
    """Gate 结果枚举"""
    PASS = "pass"
    PASS_WITH_WARNINGS = "pass_with_warnings"
    BLOCKED = "blocked"
    ERROR = "error"


class Severity(Enum):
    """问题严重程度"""
    P0 = "p0"           # 阻断
    P1 = "p1"           # 严重但非阻断
    P2 = "p2"           # 建议改进
    INFO = "info"       # 信息


@dataclass
class BlockingItem:
    """阻塞项"""
    message: str                        # 错误信息
    severity: str                       # p0 | p1 | p2 | info
    file: Optional[str] = None          # 相关文件
    line: Optional[int] = None          # 相关行号
    suggestion: Optional[str] = None    # 修复建议


@dataclass
class GateOutput:
    """Gate 统一输出格式"""
    gate_name: str                      # Gate 名称
    result: str                         # pass | pass_with_warnings | blocked | error
    cr_id: str                          # CR ID
    timestamp: str                      # 检查时间

    # 阻塞项列表
    blocking_items: List[BlockingItem]

    # 警告列表
    warnings: List[str]

    # 下一步动作
    next_action: str                    # 建议的下一步操作

    # 元数据
    metadata: dict = None               # 额外信息


def format_gate_output(output: GateOutput) -> str:
    """格式化为人类可读输出"""
    lines = []

    # 标题
    lines.append(f"=== {output.gate_name} 检查结果 ===")
    lines.append(f"CR: {output.cr_id}")
    lines.append(f"时间: {output.timestamp}")
    lines.append("")

    # 结果
    if output.result == "pass":
        lines.append("✅ PASS")
    elif output.result == "pass_with_warnings":
        lines.append("⚠️  PASS WITH WARNINGS")
    elif output.result == "blocked":
        lines.append("❌ BLOCKED")
    else:
        lines.append("🔥 ERROR")

    lines.append("")

    # 阻塞项
    if output.blocking_items:
        lines.append("阻塞项:")
        for item in output.blocking_items:
            icon = "🚫" if item.severity == "p0" else "⚠️" if item.severity == "p1" else "💡"
            lines.append(f"  {icon} [{item.severity.upper()}] {item.message}")

            if item.file:
                location = f"{item.file}"
                if item.line:
                    location += f":{item.line}"
                lines.append(f"     位置: {location}")

            if item.suggestion:
                lines.append(f"     建议: {item.suggestion}")

        lines.append("")

    # 警告
    if output.warnings:
        lines.append("警告:")
        for warning in output.warnings:
            lines.append(f"  ⚠️  {warning}")
        lines.append("")

    # 下一步
    lines.append(f"下一步: {output.next_action}")

    return "\n".join(lines)


def save_gate_output_json(output: GateOutput, output_path: str):
    """保存为 JSON 文件"""
    data = {
        "gate_name": output.gate_name,
        "result": output.result,
        "cr_id": output.cr_id,
        "timestamp": output.timestamp,
        "blocking_items": [
            {
                "message": item.message,
                "severity": item.severity,
                "file": item.file,
                "line": item.line,
                "suggestion": item.suggestion
            }
            for item in output.blocking_items
        ],
        "warnings": output.warnings,
        "next_action": output.next_action,
        "metadata": output.metadata or {}
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_gate_output_json(json_path: str) -> GateOutput:
    """从 JSON 文件加载"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return GateOutput(
        gate_name=data['gate_name'],
        result=data['result'],
        cr_id=data['cr_id'],
        timestamp=data['timestamp'],
        blocking_items=[
            BlockingItem(**item) for item in data['blocking_items']
        ],
        warnings=data['warnings'],
        next_action=data['next_action'],
        metadata=data.get('metadata')
    )


# 示例用法
if __name__ == "__main__":
    from datetime import datetime

    # 示例：SpecGate 输出
    output = GateOutput(
        gate_name="SpecGate",
        result="blocked",
        cr_id="CR-001",
        timestamp=datetime.now().isoformat(),
        blocking_items=[
            BlockingItem(
                message="包含 3 处 [待确认] 或 [TODO] 未解决",
                severity="p0",
                file="acceptance-spec.md",
                line=45,
                suggestion="解决所有 [待确认] 占位符，将 P0 Open Questions 状态改为 resolved"
            ),
            BlockingItem(
                message="缺少 SDD 结构: Data Spec",
                severity="p0",
                file="acceptance-spec.md",
                suggestion="添加 ## 1. Data Spec 章节，定义核心数据结构"
            )
        ],
        warnings=[
            "包含模糊词但无量化指标: 优化"
        ],
        next_action="修复 2 个 P0 阻塞项后重新运行 SpecGate",
        metadata={
            "fuzzy_words": ["优化"],
            "scenario_count": 4
        }
    )

    # 人类可读输出
    print(format_gate_output(output))
    print("\n" + "="*60 + "\n")

    # JSON 输出
    print("JSON 输出:")
    print(json.dumps(asdict(output), ensure_ascii=False, indent=2))

    # 保存到文件
    save_gate_output_json(output, "/tmp/gate-output.json")
    print("\n✅ JSON 已保存到 /tmp/gate-output.json")
