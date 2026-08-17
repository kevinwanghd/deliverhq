#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check Project Wiki Stale — 知识库陈旧检测脚本

来源：企业微信团队"AI代码生成率94%"经验。

核心功能：
  - SHA 基线缓存：记录每个文件上次审阅时的 SHA，变化时自动 flag "待复核"
  - 三色分诊清单：新增 / 删除 / 大改 三类信号分开列
  - pre-commit hook 阻断：有 stale 信号 → 阻止提交

用法：
  python check_project_wiki_stale.py scan --project-root .
  python check_project_wiki_stale.py scan --project-root . --check-scripts
  python check_project_wiki_stale.py reset --project-root .
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

# =============================================================================
# 配置
# =============================================================================

CACHE_FILE = ".wiki_sha_cache.json"
CACHE_DIR = Path.home() / ".deliverhq" / "cache"

# 扫描目录
SCRIPT_DIRS = ["skill/scripts", "scripts"]
WIKI_DIRS = [
    "skill/docs/knowledge-base/L1-项目总览",
    "skill/docs/knowledge-base/L2-模块级",
    "skill/docs/knowledge-base/L3-语义桥",
]

# 颜色
class Color:
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    END = '\033[0m'


# =============================================================================
# 核心函数
# =============================================================================

def compute_sha256(file_path: Path) -> str:
    """计算文件的 SHA256 前8位"""
    if not file_path.exists():
        return ""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()[:8]


def load_cache(cache_path: Path) -> Dict[str, str]:
    """加载 SHA 缓存"""
    if not cache_path.exists():
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache_path: Path, cache: Dict[str, str]):
    """保存 SHA 缓存"""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def scan_directory(base_dir: Path, sub_dirs: List[str]) -> Dict[str, Dict]:
    """扫描目录，返回文件 SHA 信息"""
    result = {}
    for sub_dir in sub_dirs:
        dir_path = base_dir / sub_dir
        if not dir_path.exists():
            continue

        for file_path in dir_path.rglob("*.py"):
            rel_path = str(file_path.relative_to(base_dir))
            sha = compute_sha256(file_path)
            result[rel_path] = {
                "sha": sha,
                "size": file_path.stat().st_size,
                "modified": file_path.stat().st_mtime,
            }

    return result


def diff_caches(old: Dict[str, Dict], new: Dict[str, Dict]) -> Dict[str, List]:
    """对比新旧缓存，返回变化"""
    old_keys = set(old.keys())
    new_keys = set(new.keys())

    result = {
        "added": sorted(list(new_keys - old_keys)),
        "removed": sorted(list(old_keys - new_keys)),
        "modified": [],
    }

    for key in old_keys & new_keys:
        if old[key]["sha"] != new[key]["sha"]:
            result["modified"].append({
                "path": key,
                "old_sha": old[key]["sha"],
                "new_sha": new[key]["sha"],
                "size_change": new[key]["size"] - old[key].get("size", 0),
            })

    result["modified"].sort(key=lambda x: x["path"])
    return result


def format_report(diff: Dict, verbose: bool = False) -> str:
    """格式化报告"""
    lines = []
    total_changes = len(diff["added"]) + len(diff["removed"]) + len(diff["modified"])

    if total_changes == 0:
        return f"{Color.GREEN}✅ 知识库无变化，所有文件保持最新{Color.END}"

    lines.append(f"{Color.YELLOW}⚠️  知识库有 {total_changes} 项变化{Color.END}\n")

    if diff["added"]:
        lines.append(f"{Color.GREEN}📗 新增文件 ({len(diff['added'])}):{Color.END}")
        for path in diff["added"]:
            lines.append(f"  + {path}")
        lines.append("")

    if diff["removed"]:
        lines.append(f"{Color.RED}📕 删除文件 ({len(diff['removed'])}):{Color.END}")
        for path in diff["removed"]:
            lines.append(f"  - {path}")
        lines.append("")

    if diff["modified"]:
        lines.append(f"{Color.YELLOW}📙 修改文件 ({len(diff['modified'])}):{Color.END}")
        for item in diff["modified"]:
            size_change = item.get("size_change", 0)
            size_str = f"+{size_change}" if size_change > 0 else str(size_change)
            lines.append(f"  ~ {item['path']} ({item['old_sha']} → {item['new_sha']}, {size_str} bytes)")

        if verbose:
            lines.append("")
            lines.append(f"{Color.BLUE}建议：{Color.END}")
            lines.append("  请检查这些文件是否需要更新对应的知识库文档。")
            lines.append("  可以运行以下命令重置缓存：")
            lines.append(f"    python check_project_wiki_stale.py reset")

    return "\n".join(lines)


