"""
共享工具模块
提供 Color 类、YAML 加载等通用功能
"""

from .colors import Color
from .yaml_utils import load_yaml, load_yaml_all

__all__ = ["Color", "load_yaml", "load_yaml_all"]
