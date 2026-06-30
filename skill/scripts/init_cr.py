#!/usr/bin/env python3
"""
CR 初始化脚本
从 CR-TEMPLATE 复制并自动替换变量，降低使用门槛
"""


import shutil
import subprocess
import sys
import os
from pathlib import Path
from typing import Iterable, List
from datetime import datetime

from cr_state import create_state, set_worktree_path
from runtime_support import ensure_cr_runtime_dirs

DELIVERHQ_ROOT = Path(__file__).resolve().parent.parent
CHANGE_REQUESTS_DIR = DELIVERHQ_ROOT / "change-requests"
WORKTREE_SCRIPT = DELIVERHQ_ROOT / "scripts" / "worktree_manager.py"
VALID_LANES = {"fast", "standard", "high-risk"}


def _print(message: str):
    print(message)


def _parse_args(args: List[str]):
    cr_id = None
    cr_name = None
    requester = ""
    lane = "standard"
    use_worktree = None
    home = None

    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--worktree":
            use_worktree = True
        elif arg == "--no-worktree":
            use_worktree = False
        elif arg == "--lane" and index + 1 < len(args):
            lane = args[index + 1]
            index += 1
        elif arg.startswith("--lane="):
            lane = arg.split("=", 1)[1]
        elif arg == "--home" and index + 1 < len(args):
            home = args[index + 1]
            index += 1
        elif arg.startswith("--home="):
            home = arg.split("=", 1)[1]
        elif cr_id is None:
            cr_id = arg
        elif cr_name is None:
            cr_name = arg
        elif not requester:
            requester = arg
        index += 1

    if cr_id is None or cr_name is None:
        raise ValueError("缺少 CR-ID 或 CR-NAME")

    if lane not in VALID_LANES:
        raise ValueError(f"无效 lane: {lane}，可选: {', '.join(sorted(VALID_LANES))}")

    if use_worktree is None:
        use_worktree = lane in {"standard", "high-risk"}

    return cr_id, cr_name, requester, lane, use_worktree, home


def _resolve_home(home_arg):
    """解析 DeliverHQ home（产物落点），agent 无关、确定性自动定位。

    委托 deliverhq_home.resolve_home：--home > DELIVERHQ_HOME > 向上找已有
    DeliverHQ/ > 项目根标志/DeliverHQ > 兜底 cwd/DeliverHQ。总能确定性落到 DeliverHQ/。
    """
    from deliverhq_home import resolve_home
    return resolve_home(explicit=home_arg, start=Path.cwd())


def _check_first_time_setup(home_dir: Path) -> bool:
    """首次使用检测：CONTEXT.md 不存在 → 停下来问要不要扫描既有代码。

    这是老项目护栏 B1 的入口——一次性投资 15-50k tokens 扫描既有代码，
    生成 CONTEXT.md（技术栈/命名风格/既有抽象/禁动清单），后续所有 CR 读它，
    避免重复实现/破坏既有抽象。
    """
    context_file = home_dir / "docs" / "CONTEXT.md"

    if context_file.exists():
        return True  # 已有 CONTEXT，直接继续

    _print("\n🔍 检测到首次在本项目使用 DeliverHQ")
    _print("")
    _print("建议选项：")
    _print("  1. 扫描既有代码生成 CONTEXT.md（15-50k tokens，一次性投资）")
    _print("     → 后续所有 CR 都读这个文件，避免重复实现/破坏既有抽象")
    _print("  2. 跳过扫描（不推荐，除非是全新项目）")
    _print("")

    choice = input("选择 [1/2，默认1]: ").strip() or "1"

    if choice == "1":
        _print("\n📊 预估 token 消耗：15k-50k（取决于项目规模）")
        _print("   Claude Sonnet 约 $0.5-1.5，一次性成本")
        proceed = input("继续？[Y/n]: ").strip().lower()
        if proceed in ("", "y", "yes"):
            _print("\n🔄 启动扫描...")
            scan_script = DELIVERHQ_ROOT / "scripts" / "scan_legacy.py"
            result = subprocess.run(
                [sys.executable, str(scan_script),
                 "--project-root", str(home_dir.parent),
                 "--out", str(home_dir / "docs")],
                cwd=str(home_dir.parent),
                env={"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", **os.environ}
            )
            if result.returncode == 0:
                _print("✅ CONTEXT.md 已生成")
                return True
            else:
                _print("⚠️  扫描失败，但可以继续（后续可手动运行 scan_legacy.py）")
                return True

    _print("⏭  已跳过扫描（可稍后运行 scan_legacy.py）")
    return True


def _replace_template_vars(target_dir: Path, replacements: dict) -> int:
    _print("\n🔄 替换模板变量...")
    replaced_count = 0

    for file_path in target_dir.rglob("*"):
        if not file_path.is_file() or file_path.suffix not in [".md", ".yml", ".yaml", ".html"]:
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
            original = content
            for placeholder, value in replacements.items():
                content = content.replace(placeholder, value)

            if content != original:
                file_path.write_text(content, encoding="utf-8")
                replaced_count += 1
                _print(f"  ✓ {file_path.relative_to(target_dir)}")
        except Exception as exc:
            _print(f"  ⚠ 跳过 {file_path}: {exc}")

    return replaced_count


