#!/usr/bin/env python3
"""
Gate Wrapper — Gate 执行包装器，集成缓存机制

用法：
    python3 scripts/gate_wrapper.py spec change-requests/CR-001/acceptance-spec.md
    python3 scripts/gate_wrapper.py design change-requests/CR-001
    python3 scripts/gate_wrapper.py quality change-requests/CR-001

自动处理：
1. 检查 Gate 缓存（fingerprint）
2. 缓存命中 → 跳过执行，返回 PASS
3. 缓存未命中 → 执行真实 Gate，更新缓存
"""

import sys
sys.dont_write_bytecode = True
import subprocess
from pathlib import Path
import os

# 添加 scripts 目录到 path，以便导入其他模块
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from gate_cache import should_skip_gate, update_gate_fingerprint, invalidate_downstream_gates
from runtime_support import configure_console

configure_console()

# Gate 脚本映射
GATE_SCRIPTS = {
    "spec": "specgate.py",
    "design": "designgate.py",
    "architecture": "architecturegate.py",
    "predev": "predev_gate.py",
    "review": "reviewgate.py",
    "quality": "qualitygate.py",
    "deploy": "deploygate.py",
    "writeback": "writeback_gate.py",
}


class Color:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def extract_cr_path(args: list) -> Path:
    """
    从参数中提取 CR 路径

    Args:
        args: Gate 脚本的参数列表

    Returns:
        CR 根目录路径
    """
    for arg in args:
        if "change-requests" in arg:
            path = Path(arg)
            # 如果是文件，返回其父目录；如果是目录，返回目录本身
            if path.is_file():
                # 如果是 CR-XXX/acceptance-spec.md，返回 CR-XXX/
                if path.parent.name.startswith("CR-"):
                    return path.parent
                # 否则继续向上找
                return path.parent
            elif path.is_dir() and path.name.startswith("CR-"):
                return path
            elif path.is_dir():
                # 可能是 change-requests/CR-XXX，取最后一个部分
                for part in path.parts[::-1]:
                    if part.startswith("CR-"):
                        # 重建路径
                        idx = path.parts.index(part)
                        return Path(*path.parts[:idx+1])

    raise ValueError(f"无法从参数中提取 CR 路径: {args}")


def main():
    if len(sys.argv) < 3:
        print("用法: gate_wrapper.py <gate_name> <gate_args...>")
        print("示例: gate_wrapper.py spec change-requests/CR-001/acceptance-spec.md")
        sys.exit(1)

    gate_name = sys.argv[1]
    gate_args = sys.argv[2:]

    if gate_name not in GATE_SCRIPTS:
        print(f"❌ 未知的 Gate: {gate_name}")
        print(f"可用的 Gate: {', '.join(GATE_SCRIPTS.keys())}")
        sys.exit(1)

    # 提取 CR 路径
    try:
        cr_path = extract_cr_path(gate_args)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    # 检查是否启用缓存
    cache_enabled = os.getenv('DELIVERHQ_GATE_CACHE', '1') == '1'
    force_run = os.getenv('DELIVERHQ_FORCE_RUN', '0') == '1'

    # 检查缓存
    if cache_enabled and not force_run:
        if should_skip_gate(cr_path, gate_name):
            print(f"{Color.BLUE}=== {gate_name.capitalize()}Gate 缓存命中 ==={Color.END}")
            print(f"{Color.GREEN}✅ 依赖文件未变化，跳过执行{Color.END}")
            print(f"{Color.BLUE}ℹ️  使用缓存的 PASS 结果（设置 DELIVERHQ_FORCE_RUN=1 强制重跑）{Color.END}")
            sys.exit(0)

    # 缓存未命中，执行真实 Gate
    gate_script = SCRIPT_DIR / GATE_SCRIPTS[gate_name]

    if not gate_script.exists():
        print(f"❌ Gate 脚本不存在: {gate_script}")
        sys.exit(1)

    print(f"{Color.BLUE}=== {gate_name.capitalize()}Gate 执行（缓存未命中或已失效） ==={Color.END}")

    # 执行 Gate
    result = subprocess.run(
        [sys.executable, str(gate_script)] + gate_args,
        env=os.environ
    )

    # 更新缓存
    if result.returncode == 0:
        # Gate 通过，更新 fingerprint
        update_gate_fingerprint(cr_path, gate_name, 'passed')
        print(f"{Color.BLUE}ℹ️  已更新 {gate_name} Gate 缓存{Color.END}")
    else:
        # Gate 失败，使下游缓存失效
        invalidate_downstream_gates(cr_path, gate_name)

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
