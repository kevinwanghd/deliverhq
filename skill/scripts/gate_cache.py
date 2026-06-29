#!/usr/bin/env python3
"""
Gate Cache — Gate 结果缓存和 fingerprint 机制

优化目标：
- 避免重复执行已通过且依赖未变的 Gate
- 改一个字段时，只重跑受影响的 Gate

原理：
1. 每个 Gate 计算 fingerprint（依赖文件的 hash）
2. Gate 运行前检查：fingerprint 没变 + status=passed → 跳过执行
3. fingerprint 变化 → 重新执行

收益：
- 修改 implementation-plan.md 时，spec/design Gate 跳过（节省 ~3000 tokens）
- 只有受影响的下游 Gate 才重新执行
"""

import hashlib
import sys
sys.dont_write_bytecode = True
from pathlib import Path
from typing import List, Optional
import yaml


# Gate 依赖关系定义（哪些文件影响哪个 Gate）
GATE_DEPENDENCIES = {
    "spec": [
        "request.md",
        "acceptance-spec.md",
        "request-clarifications.md",
    ],
    "design": [
        "acceptance-spec.md",
        "design/design-decisions.md",
        "design/prototype.html",
        "design/hi-fi-spec.md",
        "design/metadata.yml",
    ],
    "architecture": [
        "acceptance-spec.md",
        "design/design-decisions.md",
        "architecture-design.md",
    ],
    "predev": [
        "acceptance-spec.md",
        "design/design-decisions.md",
        "architecture-design.md",
        "implementation-plan.md",
        "test-plan.md",
    ],
    "review": [
        "traceability.yml",
        "changed-files.txt",  # 从 git diff 生成
    ],
    "quality": [
        "verification-manifest.yml",
        "implementation-plan.md",
        # 不包含 evidence/，因为那是输出不是输入
    ],
    "deploy": [
        "deployment-plan.md",
        "verification-manifest.yml",
    ],
    "writeback": [
        "traceability.yml",
        "*-report.md",  # 所有 report
    ]
}


def calculate_fingerprint(cr_path: Path, dependencies: List[str]) -> str:
    """
    计算依赖文件的 fingerprint（SHA256）

    Args:
        cr_path: CR 根目录
        dependencies: 依赖文件列表

    Returns:
        SHA256 hex digest
    """
    hasher = hashlib.sha256()

    # 按文件名排序，确保顺序一致
    sorted_deps = sorted(dependencies)

    for dep_pattern in sorted_deps:
        if "*" in dep_pattern:
            # 处理通配符（如 *-report.md）
            pattern = dep_pattern.replace("*", "")
            for file_path in sorted(cr_path.glob(f"*{pattern}")):
                if file_path.is_file():
                    try:
                        content = file_path.read_bytes()
                        hasher.update(file_path.name.encode('utf-8'))
                        hasher.update(content)
                    except Exception:
                        pass
        else:
            file_path = cr_path / dep_pattern
            if file_path.exists() and file_path.is_file():
                try:
                    content = file_path.read_bytes()
                    hasher.update(dep_pattern.encode('utf-8'))
                    hasher.update(content)
                except Exception:
                    # 文件读取失败，跳过
                    pass

    return hasher.hexdigest()


def get_gate_fingerprint(cr_path: Path, gate_name: str) -> str:
    """
    获取指定 Gate 的 fingerprint

    Args:
        cr_path: CR 根目录
        gate_name: Gate 名称（spec/design/architecture/等）

    Returns:
        fingerprint (SHA256 hex)
    """
    dependencies = GATE_DEPENDENCIES.get(gate_name, [])
    return calculate_fingerprint(cr_path, dependencies)


