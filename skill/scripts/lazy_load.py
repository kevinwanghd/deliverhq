#!/usr/bin/env python3
"""
Lazy Load Support — 延迟加载工具函数

为 Gate 脚本提供轻量级文件检查，避免自动加载大文件内容。
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
import json
import yaml


def check_file_exists(file_path: Path) -> bool:
    """检查文件存在性（不读取内容）"""
    return file_path.exists() and file_path.is_file()


def get_file_summary(file_path: Path, max_lines: int = 10) -> Optional[str]:
    """只读取文件前 N 行作为摘要（用于 TLDR 或快速检查）"""
    if not check_file_exists(file_path):
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                lines.append(line.rstrip())
            return '\n'.join(lines)
    except Exception:
        return None


def check_evidence_files(cr_path: Path, required_files: List[str]) -> Dict[str, bool]:
    """
    轻量级 evidence 文件检查（不读取内容）

    Args:
        cr_path: CR 根目录
        required_files: 需要检查的文件列表（相对于 evidence/）

    Returns:
        {filename: exists} 字典
    """
    evidence_dir = cr_path / 'evidence'
    results = {}

    for filename in required_files:
        file_path = evidence_dir / filename
        results[filename] = check_file_exists(file_path)

    return results


def load_evidence_if_needed(cr_path: Path, filename: str, debug: bool = False) -> Optional[Dict[str, Any]]:
    """
    条件加载 evidence 文件（只在 debug 模式或需要时加载）

    Args:
        cr_path: CR 根目录
        filename: evidence 文件名
        debug: 是否强制加载

    Returns:
        文件内容（JSON 解析后）或 None
    """
    if not debug:
        # 非 debug 模式，只检查存在性，不读取内容
        file_path = cr_path / 'evidence' / filename
        if check_file_exists(file_path):
            return {"__lazy__": True, "file": str(file_path)}
        return None

    # debug 模式，读取完整内容
    file_path = cr_path / 'evidence' / filename
    if not check_file_exists(file_path):
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            if filename.endswith('.json'):
                return json.load(f)
            elif filename.endswith(('.yml', '.yaml')):
                return yaml.safe_load(f)
            else:
                return {"content": f.read()}
    except Exception:
        return None


def check_reports_lightweight(cr_path: Path, report_names: List[str]) -> Dict[str, str]:
    """
    轻量级报告检查（只读取 verdict，不读取全文）

    Args:
        cr_path: CR 根目录
        report_names: 报告文件名列表（如 ['review-report.md', 'quality-report.md']）

    Returns:
        {report_name: verdict} 字典，verdict 为 'PASS'/'BLOCKED'/'MISSING'
    """
    results = {}

    for report_name in report_names:
        report_path = cr_path / report_name

        if not check_file_exists(report_path):
            results[report_name] = 'MISSING'
            continue

        # 只读取前 50 行查找 verdict
        summary = get_file_summary(report_path, max_lines=50)
        if summary is None:
            results[report_name] = 'UNKNOWN'
            continue

        if '✅ PASS' in summary or 'PASS -' in summary:
            results[report_name] = 'PASS'
        elif '❌ BLOCKED' in summary or 'BLOCKED -' in summary:
            results[report_name] = 'BLOCKED'
        else:
            results[report_name] = 'UNKNOWN'

    return results


def load_traceability_summary(cr_path: Path, full_load: bool = False) -> Optional[Dict[str, Any]]:
    """
    加载 traceability.yml 的摘要或全文

    Args:
        cr_path: CR 根目录
        full_load: 是否加载全文（默认只加载前 20 行摘要）

    Returns:
        摘要或完整内容
    """
    traceability_path = cr_path / 'traceability.yml'

    if not check_file_exists(traceability_path):
        return None

    if not full_load:
        # 只读摘要（前 20 行）
        summary = get_file_summary(traceability_path, max_lines=20)
        if summary:
            try:
                return yaml.safe_load(summary)
            except Exception:
                return {"__summary__": summary}
        return None

    # 加载全文
    try:
        with open(traceability_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception:
        return None


# 兼容性：环境变量控制是否启用延迟加载
import os
LAZY_LOAD_ENABLED = os.getenv('DELIVERHQ_LAZY_LOAD', '1') == '1'
DEBUG_MODE = os.getenv('DELIVERHQ_DEBUG', '0') == '1'


def should_lazy_load() -> bool:
    """判断当前是否应该使用延迟加载"""
    return LAZY_LOAD_ENABLED and not DEBUG_MODE
