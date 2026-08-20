#!/usr/bin/env python3
"""
Human Checkpoint — 人工硬关卡

来源：企业微信团队"AI代码生成率94%"经验。

核心原则：信任但不放任。在关键节点强制等待人工确认。

4 个硬关卡：
  HK-0 现场快报：接力入口进入后第一时间
  HK-1 PENDING 条目确认：需求拆解完成后
  HK-2 沉淀确认：TECH_SPEC.md 落盘前
  HK-3 commit 文案确认：git commit 前

用法：
  python human_checkpoint.py HK-0 --cr-id CR-001 --context "当前进度：已完成设计稿分析"
  python human_checkpoint.py HK-1 --cr-id CR-001
  python human_checkpoint.py HK-2 --cr-id CR-001
  python human_checkpoint.py HK-3 --cr-id CR-001 --context "commit message..."
"""

import argparse
import sys
import yaml
from pathlib import Path
from common import load_yaml

# =============================================================================
# 配置
# =============================================================================

CHECKPOINTS = {
    "HK-0": {
        "name": "现场快报",
        "description": "接力入口进入后第一时间",
        "wait_for": "用户确认进度/改 N",
        "prompt": """
当前进度：{context}

请确认：
1. 以上进度是否正确？
2. 是否有需要调整的地方（N）？
3. 可以继续下一步吗？

输入 'go' 或 '继续' 继续执行，
输入 'N: 具体说明' 修改进度，
输入 'stop' 暂停。
""",
        "auto_proceed_allowed": False
    },
    "HK-1": {
        "name": "PENDING 条目确认",
        "description": "需求拆解完成后",
        "wait_for": "用户'确认/改 xxx'",
        "prompt": """
需求拆解已完成，请逐条确认：

{pending_items}

请对每个条目确认：
- 输入 'ok' 或 '✓' 确认
- 输入 'N: 修改说明' 调整
- 输入 'del' 删除

所有条目确认后，输入 'go' 继续执行。
""",
        "auto_proceed_allowed": False
    },
    "HK-2": {
        "name": "沉淀确认",
        "description": "TECH_SPEC.md 落盘前",
        "wait_for": "用户'沉淀 ok/通过'",
        "prompt": """
TECH_SPEC.md 沉淀内容预览：

{tech_spec_preview}

请检查：
1. 内容是否准确反映了本次开发？
2. 是否有遗漏或错误？
3. 可以落盘吗？

输入 'ok' 或 '通过' 确认落盘，
输入 'N: 具体说明' 要求修改。
""",
        "auto_proceed_allowed": False
    },
    "HK-3": {
        "name": "commit 文案确认",
        "description": "git commit 前",
        "wait_for": "用户'提交/go'",
        "prompt": """
三段式 commit 文案预览：

{commit_message}

AI 署名：[AI-{model_name}]
代码生成率：{code_gen_rate}

请检查：
1. commit 信息是否准确？
2. 范围是否正确？
3. 可以提交吗？

输入 'go' 或 '提交' 执行 commit，
输入 'N: 具体说明' 修改文案。
""",
        "auto_proceed_allowed": False
    }
}

# governance.config.yml 多路径查找（适配 skill/ 和项目根目录）
_config_paths = [
    Path(__file__).parent.parent / "governance.config.yml",  # skill/ 下
    Path(__file__).parent.parent.parent / "governance.config.yml",  # 项目根目录下
]
DEFAULT_CONFIG_PATH = next((p for p in _config_paths if p.exists()), _config_paths[0])


# =============================================================================
# 工具函数
# =============================================================================

def load_checkpoints_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict:
    """从 governance.config.yml 加载 checkpoint 配置"""
    if not config_path.exists():
        return CHECKPOINTS

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = load_yaml(f)
        if config and "human_checkpoints" in config:
            # 用配置文件覆盖默认配置
            custom = {}
            for cp in config["human_checkpoints"]:
                custom[cp["id"]] = cp
            return {**CHECKPOINTS, **custom}
    except Exception:
        pass

    return CHECKPOINTS


