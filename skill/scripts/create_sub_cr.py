#!/usr/bin/env python3
"""
create_sub_cr.py — 子 CR 创建工具（Epic → Story 拆解）

设计原则：
- 数字后缀：CR-001-01/02/03（无上限，排序自然）
- Epic 只走轻量 spec（高层验收标准）
- 子 CR 独立走完整 Gate 链，天然隔离上下文

用法：
  python3 create_sub_cr.py CR-001 --title "OAuth 2.0 集成"
  python3 create_sub_cr.py CR-001 --title "JWT token 管理" --depends-on CR-001-01
  python3 create_sub_cr.py CR-001 --list           # 列出所有子 CR
  python3 create_sub_cr.py CR-001 --status         # 查看 Epic 完成状态
"""

import argparse
import shutil
import sys
sys.dont_write_bytecode = True
from datetime import datetime, timezone
from pathlib import Path

import yaml

from runtime_support import configure_console

DELIVERHQ_ROOT = Path(__file__).parent.parent
configure_console()


class Color:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'


def load_sub_crs(epic_path: Path) -> dict:
    """加载 sub-crs.yml（不存在则返回空结构）"""
    sub_crs_file = epic_path / 'sub-crs.yml'
    if sub_crs_file.exists():
        try:
            with open(sub_crs_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                # 确保 sub_crs 是列表
                if 'sub_crs' not in data:
                    data['sub_crs'] = []
                return data
        except Exception as e:
            print(f"{Color.RED}❌ 读取 sub-crs.yml 失败: {e}{Color.END}")
            sys.exit(1)
    return {
        'epic': epic_path.name,
        'title': '',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'sub_crs': []
    }


def save_sub_crs(epic_path: Path, data: dict):
    """保存 sub-crs.yml"""
    sub_crs_file = epic_path / 'sub-crs.yml'
    with open(sub_crs_file, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def next_sub_cr_id(epic_id: str, existing_sub_crs: list) -> str:
    """
    计算下一个子 CR 的 ID（数字后缀）

    示例：
    - CR-001 → CR-001-01
    - CR-001-01, CR-001-02 已存在 → CR-001-03
    """
    if not existing_sub_crs:
        return f"{epic_id}-01"

    # 提取所有已有数字后缀
    suffixes = []
    for sub_cr in existing_sub_crs:
        sub_id = sub_cr.get('id', '')
        if sub_id.startswith(f"{epic_id}-"):
            suffix = sub_id[len(f"{epic_id}-"):]
            try:
                suffixes.append(int(suffix))
            except ValueError:
                pass

    next_num = max(suffixes, default=0) + 1
    return f"{epic_id}-{next_num:02d}"


def create_sub_cr(epic_id: str, title: str, depends_on: list[str] = None):
    """
    创建子 CR 目录和初始文件

    Args:
        epic_id: 父 CR ID（如 CR-001）
        title: 子 CR 标题
        depends_on: 依赖的子 CR ID 列表
    """
    epic_path = DELIVERHQ_ROOT / 'change-requests' / epic_id

    if not epic_path.exists():
        print(f"{Color.RED}❌ Epic CR 不存在: {epic_path}{Color.END}")
        print(f"   请先创建 Epic CR：python3 init_cr.py {epic_id} '{epic_id} Epic'")
        sys.exit(1)

    # 加载现有 sub-crs.yml
    sub_crs_data = load_sub_crs(epic_path)
    if not sub_crs_data.get('title'):
        # 读取 Epic 标题
        state_file = epic_path / 'state.yml'
        if state_file.exists():
            with open(state_file, 'r', encoding='utf-8') as f:
                state = yaml.safe_load(f) or {}
                sub_crs_data['title'] = state.get('title', epic_id)

    # 生成子 CR ID
    sub_cr_id = next_sub_cr_id(epic_id, sub_crs_data['sub_crs'])
    sub_cr_path = DELIVERHQ_ROOT / 'change-requests' / sub_cr_id

    if sub_cr_path.exists():
        print(f"{Color.RED}❌ 子 CR 目录已存在: {sub_cr_path}{Color.END}")
        sys.exit(1)

    # 从 CR-TEMPLATE 创建子 CR
    template_path = DELIVERHQ_ROOT / 'change-requests' / 'CR-TEMPLATE'
    if template_path.exists():
        shutil.copytree(str(template_path), str(sub_cr_path))
        print(f"{Color.BLUE}  → 从 CR-TEMPLATE 复制目录结构{Color.END}")
    else:
        sub_cr_path.mkdir(parents=True)
        print(f"{Color.YELLOW}  ⚠ CR-TEMPLATE 不存在，创建空目录{Color.END}")

    # 创建 request.md
    request_content = f"""# {sub_cr_id}: {title}

**所属 Epic**: [{epic_id}](../{epic_id}/request.md)
**创建时间**: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
"""
    if depends_on:
        deps_str = ', '.join(f'[{d}](../{d}/request.md)' for d in depends_on)
        request_content += f"**依赖**: {deps_str}\n"

    request_content += f"""
## 子任务需求

> 此处描述 {sub_cr_id} 的具体需求。
> 参考 Epic [{epic_id}](../{epic_id}/acceptance-spec.md) 的高层目标。

{{待填写}}

## 完成标准

- [ ] {{验收条件 1}}
- [ ] {{验收条件 2}}

## 范围边界

**包含**：
- {{具体实现点}}

**不包含**（属于其他子 CR 或 Epic 后续）：
- {{排除项}}
"""
    (sub_cr_path / 'request.md').write_text(request_content, encoding='utf-8')

    # 创建 parent.yml（标记父 CR）
    parent_data = {
        'parent': epic_id,
        'sub_cr_id': sub_cr_id,
        'title': title,
        'depends_on': depends_on or [],
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    with open(sub_cr_path / 'parent.yml', 'w', encoding='utf-8') as f:
        yaml.dump(parent_data, f, allow_unicode=True, default_flow_style=False)

    # 初始化 state.yml
    state_data = {
        'cr_id': sub_cr_id,
        'title': title,
        'lane': 'standard',
        'current_state': 'draft',
        'current_phase': 'spec',
        'current_owner': 'spec-agent',
        'goal': '',
        'parent': epic_id,
        'depends_on': depends_on or [],
        'last_gate': None,
        'next_required_gate': 'spec',
        'gate_status': {},
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    with open(sub_cr_path / 'state.yml', 'w', encoding='utf-8') as f:
        yaml.dump(state_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    # 更新父 CR 的 sub-crs.yml
    sub_crs_data['sub_crs'].append({
        'id': sub_cr_id,
        'title': title,
        'status': 'pending',
        'depends_on': depends_on or [],
        'created_at': datetime.now(timezone.utc).isoformat()
    })
    save_sub_crs(epic_path, sub_crs_data)

    print(f"\n{Color.GREEN}✅ 子 CR 创建成功: {sub_cr_id}{Color.END}")
    print(f"   标题: {title}")
    print(f"   路径: {sub_cr_path}")
    if depends_on:
        print(f"   依赖: {', '.join(depends_on)}")
    print(f"\n{Color.BLUE}下一步:{Color.END}")
    print(f"   1. 填写 {sub_cr_id}/request.md（子任务需求）")
    print(f"   2. 运行: python3 skill_orchestrator.py verb spec change-requests/{sub_cr_id}")

    return sub_cr_id


def list_sub_crs(epic_id: str):
    """列出 Epic 的所有子 CR"""
    epic_path = DELIVERHQ_ROOT / 'change-requests' / epic_id

    if not epic_path.exists():
        print(f"{Color.RED}❌ Epic CR 不存在: {epic_id}{Color.END}")
        sys.exit(1)

    sub_crs_data = load_sub_crs(epic_path)
    sub_crs = sub_crs_data.get('sub_crs', [])

    if not sub_crs:
        print(f"{Color.YELLOW}⚠ {epic_id} 还没有子 CR{Color.END}")
        print(f"   创建第一个: python3 create_sub_cr.py {epic_id} --title '子任务名称'")
        return

    print(f"\n{Color.BLUE}=== {epic_id} 子 CR 列表 ==={Color.END}")
    print(f"Epic: {sub_crs_data.get('title', epic_id)}\n")

    for sub in sub_crs:
        status_icon = {
            'completed': '✅',
            'in_progress': '🔄',
            'pending': '⏳',
            'blocked': '❌'
        }.get(sub.get('status', 'pending'), '⏳')

        deps = sub.get('depends_on', [])
        deps_str = f" (依赖: {', '.join(deps)})" if deps else ""

        print(f"  {status_icon} {sub['id']}: {sub['title']}{deps_str}")


def check_epic_status(epic_id: str):
    """检查 Epic 完成状态"""
    epic_path = DELIVERHQ_ROOT / 'change-requests' / epic_id

    if not epic_path.exists():
        print(f"{Color.RED}❌ Epic CR 不存在: {epic_id}{Color.END}")
        sys.exit(1)

    sub_crs_data = load_sub_crs(epic_path)
    sub_crs = sub_crs_data.get('sub_crs', [])

    if not sub_crs:
        print(f"{Color.YELLOW}⚠ {epic_id} 还没有子 CR{Color.END}")
        return

    # 从各子 CR 的 state.yml 读取最新状态
    statuses = {}
    for sub in sub_crs:
        sub_id = sub['id']
        sub_path = DELIVERHQ_ROOT / 'change-requests' / sub_id
        state_file = sub_path / 'state.yml'

        if state_file.exists():
            with open(state_file, 'r', encoding='utf-8') as f:
                state = yaml.safe_load(f) or {}
                statuses[sub_id] = state.get('current_state', 'unknown')
        else:
            statuses[sub_id] = 'missing'

    total = len(sub_crs)
    completed = sum(1 for s in statuses.values() if s in ('archived', 'deployed'))
    in_progress = sum(1 for s in statuses.values() if s not in ('pending', 'draft', 'archived', 'deployed', 'missing'))

    print(f"\n{Color.BLUE}=== {epic_id} Epic 状态 ==={Color.END}")
    print(f"总计: {total}  已完成: {completed}  进行中: {in_progress}  待开始: {total - completed - in_progress}\n")

    for sub in sub_crs:
        sub_id = sub['id']
        state = statuses.get(sub_id, 'missing')
        icon = '✅' if state in ('archived', 'deployed') else ('🔄' if state not in ('pending', 'draft', 'missing') else '⏳')
        deps = sub.get('depends_on', [])
        deps_str = f" ← {', '.join(deps)}" if deps else ""
        print(f"  {icon} {sub_id}: {sub['title']} [{state}]{deps_str}")

    if completed == total:
        print(f"\n{Color.GREEN}🎉 所有子 CR 已完成！Epic {epic_id} 可以归档。{Color.END}")
    else:
        print(f"\n{Color.BLUE}ℹ️  进度: {completed}/{total}{Color.END}")


def main():
    parser = argparse.ArgumentParser(
        description="子 CR 创建工具（Epic → Story 拆解）"
    )
    parser.add_argument('epic_id', help='父 CR ID（如 CR-001）')

    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--title', '-t', help='子 CR 标题（创建子 CR）')
    action.add_argument('--list', '-l', action='store_true', help='列出所有子 CR')
    action.add_argument('--status', '-s', action='store_true', help='查看 Epic 完成状态')

    parser.add_argument('--depends-on', '-d', nargs='*', default=[], help='依赖的子 CR ID')

    args = parser.parse_args()

    if args.list:
        list_sub_crs(args.epic_id)
    elif args.status:
        check_epic_status(args.epic_id)
    elif args.title:
        create_sub_cr(args.epic_id, args.title, args.depends_on or [])


if __name__ == '__main__':
    main()