def should_skip_gate(cr_path: Path, gate_name: str) -> bool:
    """
    判断是否可以跳过 Gate 执行

    条件：
    1. state.yml 中 gate_status[gate_name] = pass
    2. 当前 fingerprint == 缓存的 fingerprint

    Args:
        cr_path: CR 根目录
        gate_name: Gate 名称

    Returns:
        True 表示可以跳过（缓存命中）
    """
    state_path = cr_path / "state.yml"

    if not state_path.exists():
        return False

    try:
        with open(state_path, 'r', encoding='utf-8') as f:
            state = yaml.safe_load(f) or {}
    except Exception:
        return False

    # 检查状态（从 gate_status 字段）
    gate_status = state.get('gate_status', {})
    if gate_status.get(gate_name) != 'pass':
        return False

    # 检查 fingerprint（从 gates 字段）
    gates = state.get('gates', {})
    gate_info = gates.get(gate_name, {})

    cached_fingerprint = gate_info.get('fingerprint')
    if not cached_fingerprint:
        return False

    current_fingerprint = get_gate_fingerprint(cr_path, gate_name)

    return current_fingerprint == cached_fingerprint


def update_gate_fingerprint(cr_path: Path, gate_name: str, status: str):
    """
    更新 Gate 的 fingerprint（Gate 执行后调用）

    Args:
        cr_path: CR 根目录
        gate_name: Gate 名称
        status: Gate 状态（passed/blocked）
    """
    state_path = cr_path / "state.yml"

    try:
        if state_path.exists():
            with open(state_path, 'r', encoding='utf-8') as f:
                state = yaml.safe_load(f) or {}
        else:
            state = {}
    except Exception:
        state = {}

    # 计算当前 fingerprint
    current_fingerprint = get_gate_fingerprint(cr_path, gate_name)

    # 更新 gates 字段
    if 'gates' not in state:
        state['gates'] = {}

    if gate_name not in state['gates']:
        state['gates'][gate_name] = {}

    state['gates'][gate_name]['fingerprint'] = current_fingerprint

    # 写回 state.yml
    try:
        with open(state_path, 'w', encoding='utf-8') as f:
            yaml.dump(state, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    except Exception as e:
        print(f"警告: 无法更新 state.yml fingerprint: {e}", file=sys.stderr)


def invalidate_downstream_gates(cr_path: Path, changed_gate: str):
    """
    当某个 Gate 变化时，使其下游 Gate 的缓存失效

    Gate 依赖链：
    spec → design → architecture → predev → dev → review → quality → deploy → writeback

    Args:
        cr_path: CR 根目录
        changed_gate: 发生变化的 Gate
    """
    gate_chain = [
        "spec", "design", "architecture", "predev",
        "dev", "review", "quality", "deploy", "writeback"
    ]

    if changed_gate not in gate_chain:
        return

    # 找到下游 Gate
    changed_index = gate_chain.index(changed_gate)
    downstream_gates = gate_chain[changed_index + 1:]

    state_path = cr_path / "state.yml"

    if not state_path.exists():
        return

    try:
        with open(state_path, 'r', encoding='utf-8') as f:
            state = yaml.safe_load(f) or {}

        gates = state.get('gates', {})

        # 清除下游 Gate 的 fingerprint
        for gate_name in downstream_gates:
            if gate_name in gates and 'fingerprint' in gates[gate_name]:
                del gates[gate_name]['fingerprint']

        # 写回
        with open(state_path, 'w', encoding='utf-8') as f:
            yaml.dump(state, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    except Exception as e:
        print(f"警告: 无法使下游 Gate 缓存失效: {e}", file=sys.stderr)


# CLI for debugging
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gate 缓存工具")
    parser.add_argument("cr_path", help="CR 目录路径")
    parser.add_argument("--gate", help="Gate 名称")
    parser.add_argument("--check", action="store_true", help="检查是否可以跳过")
    parser.add_argument("--fingerprint", action="store_true", help="计算 fingerprint")

    args = parser.parse_args()
    cr_path = Path(args.cr_path)

    if args.check and args.gate:
        can_skip = should_skip_gate(cr_path, args.gate)
        print(f"{'✅ 可以跳过' if can_skip else '❌ 需要执行'}: {args.gate}")
        sys.exit(0 if can_skip else 1)

    if args.fingerprint and args.gate:
        fp = get_gate_fingerprint(cr_path, args.gate)
        print(f"{args.gate} fingerprint: {fp}")

    else:
        parser.print_help()
