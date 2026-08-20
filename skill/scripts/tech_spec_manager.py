#!/usr/bin/env python3
"""
TECH_SPEC Manager — 跨会话知识传承

来源：企业微信团队"AI代码生成率94%"经验。

核心原则：跨会话知识传承的载体。让"知识"和"代码"等量齐观。

三件套：
  1. TECH_SPEC.md — 永久知识（功能边界/模块地图/不变式）
  2. subtasks.json — 跨会话状态（每个子需求的状态/当前阶段/关联 commit）
  3. timeline.txt — 会话内事件流水（start / human-correction / commit）

用法：
  python tech_spec_manager.py init --cr-id CR-001
  python tech_spec_manager.py update --cr-id CR-001 --section "迭代历史"
  python tech_spec_manager.py status --cr-id CR-001
  python tech_spec_manager.py handover --cr-id CR-001
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from common import load_yaml

# =============================================================================
# 配置
# =============================================================================

TECH_SPEC_TEMPLATE = """# TECH_SPEC — {cr_id}

> 跨会话知识传承的单一事实源。
> 本文件由 `tech_spec_manager.py` 管理，git-tracked。

## 元数据

- **CR**: {cr_id}
- **创建时间**: {created_at}
- **最后更新**: {updated_at}
- **版本**: v1.0

---

## §0 AI 自检清单

> 给下次会话入场扫描。

- [ ] 确认当前阶段
- [ ] 确认 pending 项
- [ ] 确认不变式
- [ ] 确认模块地图

---

## §1 功能边界

> 哪些做、哪些不做（防越界）。

### 已确认做

-

### 确认不做

-

### 防越界规则

- 禁止在未批准范围内添加功能
- 禁止删除未确认的模块
- 禁止修改受保护路径

---

## §3 模块地图

> 文件 + 关键方法 + 调用链。

### 关键文件

| 文件 | 职责 | 关键方法 |
|------|------|---------|
| | | |

### 调用链

```
```

---

## §5 不变式

> 不能动的命名、文件清单、拦截边界。

### 不能动的命名

-

### 不能动的文件

-

### 拦截边界

-

---

## §7 演进事件

> 按时间线排列的 BUG-N / ITER-N / REV-N。

| 日期 | 事件 | 详情 |
|------|------|------|
| {created_at} | INIT | 初始创建 |

---

## §8 产物清单

> 每次 commit 改了什么。

| 日期 | CR | 改动范围 | commit hash |
|------|-----|---------|-------------|
| | | | |

---

## §9 版本号

- v1.0 — 初始版本
- v1.1 — （待更新）
- v2.0 — （baseline 合并）

---

*最后更新：{updated_at}*
*本文件由 `tech_spec_manager.py` 管理*
"""

SUBTASKS_TEMPLATE = {
    "version": "1.0",
    "cr_id": "",
    "created_at": "",
    "updated_at": "",
    "tasks": []
}

TIMELINE_TEMPLATE = """# Timeline — {cr_id}

> 会话内事件流水。由 `tech_spec_manager.py` 自动追加。

