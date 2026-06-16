#!/usr/bin/env python3
"""
DeliverHQ 骨架完整性自检
验证所有必需文件和目录是否存在
"""

import sys
from pathlib import Path

# 必需的文件清单（相对 DeliverHQ/ 目录）
REQUIRED_FILES = [
    # 入口层
    "CLAUDE.md",
    "AGENTS.md",
    "dir-graph.yaml",
    "README.md",
    ".ai-instructions",  # AI 平台集成指令

    # 组织记忆
    "docs/CONTEXT.md",
    "docs/architecture.md",
    "docs/interfaces.md",
    "docs/data-model.md",
    "docs/rules.md",
    "docs/decisions.md",
    "docs/mistake-book.md",
    "docs/verification.md",

    # 扫描报告
    "docs/reports/code-health-report.md",
    "docs/reports/legacy-scan-report.md",

    # CR 模板
    "change-requests/CR-TEMPLATE/request.md",
    "change-requests/CR-TEMPLATE/acceptance-spec.md",
    "change-requests/CR-TEMPLATE/context-summary.md",
    "change-requests/CR-TEMPLATE/implementation-plan.md",
    "change-requests/CR-TEMPLATE/test-plan.md",
    "change-requests/CR-TEMPLATE/quality-report.md",
    "change-requests/CR-TEMPLATE/writeback-report.md",
    "change-requests/CR-TEMPLATE/human-decisions.md",
    "change-requests/CR-TEMPLATE/traceability.yml",
    "change-requests/CR-TEMPLATE/exceptions.yml",

    # 设计模板
    "change-requests/CR-TEMPLATE/design/lo-fi-spec.md",
    "change-requests/CR-TEMPLATE/design/hi-fi-spec.md",
    "change-requests/CR-TEMPLATE/design/prototype.html",
    "change-requests/CR-TEMPLATE/design/design-decisions.md",
    "change-requests/CR-TEMPLATE/design/assets/README.md",

    # Gate 报告模板
    "change-requests/CR-TEMPLATE/specgate-report.md",
    "change-requests/CR-TEMPLATE/designgate-report.md",
    "change-requests/CR-TEMPLATE/context-window-report.md",
    "change-requests/CR-TEMPLATE/qualitygate-report.md",
    "change-requests/CR-TEMPLATE/writeback-gate-report.md",

    # 检查脚本
    "scripts/pre_dev_gate.py",
    "scripts/check_skeleton.py",
    "scripts/init_cr.py",
    "scripts/specgate.py",
    "scripts/designgate.py",
    "scripts/context_window_check.py",
    "scripts/qualitygate.py",
    "scripts/writeback_gate.py",
    "scripts/update_rule_maturity.py",
    "scripts/update_mistake_book.py",

    # 迁移与回滚文档
    "MIGRATION.md",
    "ROLLBACK.md",
]

# 必需的目录清单
REQUIRED_DIRS = [
    "docs",
    "docs/reports",
    "change-requests",
    "change-requests/CR-TEMPLATE",
    "change-requests/CR-TEMPLATE/design",
    "delivery",
    "_archived",
    "scripts",
]

def check_completeness(base_dir="."):
    """检查 DeliverHQ 骨架完整性"""
    base = Path(base_dir)

    print("=== DeliverHQ 骨架完整性检查 ===\n")

    missing_dirs = []
    missing_files = []

    # 检查目录
    print("[目录检查]")
    for dir_path in REQUIRED_DIRS:
        full_path = base / dir_path
        if full_path.exists():
            print(f"  ✓ {dir_path}")
        else:
            print(f"  ✗ {dir_path} (缺失)")
            missing_dirs.append(dir_path)

    # 检查文件
    print("\n[文件检查]")
    for file_path in REQUIRED_FILES:
        full_path = base / file_path
        if full_path.exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ {file_path} (缺失)")
            missing_files.append(file_path)

    # 统计
    print(f"\n[统计]")
    print(f"目录: {len(REQUIRED_DIRS) - len(missing_dirs)}/{len(REQUIRED_DIRS)}")
    print(f"文件: {len(REQUIRED_FILES) - len(missing_files)}/{len(REQUIRED_FILES)}")

    # 结果
    print(f"\n[结果]")
    if not missing_dirs and not missing_files:
        print("✅ DeliverHQ 骨架完整，可以用于新项目开发或老项目扫描。")
        return True
    else:
        print("❌ DeliverHQ 骨架不完整，请补齐缺失文件。")
        if missing_dirs:
            print(f"\n缺失目录 ({len(missing_dirs)}):")
            for d in missing_dirs:
                print(f"  - {d}")
        if missing_files:
            print(f"\n缺失文件 ({len(missing_files)}):")
            for f in missing_files:
                print(f"  - {f}")
        return False

def main():
    base_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    passed = check_completeness(base_dir)
    sys.exit(0 if passed else 1)

if __name__ == "__main__":
    main()
