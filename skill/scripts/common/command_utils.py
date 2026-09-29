#!/usr/bin/env python3
"""
命令行 / git 输出解析工具
统一跨平台命令拆分与 `git status --porcelain -z` 解析
"""

import os
import shlex
import shutil
from typing import List, Sequence, Union


def split_command(command: Union[str, Sequence[str]]) -> List[str]:
    """把命令字符串拆成 argv（shell=False 使用）。

    Windows 下 shlex 的 POSIX 模式会把反斜杠当转义符吃掉
    （`pytest tests\\unit` → `testsunit`），因此在 nt 上使用非 POSIX 模式，
    并剥掉 token 两侧成对的引号。已是列表时原样复制返回。
    """
    if not isinstance(command, str):
        return list(command)
    posix = os.name != "nt"
    tokens = shlex.split(command, posix=posix)
    if posix:
        return tokens
    stripped = []
    for token in tokens:
        if len(token) >= 2 and token[0] == token[-1] and token[0] in ('"', "'"):
            token = token[1:-1]
        stripped.append(token)
    return stripped


def resolve_executable(argv: List[str]) -> List[str]:
    """Windows 下用 shutil.which 解析 argv[0]，使 npm/pnpm 等 .cmd shim 可直接执行。"""
    if os.name == "nt" and argv:
        found = shutil.which(argv[0])
        if found:
            return [found, *argv[1:]]
    return argv


def parse_porcelain_z(output: str) -> List[str]:
    """解析 `git -c core.quotepath=false status --porcelain -z` 输出，返回变更路径（重命名取新路径）。

    记录以 NUL 分隔，格式为 `XY <path>`；重命名/复制（X 或 Y 为 R/C）后面紧跟一个额外的原路径字段。
    """
    paths: List[str] = []
    records = output.split("\0")
    i = 0
    while i < len(records):
        record = records[i]
        i += 1
        if len(record) < 4:
            continue
        status, path = record[:2], record[3:]
        if "R" in status or "C" in status:
            i += 1  # 跳过原路径字段
        if path:
            paths.append(path.replace("\\", "/"))
    return paths