| 时间 | 事件类型 | 详情 |
|------|---------|------|
| {created_at} | START | 会话开始 |
"""

# =============================================================================
# 工具函数
# =============================================================================

def get_cr_dir(cr_id: str) -> Path:
    """获取 CR 目录"""
    candidates = [
        Path("DeliverHQ") / "change-requests" / cr_id,
        Path("change-requests") / cr_id,
    ]
    for d in candidates:
        if d.exists():
            return d
    # 如果不存在，尝试创建
    d = candidates[0]
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_tech_spec_path(cr_dir: Path) -> Path:
    """获取 TECH_SPEC.md 路径"""
    return cr_dir / "TECH_SPEC.md"


def get_subtasks_path(cr_dir: Path) -> Path:
    """获取 subtasks.json 路径"""
    return cr_dir / "subtasks.json"


def get_timeline_path(cr_dir: Path) -> Path:
    """获取 timeline.txt 路径"""
    return cr_dir / "timeline.txt"


def load_yaml_robust(path: Path) -> dict:
    """安全加载 YAML（容错）"""
    import yaml
    try:
        with open(path, "r", encoding="utf-8") as f:
            return load_yaml(f)
    except Exception:
        return {}


def save_yaml_robust(path: Path, data: dict):
    """安全保存 YAML"""
    import yaml
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


# =============================================================================
# 核心操作
# =============================================================================

def cmd_init(cr_id: str, force: bool = False) -> dict:
    """初始化 TECH_SPEC 三件套"""
    cr_dir = get_cr_dir(cr_id)
    tech_spec_path = get_tech_spec_path(cr_dir)
    subtasks_path = get_subtasks_path(cr_dir)
    timeline_path = get_timeline_path(cr_dir)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    results = []

    # TECH_SPEC.md
    if tech_spec_path.exists() and not force:
        results.append(f"⚠️  已存在：{tech_spec_path}")
    else:
        content = TECH_SPEC_TEMPLATE.format(
            cr_id=cr_id,
            created_at=now,
            updated_at=now
        )
        tech_spec_path.write_text(content, encoding="utf-8")
        results.append(f"✅ 创建：{tech_spec_path}")

    # subtasks.json
    if subtasks_path.exists() and not force:
        results.append(f"⚠️  已存在：{subtasks_path}")
    else:
        data = SUBTASKS_TEMPLATE.copy()
        data["cr_id"] = cr_id
        data["created_at"] = now
        data["updated_at"] = now
        subtasks_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        results.append(f"✅ 创建：{subtasks_path}")

    # timeline.txt
    if timeline_path.exists() and not force:
        results.append(f"⚠️  已存在：{timeline_path}")
    else:
        content = TIMELINE_TEMPLATE.format(
            cr_id=cr_id,
            created_at=now
        )
        timeline_path.write_text(content, encoding="utf-8")
        results.append(f"✅ 创建：{timeline_path}")

    return {"success": True, "results": results}


def cmd_add_task(cr_id: str, title: str, task_type: str = "new",
                 data_source: str = "", figma_node: str = "", depends_on: str = "") -> dict:
    """添加子任务"""
    cr_dir = get_cr_dir(cr_id)
    subtasks_path = get_subtasks_path(cr_dir)

    # 加载或创建
    if subtasks_path.exists():
        data = json.loads(subtasks_path.read_text(encoding="utf-8"))
    else:
        data = SUBTASKS_TEMPLATE.copy()
        data["cr_id"] = cr_id
        data["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 生成 ID
    task_id = f"TASK-{len(data['tasks']) + 1:03d}"

    task = {
        "id": task_id,
        "title": title,
        "type": task_type,
        "status": "pending",
        "data_source": data_source,
        "figma_node": figma_node,
        "depends_on": [d.strip() for d in depends_on.split(",") if d.strip()] if depends_on else []
    }

    data["tasks"].append(task)
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    subtasks_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"success": True, "task_id": task_id, "task": task}


def cmd_update_task(cr_id: str, task_id: str, status: str = None,
                    title: str = None) -> dict:
    """更新子任务状态"""
    cr_dir = get_cr_dir(cr_id)
    subtasks_path = get_subtasks_path(cr_dir)

    if not subtasks_path.exists():
        return {"success": False, "error": "subtasks.json 不存在"}

    data = json.loads(subtasks_path.read_text(encoding="utf-8"))

    for task in data["tasks"]:
        if task["id"] == task_id:
            if status:
                task["status"] = status
            if title:
                task["title"] = title
            data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            subtasks_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"success": True, "task": task}

    return {"success": False, "error": f"未找到任务 {task_id}"}


def cmd_append_timeline(cr_id: str, event_type: str, detail: str) -> dict:
    """追加时间线事件"""
    cr_dir = get_cr_dir(cr_id)
    timeline_path = get_timeline_path(cr_dir)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 事件类型映射
    type_icons = {
        "start": "START",
        "human_correction": "HUMAN-CORRECTION",
        "commit": "COMMIT",
        "bug": "BUG",
        "iteration": "ITER",
        "revision": "REV",
    }

    icon = type_icons.get(event_type, event_type.upper())

    line = f"| {now} | {icon} | {detail} |"

    if not timeline_path.exists():
        timeline_path.write_text(
            TIMELINE_TEMPLATE.format(cr_id=cr_id, created_at=now),
            encoding="utf-8"
        )

    with open(timeline_path, "a", encoding="utf-8") as f:
        f.write(f"\n{line}")

    return {"success": True, "line": line}


def cmd_status(cr_id: str) -> dict:
    """查看状态"""
    cr_dir = get_cr_dir(cr_id)

    results = {
        "cr_id": cr_id,
        "files": {}
    }

    # TECH_SPEC.md
    tech_spec_path = get_tech_spec_path(cr_dir)
    if tech_spec_path.exists():
        content = tech_spec_path.read_text(encoding="utf-8")
        # 提取版本和更新时间
        version = "v1.0"
        updated = ""
        for line in content.split("\n"):
            if line.startswith("- **版本**:"):
                version = line.split(":", 1)[1].strip()
            if line.startswith("*最后更新"):
                updated = line.split("：", 1)[-1].rstrip("*")
        results["files"]["TECH_SPEC.md"] = {
            "exists": True,
            "version": version,
            "updated": updated
        }
    else:
        results["files"]["TECH_SPEC.md"] = {"exists": False}

    # subtasks.json
    subtasks_path = get_subtasks_path(cr_dir)
    if subtasks_path.exists():
        data = json.loads(subtasks_path.read_text(encoding="utf-8"))
        tasks = data.get("tasks", [])
        pending = sum(1 for t in tasks if t.get("status") == "pending")
        done = sum(1 for t in tasks if t.get("status") == "done")
        results["files"]["subtasks.json"] = {
            "exists": True,
            "total": len(tasks),
            "pending": pending,
            "done": done
        }
    else:
        results["files"]["subtasks.json"] = {"exists": False}

    # timeline.txt
    timeline_path = get_timeline_path(cr_dir)
    if timeline_path.exists():
        lines = timeline_path.read_text(encoding="utf-8").split("\n")
        results["files"]["timeline.txt"] = {
            "exists": True,
            "events": len([l for l in lines if l.startswith("|")]) - 1  # 减去表头
        }
    else:
        results["files"]["timeline.txt"] = {"exists": False}

    return results


def cmd_handover(cr_id: str) -> dict:
    """生成交接报告"""
    cr_dir = get_cr_dir(cr_id)

    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append(f"交接报告 — {cr_id}")
    report_lines.append("=" * 60)
    report_lines.append("")

    # TECH_SPEC.md 摘要
    tech_spec_path = get_tech_spec_path(cr_dir)
    if tech_spec_path.exists():
        content = tech_spec_path.read_text(encoding="utf-8")
        report_lines.append("§1 功能边界：")
        # 提取功能边界部分
        in_section = False
        for line in content.split("\n"):
            if "§1 功能边界" in line:
                in_section = True
            elif in_section and line.startswith("## §"):
                break
            elif in_section and line.strip():
                report_lines.append(f"  {line}")
        report_lines.append("")

    # subtasks.json 摘要
    subtasks_path = get_subtasks_path(cr_dir)
    if subtasks_path.exists():
        data = json.loads(subtasks_path.read_text(encoding="utf-8"))
        tasks = data.get("tasks", [])
        pending = [t for t in tasks if t.get("status") == "pending"]
        done = [t for t in tasks if t.get("status") == "done"]

        report_lines.append(f"子任务状态：{len(done)} 完成 / {len(pending)} 待处理")
        if pending:
            report_lines.append("  待处理：")
            for t in pending[:5]:  # 最多显示 5 个
                report_lines.append(f"    - [{t['id']}] {t['title']}")
            if len(pending) > 5:
                report_lines.append(f"    ... 还有 {len(pending) - 5} 个")
        report_lines.append("")

    # timeline.txt 摘要
    timeline_path = get_timeline_path(cr_dir)
    if timeline_path.exists():
        lines = timeline_path.read_text(encoding="utf-8").split("\n")
        report_lines.append("最近事件：")
        for line in lines[-5:]:  # 最近 5 条
            if line.startswith("|"):
                report_lines.append(f"  {line}")
        report_lines.append("")

    report_lines.append("=" * 60)
    report_lines.append("入场操作：")
    report_lines.append("  1. 阅读 TECH_SPEC.md 确认功能边界")
    report_lines.append("  2. 查看 subtasks.json 确认待处理项")
    report_lines.append("  3. 查看 timeline.txt 了解历史")
    report_lines.append("  4. 运行 HK-0 现场快报确认进度")
    report_lines.append("=" * 60)

    report = "\n".join(report_lines)
    print(report)

    return {"success": True, "report": report}


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="TECH_SPEC Manager — 跨会话知识传承",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python tech_spec_manager.py init --cr-id CR-001
  python tech_spec_manager.py add-task --cr-id CR-001 --title "实现登录功能" --type new
  python tech_spec_manager.py update-task --cr-id CR-001 --task-id TASK-001 --status done
  python tech_spec_manager.py timeline --cr-id CR-001 --event commit --detail "完成登录功能"
  python tech_spec_manager.py status --cr-id CR-001
  python tech_spec_manager.py handover --cr-id CR-001
        """
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # init
    p_init = subparsers.add_parser("init", help="初始化 TECH_SPEC 三件套")
    p_init.add_argument("--cr-id", required=True, help="CR 编号")
    p_init.add_argument("--force", action="store_true", help="强制覆盖")

    # add-task
    p_add = subparsers.add_parser("add-task", help="添加子任务")
    p_add.add_argument("--cr-id", required=True, help="CR 编号")
    p_add.add_argument("--title", required=True, help="任务标题")
    p_add.add_argument("--type", default="new", choices=["new", "modify", "ignore"], help="任务类型")
    p_add.add_argument("--data-source", default="", help="数据来源")
    p_add.add_argument("--figma-node", default="", help="Figma 节点 ID")
    p_add.add_argument("--depends-on", default="", help="依赖任务（逗号分隔）")

    # update-task
    p_update = subparsers.add_parser("update-task", help="更新子任务")
    p_update.add_argument("--cr-id", required=True, help="CR 编号")
    p_update.add_argument("--task-id", required=True, help="任务 ID")
    p_update.add_argument("--status", choices=["pending", "in_progress", "done"], help="新状态")
    p_update.add_argument("--title", help="新标题")

    # timeline
    p_timeline = subparsers.add_parser("timeline", help="追加时间线事件")
    p_timeline.add_argument("--cr-id", required=True, help="CR 编号")
    p_timeline.add_argument("--event", required=True,
                           choices=["start", "human_correction", "commit", "bug", "iteration", "revision"],
                           help="事件类型")
    p_timeline.add_argument("--detail", required=True, help="事件详情")

    # status
    p_status = subparsers.add_parser("status", help="查看状态")
    p_status.add_argument("--cr-id", required=True, help="CR 编号")

    # handover
    p_handover = subparsers.add_parser("handover", help="生成交接报告")
    p_handover.add_argument("--cr-id", required=True, help="CR 编号")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    result = None

    if args.command == "init":
        result = cmd_init(args.cr_id, args.force)
    elif args.command == "add-task":
        result = cmd_add_task(
            args.cr_id, args.title, args.type,
            args.data_source, args.figma_node, args.depends_on
        )
    elif args.command == "update-task":
        result = cmd_update_task(
            args.cr_id, args.task_id, args.status, args.title
        )
    elif args.command == "timeline":
        result = cmd_append_timeline(
            args.cr_id, args.event, args.detail
        )
    elif args.command == "status":
        result = cmd_status(args.cr_id)
    elif args.command == "handover":
        result = cmd_handover(args.cr_id)

    if result:
        if "error" in result and not result["success"]:
            print(f"❌ {result['error']}")
            sys.exit(1)
        elif result.get("results"):
            for r in result["results"]:
                print(r)
        elif "report" in result:
            pass  # 已在 cmd_handover 中打印
        elif args.command == "status":
            # 格式化输出
            import json
            print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