def _create_state(target_dir: Path, cr_id: str, cr_name: str, requester: str, lane: str):
    owner = requester or "human"
    create_state(target_dir, cr_id, cr_name, lane=lane, owner=owner)
    _print(f"🧭 已创建 state.yml（lane={lane}）")


def _create_runtime_dirs(target_dir: Path):
    created = ensure_cr_runtime_dirs(target_dir)
    if created:
        _print("📦 已创建运行时目录:")
        for directory in created:
            _print(f"  - {directory.relative_to(target_dir)}")


def _create_worktree(cr_id: str, project_root: Path):
    _print("\n🌲 创建 worktree...")
    result = subprocess.run(
        [sys.executable, str(WORKTREE_SCRIPT), "create", cr_id],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        cwd=str(project_root),
    )

    if result.returncode == 0:
        _print("✅ Worktree 创建成功")
        _print(f"📂 切换到 worktree: cd .claude/worktrees/{cr_id}")
        return project_root / ".claude" / "worktrees" / cr_id

    _print(f"⚠️  Worktree 创建失败: {result.stderr.strip()}")
    _print(f"   可以稍后手动创建: python scripts/worktree_manager.py create {cr_id}")
    return None


def init_cr(cr_id, cr_name, requester="", lane="standard", use_worktree=False, home=None):
    """初始化新 CR。

    模板源恒为 skill 包内的 CR-TEMPLATE；产物落点为 <home>/change-requests/<cr_id>。
    home 为 DeliverHQ 治理目录（如 <项目根>/DeliverHQ），不在 skill 安装目录里散落。
    """

    template_dir = CHANGE_REQUESTS_DIR / "CR-TEMPLATE"          # 模板源：恒在 skill 包内
    home_dir = Path(home).resolve() if home else DELIVERHQ_ROOT  # 产物落点：DeliverHQ home
    target_dir = home_dir / "change-requests" / cr_id

    if target_dir.exists():
        _print(f"❌ 错误: {target_dir} 已存在")
        return False

    if not template_dir.exists():
        _print(f"❌ 错误: 模板目录不存在: {template_dir}")
        return False

    (home_dir / "change-requests").mkdir(parents=True, exist_ok=True)
    _print(f"📁 复制模板 {template_dir} → {target_dir}")
    shutil.copytree(template_dir, target_dir)

    today = datetime.now().strftime("%Y-%m-%d")
    replacements = {
        "{{CR_ID}}": cr_id,
        "{{CR_NAME}}": cr_name,
        "{{CR-ID}}": cr_id,
        "{{date}}": today,
        "{{requester}}": requester or "待填写",
    }

    replaced_count = _replace_template_vars(target_dir, replacements)
    _create_state(target_dir, cr_id, cr_name, requester, lane)
    _create_runtime_dirs(target_dir)

    _print(f"\n✅ CR 初始化完成: {target_dir}")
    _print(f"📝 已替换 {replaced_count} 个文件中的变量")

    if use_worktree:
        project_root = home_dir.parent  # home_dir 是 <项目根>/DeliverHQ，项目根是其父目录
        worktree_path = _create_worktree(cr_id, project_root)
        if worktree_path is not None:
            set_worktree_path(target_dir, str(worktree_path.resolve()))

    _print("\n📋 下一步:")
    _print(f"1. 编辑 {target_dir}/request.md 填写需求")
    _print(f"2. 让 Spec Agent 生成 acceptance-spec.md")
    _print(f"3. 运行门禁检查: python DeliverHQ/scripts/pre_dev_gate.py {cr_id}")
    if use_worktree:
        _print(f"4. 在 worktree 中开发: cd .claude/worktrees/{cr_id}")

    return True


def main():
    if len(sys.argv) < 3:
        _print("用法: python init_cr.py <CR-ID> <CR-NAME> [REQUESTER] [--home <项目根>/DeliverHQ] [--lane fast|standard|high-risk] [--worktree|--no-worktree]")
        _print("\n示例:")
        _print("  python DeliverHQ/scripts/init_cr.py CR-001 '实现用户登录日志功能' '产品经理'")
        _print("  python init_cr.py CR-002 '修复分页查询Bug' --home /path/to/proj/DeliverHQ --lane fast")
        _print("\n说明: --home 可省略。脚本会自动定位 DeliverHQ 目录(agent 无关):")
        _print("  --home > 环境变量 DELIVERHQ_HOME > 向上找已有 DeliverHQ/ > 项目根/DeliverHQ > cwd/DeliverHQ")
        sys.exit(1)

    try:
        cr_id, cr_name, requester, lane, use_worktree, home = _parse_args(sys.argv[1:])
    except ValueError as exc:
        _print(f"❌ 错误: {exc}")
        sys.exit(1)

    if not cr_id.startswith("CR-"):
        _print("❌ 错误: CR-ID 必须以 'CR-' 开头，如 CR-001")
        sys.exit(1)

    home_dir = _resolve_home(home)
    _print(f"📍 DeliverHQ home: {home_dir}")

    # 首次入场检测：CONTEXT.md 不存在 → 停下来问要不要扫描既有代码
    _check_first_time_setup(home_dir)

    success = init_cr(cr_id, cr_name, requester, lane, use_worktree, str(home_dir))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