def find_tech_spec(cr_dir: Path) -> Path | None:
    """查找 TECH_SPEC.md"""
    candidates = [
        cr_dir / "TECH_SPEC.md",
        cr_dir / "docs" / "TECH_SPEC.md",
        cr_dir.parent.parent / "docs" / "knowledge-base" / "TECH_SPEC.md",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def find_subtasks(cr_dir: Path) -> Path | None:
    """查找 subtasks.json"""
    candidates = [
        cr_dir / "subtasks.json",
        cr_dir / "context" / "subtasks.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


# =============================================================================
# 核心逻辑
# =============================================================================

def run_checkpoint(
    checkpoint_id: str,
    cr_id: str | None = None,
    context: str = "",
    auto_approve: bool = False,
    config_path: Path = DEFAULT_CONFIG_PATH
) -> dict:
    """
    执行人工硬关卡。

    参数：
        checkpoint_id: HK-0 / HK-1 / HK-2 / HK-3
        cr_id: CR 编号（如 CR-001）
        context: 额外上下文信息
        auto_approve: 是否自动批准（仅用于测试）
        config_path: governance.config.yml 路径

    返回：
        {"approved": bool, "message": str}
    """

    checkpoints = load_checkpoints_config(config_path)

    if checkpoint_id not in checkpoints:
        print(f"❌ 未知关卡：{checkpoint_id}")
        print(f"可用关卡：{', '.join(checkpoints.keys())}")
        return {"approved": False, "message": f"未知关卡 {checkpoint_id}"}

    cp = checkpoints[checkpoint_id]

    print("=" * 60)
    print(f"🔴 人工硬关卡：{checkpoint_id} — {cp['name']}")
    print("=" * 60)
    print(f"触发条件：{cp['description']}")
    print(f"等待用户：{cp['wait_for']}")
    print()

    # HK-0: 现场快报
    if checkpoint_id == "HK-0":
        prompt = cp["prompt"].format(context=context or "（无额外上下文）")
        print(prompt)

    # HK-1: PENDING 条目确认
    elif checkpoint_id == "HK-1":
        pending_items = []
        if cr_id:
            # 尝试从 CR 目录加载
            cr_paths = [
                Path("DeliverHQ") / "change-requests" / cr_id,
                Path("change-requests") / cr_id,
            ]
            for cr_dir in cr_paths:
                if cr_dir.exists():
                    subtasks = find_subtasks(cr_dir)
                    if subtasks:
                        import json
                        try:
                            data = json.loads(subtasks.read_text(encoding="utf-8"))
                            for item in data.get("tasks", []):
                                if item.get("status") in ["pending", "PENDING"]:
                                    pending_items.append(
                                        f"- [{item.get('id', '?')}] {item.get('title', '?')}"
                                    )
                        except Exception:
                            pass
        if not pending_items:
            pending_items = ["- （无 PENDING 条目）"]
        prompt = cp["prompt"].format(pending_items="\n".join(pending_items))
        print(prompt)

    # HK-2: 沉淀确认
    elif checkpoint_id == "HK-2":
        preview = "（未找到 TECH_SPEC.md）"
        if cr_id:
            cr_paths = [
                Path("DeliverHQ") / "change-requests" / cr_id,
                Path("change-requests") / cr_id,
            ]
            for cr_dir in cr_paths:
                tech_spec = find_tech_spec(cr_dir)
                if tech_spec:
                    content = tech_spec.read_text(encoding="utf-8")
                    # 截取前 500 字
                    preview = content[:500] + "..." if len(content) > 500 else content
                    break
        prompt = cp["prompt"].format(tech_spec_preview=preview)
        print(prompt)

    # HK-3: commit 文案确认
    elif checkpoint_id == "HK-3":
        commit_message = context or "（未提供 commit 文案）"
        # 尝试从 context 中提取
        import re
        code_gen_match = re.search(r"代码生成率[：:]\s*(\d+%)", context or "")
        code_gen_rate = code_gen_match.group(1) if code_gen_match else "待统计"

        prompt = cp["prompt"].format(
            commit_message=commit_message,
            model_name="Claude/GPT",
            code_gen_rate=code_gen_rate
        )
        print(prompt)

    print()
    print("-" * 60)

    if auto_approve:
        print("⚠️ AUTO-APPROVE 模式：自动批准继续执行")
        return {"approved": True, "message": "自动批准"}

    # 交互式等待用户输入
    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消")
            return {"approved": False, "message": "用户取消"}

        if user_input.lower() in ["go", "继续", "ok", "通过", "提交"]:
            print("✅ 人工确认通过")
            return {"approved": True, "message": "人工确认通过"}

        elif user_input.lower().startswith("n:"):
            # 需要修改
            modification = user_input[2:].strip()
            print(f"📝 要求修改：{modification}")
            return {"approved": False, "message": f"需要修改：{modification}"}

        elif user_input.lower() == "stop":
            print("⏹️ 已暂停")
            return {"approved": False, "message": "用户暂停"}

        elif user_input.lower() in ["del", "删除"]:
            print("📝 标记为删除")
            continue

        else:
            print("请输入：'go' 继续 / 'N:说明' 修改 / 'stop' 暂停")


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Human Checkpoint — 人工硬关卡",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python human_checkpoint.py HK-0 --cr-id CR-001 --context "已完成设计稿分析"
  python human_checkpoint.py HK-1 --cr-id CR-001
  python human_checkpoint.py HK-2 --cr-id CR-001
  python human_checkpoint.py HK-3 --cr-id CR-001 --context "$(cat /tmp/commit_msg.txt)"

4 个关卡：
  HK-0 现场快报  — 接力入口进入后第一时间
  HK-1 PENDING确认 — 需求拆解完成后
  HK-2 沉淀确认  — TECH_SPEC.md 落盘前
  HK-3 commit确认 — git commit 前
        """
    )
    parser.add_argument(
        "checkpoint_id",
        choices=list(CHECKPOINTS.keys()),
        help="关卡 ID"
    )
    parser.add_argument(
        "--cr-id",
        help="CR 编号（如 CR-001）"
    )
    parser.add_argument(
        "--context",
        default="",
        help="额外上下文信息"
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="自动批准（仅用于测试）"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="governance.config.yml 路径"
    )

    args = parser.parse_args()

    result = run_checkpoint(
        checkpoint_id=args.checkpoint_id,
        cr_id=args.cr_id,
        context=args.context,
        auto_approve=args.auto_approve,
        config_path=args.config
    )

    # 返回退出码
    sys.exit(0 if result["approved"] else 1)


if __name__ == "__main__":
    main()
