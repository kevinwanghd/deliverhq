#!/usr/bin/env python3
"""
YAML 加载工具
统一 YAML 加载逻辑，统一错误处理和编码处理
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import yaml


def load_yaml(path: Union[str, Path]) -> Dict[str, Any]:
    """
    安全加载单个 YAML 文件或解析 YAML 字符串内容

    Args:
        path: YAML 文件路径，或包含 YAML 内容的字符串

    Returns:
        解析后的字典，文件不存在或解析失败时返回空字典

    统一的加载模式：
    - 统一使用 UTF-8 编码
    - 统一返回空字典而非 None
    - 统一异常处理
    - 支持传入文件路径（Path/str）或 YAML 字符串内容
    """
    try:
        # 如果是字符串（而非路径），直接解析为 YAML
        if isinstance(path, str) and not Path(path).exists():
            # 可能是 YAML 字符串内容，不是文件路径
            if not path.startswith('/') and not path.startswith('.') and not path.startswith('~'):
                return yaml.safe_load(path) or {}
            # 可能是路径但不存在
            return {}
        p = Path(path)
        if not p.exists():
            return {}
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError) as e:
        # 静默失败，调用方可通过返回值判断
        return {}
    except Exception:
        return {}


def load_yaml_all(path: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    安全加载多文档 YAML 文件（使用 yaml.safe_load_all）

    Args:
        path: YAML 文件路径

    Returns:
        文档列表，文件不存在或解析失败时返回空列表
    """
    try:
        p = Path(path)
        if not p.exists():
            return []
        content = p.read_text(encoding="utf-8")
        docs = list(yaml.safe_load_all(content))
        return [doc for doc in docs if doc]  # 过滤空文档
    except (yaml.YAMLError, OSError) as e:
        return []
    except Exception:
        return {}


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