# =============================================================================
# CLI
# =============================================================================

def main():
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    parser = argparse.ArgumentParser(
        description="Check Project Wiki Stale - Knowledge Base Drift Detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 扫描知识库变化
  python check_project_wiki_stale.py scan --project-root .

  # 详细模式
  python check_project_wiki_stale.py scan --project-root . -v

  # 扫描脚本目录
  python check_project_wiki_stale.py scan --project-root . --check-scripts

  # 重置缓存
  python check_project_wiki_stale.py reset --project-root .

  # dry-run（不保存缓存）
  python check_project_wiki_stale.py scan --project-root . --dry-run
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # scan
    p_scan = subparsers.add_parser("scan", help="扫描知识库变化")
    p_scan.add_argument("--project-root", type=Path, default=Path.cwd(), help="项目根目录")
    p_scan.add_argument("--check-scripts", action="store_true", help="同时检查脚本目录")
    p_scan.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    p_scan.add_argument("--dry-run", action="store_true", help="不保存缓存，只报告")
    p_scan.add_argument("--cache-dir", type=Path, help="缓存目录")

    # reset
    p_reset = subparsers.add_parser("reset", help="重置缓存")
    p_reset.add_argument("--project-root", type=Path, default=Path.cwd(), help="项目根目录")
    p_reset.add_argument("--cache-dir", type=Path, help="缓存目录")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "scan":
        project_root = args.project_root.resolve()

        # 确定缓存目录
        if args.cache_dir:
            cache_dir = args.cache_dir
        else:
            cache_dir = CACHE_DIR

        cache_path = cache_dir / f"{project_root.name}.wiki_sha_cache.json"

        # 扫描目录
        scan_dirs = WIKI_DIRS.copy()
        if args.check_scripts:
            scan_dirs.extend(SCRIPT_DIRS)

        print(f"{Color.BLUE}扫描目录：{', '.join(scan_dirs)}{Color.END}\n")

        new_cache = scan_directory(project_root, scan_dirs)
        old_cache = load_cache(cache_path)

        diff = diff_caches(old_cache, new_cache)

        # 输出报告
        print(format_report(diff, args.verbose))

        # 保存缓存（dry-run 模式不保存）
        if not args.dry_run:
            save_cache(cache_path, {k: v["sha"] for k, v in new_cache.items()})
            print(f"\n{Color.BLUE}缓存已更新：{cache_path}{Color.END}")

        # 退出码：有变化返回警告
        total_changes = len(diff["added"]) + len(diff["removed"]) + len(diff["modified"])
        sys.exit(1 if total_changes > 0 else 0)

    elif args.command == "reset":
        project_root = args.project_root.resolve()

        if args.cache_dir:
            cache_dir = args.cache_dir
        else:
            cache_dir = CACHE_DIR

        cache_path = cache_dir / f"{project_root.name}.wiki_sha_cache.json"

        if cache_path.exists():
            cache_path.unlink()
            print(f"{Color.GREEN}✅ 缓存已重置：{cache_path}{Color.END}")
        else:
            print(f"{Color.YELLOW}⚠️  缓存不存在：{cache_path}{Color.END}")


if __name__ == "__main__":
    main()
