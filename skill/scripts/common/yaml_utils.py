#!/usr/bin/env python3
"""
YAML 加载工具
统一 YAML 加载逻辑，统一错误处理和编码处理
"""

import re
from pathlib import Path
from typing import IO, Any, Dict, List, Optional, Union
import yaml


_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _looks_like_yaml_text(value: str) -> bool:
    """明确是 YAML 文本（而非路径）：含换行或 `key: value` 结构。"""
    if "\n" in value:
        return True
    if _looks_like_path(value):
        return False
    return ": " in value or value.rstrip().endswith(":")


def _looks_like_path(value: str) -> bool:
    """单行字符串看起来像文件路径（盘符、分隔符、yml/yaml 后缀等）。"""
    if "\n" in value:
        return False
    v = value.strip()
    if not v:
        return False
    if _DRIVE_RE.match(v) or v.startswith(("/", ".", "~", "\\")):
        return True
    if v.lower().endswith((".yml", ".yaml", ".json")):
        return True
    return ("/" in v or "\\" in v) and ": " not in v


def _safe_exists(value: str) -> bool:
    try:
        return Path(value).exists()
    # risk:swallowed-exception reason:"非法路径字符串视为不存在，交由文本/路径判定继续处理" owner:@deliverhq reviewed:2026-09-29
    except (OSError, ValueError):
        return False


def load_yaml(path: Union[str, Path, IO]) -> Dict[str, Any]:
    """
    安全加载单个 YAML 文件或解析 YAML 字符串内容

    Args:
        path: YAML 文件路径，或包含 YAML 内容的字符串

    Returns:
        解析后的字典；文件不存在、解析失败或顶层不是映射时返回空字典

    统一的加载模式：
    - 统一使用 UTF-8 编码
    - 统一返回空字典而非 None / list / 标量
    - 统一异常处理
    - 支持传入文件路径（Path/str）或 YAML 字符串内容；
      看起来像路径的字符串（盘符、分隔符、.yml 后缀）一律按路径处理，不存在返回 {}
    """
    try:
        if hasattr(path, "read"):
            # 兼容调用方传入已打开的文件对象
            data = yaml.safe_load(path.read())
        elif isinstance(path, str) and ("\n" in path or not _safe_exists(path)):
            # 只有明确是 YAML 文本时才按文本解析；像路径但不存在 → {}
            if not _looks_like_yaml_text(path):
                return {}
            data = yaml.safe_load(path)
        else:
            p = Path(path)
            if not p.exists():
                return {}
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    # risk:swallowed-exception reason:"约定以空字典表示加载失败，调用方据此降级或阻断" owner:@deliverhq reviewed:2026-09-29
    except (yaml.YAMLError, OSError, ValueError, TypeError):
        # 调用方通过空字典判断加载失败
        return {}


def load_yaml_all(path: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    安全加载多文档 YAML 文件（使用 yaml.safe_load_all）

    Args:
        path: YAML 文件路径，或包含多文档 YAML 内容的字符串（含换行）

    Returns:
        文档列表，文件不存在或解析失败时返回空列表
    """
    try:
        if isinstance(path, str) and "\n" in path:
            content = path
        else:
            p = Path(path)
            if not p.exists():
                return []
            content = p.read_text(encoding="utf-8")
        docs = list(yaml.safe_load_all(content))
        return [doc for doc in docs if doc]  # 过滤空文档
    # risk:swallowed-exception reason:"约定以空列表表示多文档加载失败，调用方据此降级" owner:@deliverhq reviewed:2026-09-29
    except (yaml.YAMLError, OSError, ValueError, TypeError):
        return []


def load_yaml_optional(
    path: Union[str, Path],
    default: Any = None
) -> Any:
    """
    可选 YAML 加载（用于测试场景，需要区分"不存在"和"空文件"）

    Args:
        path: YAML 文件路径
        default: 文件不存在时的默认值

    Returns:
        解析后的值，或默认值
    """
    try:
        p = Path(path)
        if not p.exists():
            return default
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception:
        return default
