#!/usr/bin/env python3
"""
ANSI 颜色输出工具
统一控制台文本颜色，支持跨脚本一致性
"""


class Color:
    """ANSI 颜色代码（统一管理，避免 22 个脚本重复定义）"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    END = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

    @classmethod
    def green(cls, text: str) -> str:
        """绿色文本"""
        return f"{cls.GREEN}{text}{cls.END}"

    @classmethod
    def yellow(cls, text: str) -> str:
        """黄色文本"""
        return f"{cls.YELLOW}{text}{cls.END}"

    @classmethod
    def red(cls, text: str) -> str:
        """红色文本"""
        return f"{cls.RED}{text}{cls.END}"

    @classmethod
    def blue(cls, text: str) -> str:
        """蓝色文本"""
        return f"{cls.BLUE}{text}{cls.END}"

    @classmethod
    def cyan(cls, text: str) -> str:
        """青色文本"""
        return f"{cls.CYAN}{text}{cls.END}"

    @classmethod
    def bold(cls, text: str) -> str:
        """加粗文本"""
        return f"{cls.BOLD}{text}{cls.END}"

    @classmethod
    def dim(cls, text: str) -> str:
        """暗淡文本"""
        return f"{cls.DIM}{text}{cls.END}"
