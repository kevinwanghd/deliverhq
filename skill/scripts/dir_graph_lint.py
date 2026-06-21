#!/usr/bin/env python3
"""
dir_graph_lint.py - lint DeliverHQ dir-graph.yaml.

Checks the machine-readable directory contract stays usable without adding a
large policy engine.
"""

import sys
from pathlib import Path

import yaml

DELIVERHQ_ROOT = Path(__file__).resolve().parent.parent


REQUIRED_TOP_LEVEL = ["schema", "version", "workspace", "deliverhq_home", "entrypoints", "directories", "protected_paths", "agents"]
REQUIRED_HOME_PATHS = ["docs/", "change-requests/", "delivery/", "_archived/", "scripts/"]


def lint_dir_graph(path: Path):
    blockers = []
    warnings = []

    if not path.exists():
        return ["dir-graph.yaml 不存在"], warnings

    try:
        documents = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        data = documents[0] if documents else {}
    except Exception as exc:
        return ["dir-graph.yaml 解析失败: %s" % exc], warnings

    for key in REQUIRED_TOP_LEVEL:
        if key not in data:
            blockers.append("缺少顶层字段: %s" % key)

    home = data.get("deliverhq_home") or {}
    if home.get("dir") != "DeliverHQ":
        blockers.append("deliverhq_home.dir 必须为 DeliverHQ")
    if home.get("enforced") is not True:
        blockers.append("deliverhq_home.enforced 必须为 true")

    contained = home.get("contained_paths") or []
    for required in REQUIRED_HOME_PATHS:
        if required not in contained:
            blockers.append("deliverhq_home.contained_paths 缺少 %s" % required)

    agents = data.get("agents") or {}
    if not isinstance(agents, dict) or not agents:
        blockers.append("agents 必须是非空映射")
    else:
        for name, config in agents.items():
            if not isinstance(config, dict):
                blockers.append("agent %s 配置必须是映射" % name)
                continue
            reads = config.get("reads", [])
            writes = config.get("writes", [])
            if not reads:
                warnings.append("agent %s 未声明 reads" % name)
            if not writes:
                warnings.append("agent %s 未声明 writes" % name)
            for item in list(reads or []) + list(writes or []):
                if not isinstance(item, str):
                    blockers.append("agent %s 路径条目必须是字符串" % name)

    protected_paths = data.get("protected_paths") or []
    if not isinstance(protected_paths, list):
        blockers.append("protected_paths 必须是列表")
    elif not protected_paths:
        warnings.append("protected_paths 为空")

    text = path.read_text(encoding="utf-8")
    unresolved = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "{{" in stripped or "}}" in stripped:
            unresolved.append(stripped)
    if unresolved:
        warnings.append("dir-graph.yaml 含模板占位符: %s" % "; ".join(unresolved[:3]))

    return blockers, warnings


def main():
    path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DELIVERHQ_ROOT / "dir-graph.yaml"
    blockers, warnings = lint_dir_graph(path)

    print("=== dir-graph lint ===")
    print("file: %s" % path)
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print("  - %s" % warning)
    if blockers:
        print("BLOCKED:")
        for blocker in blockers:
            print("  - %s" % blocker)
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
