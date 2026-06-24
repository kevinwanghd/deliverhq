#!/usr/bin/env python3
"""
deliverhq_home.py —— DeliverHQ home 目录确定性定位（agent 无关）

任何写产物的脚本都用本模块决定"产物落到哪个 DeliverHQ/ 目录"，
不依赖宿主 agent（Hermes/Claude/Codex/Gemini）、不依赖脚本安装位置、不靠读文档。

定位优先级（确定性，从高到低）：
  1. 显式 explicit 参数（如 --home）
  2. 环境变量 DELIVERHQ_HOME
  3. 从 start 目录向上查找已存在的 `DeliverHQ/` 目录 → 用它
  4. 从 start 目录向上查找项目根标志（.git / package.json / pyproject.toml /
     go.mod / Cargo.toml / pom.xml / *.sln），命中则用 <项目根>/DeliverHQ
  5. 兜底：<start>/DeliverHQ

返回的 home 目录可能尚不存在；调用方负责按需 mkdir。
纯标准库，Python 3.10+。
"""

import os
from pathlib import Path

PROJECT_ROOT_MARKERS = (
    ".git", "package.json", "pyproject.toml", "go.mod",
    "Cargo.toml", "pom.xml", "build.gradle",
)


def _has_marker(d: Path) -> bool:
    for m in PROJECT_ROOT_MARKERS:
        if (d / m).exists():
            return True
    # *.sln（.NET 解决方案）
    try:
        if any(d.glob("*.sln")):
            return True
    except OSError:
        pass
    return False


def resolve_home(explicit=None, start=None) -> Path:
    """确定性地解析 DeliverHQ home 目录（见模块 docstring 的优先级）。"""
    # 1. 显式
    if explicit:
        return Path(explicit).resolve()

    # 2. 环境变量
    env = os.environ.get("DELIVERHQ_HOME")
    if env:
        return Path(env).resolve()

    start_dir = Path(start).resolve() if start else Path.cwd()
    if start_dir.is_file():
        start_dir = start_dir.parent

    # 3. 向上找已存在的 DeliverHQ/
    for d in [start_dir] + list(start_dir.parents):
        cand = d / "DeliverHQ"
        if cand.is_dir():
            return cand.resolve()
        # 若 start 本身就在某个 DeliverHQ/ 里，直接用那个 DeliverHQ 根
        if d.name == "DeliverHQ":
            return d.resolve()

    # 4. 向上找项目根标志 → <根>/DeliverHQ
    for d in [start_dir] + list(start_dir.parents):
        if _has_marker(d):
            return (d / "DeliverHQ").resolve()

    # 5. 兜底
    return (start_dir / "DeliverHQ").resolve()


def cr_dir(home: Path, cr_id: str) -> Path:
    return Path(home) / "change-requests" / cr_id
