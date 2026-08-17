#!/usr/bin/env python3
"""
五步定位法 — Five Step Locator

来源：企业微信团队"AI代码生成率94%"经验。

核心原则：大模型不是搜索引擎。把"在大型项目里找改动点"拆成5个收敛步骤：
  1. 意图消歧 → 2. 模块定位 → 3. 关键词搜索 → 4. 调用链追踪 → 5. 验证确认

每一步都在"缩小范围"，让模型从来不会被整个代码库淹死。

用法：
  python five_step_locator.py "邮件列表顶部出现红色小条" --project-root . --output result.json
"""

import argparse
import json
import sys
from pathlib import Path

# =============================================================================
# 配置
# =============================================================================

STEPS = [
    {
        "id": 1,
        "name": "意图消歧",
        "description": "项目概述 ~2K + 用户原话",
        "output": "「4种技术解读」",
        "input_hint": "给 LLM 的输入量：项目概述 ~2K + 用户原话"
    },
    {
        "id": 2,
        "name": "模块定位",
        "description": "目录树 + 解读结果",
        "output": "2-3 个候选文件路径",
        "input_hint": "给 LLM 的输入量：目录树 + 解读结果"
    },
    {
        "id": 3,
        "name": "关键词搜索",
        "description": "rg 直接跑",
        "output": "函数声明 + 位置",
        "input_hint": "给 LLM 的输入量：rg 搜索结果"
    },
    {
        "id": 4,
        "name": "调用链追踪",
        "description": "单文件 ~10K",
        "output": "完整调用链",
        "input_hint": "给 LLM 的输入量：单文件 ~10K"
    },
    {
        "id": 5,
        "name": "验证确认",
        "description": "函数实现 ~5K",
        "output": "最终改动点 + 理由",
        "input_hint": "给 LLM 的输入量：函数实现 ~5K"
    }
]

OUTPUT_TEMPLATE = """
=== 五步定位结果 ===

步骤 1：意图消歧
  输入量：项目概述 ~2K + 用户原话
  产出：{interpretations}

步骤 2：模块定位
  输入量：目录树 + 解读结果
  产出：{modules}

步骤 3：关键词搜索
  输入量：rg 搜索结果
  产出：{search_results}

步骤 4：调用链追踪
  输入量：单文件 ~10K
  产出：{call_chain}

步骤 5：验证确认
  输入量：函数实现 ~5K
  产出：{final_location}

最终定位：
  文件：{file}
  行号：{line}
  理由：{reason}

"""

# =============================================================================
# 工具函数
# =============================================================================

def find_project_overview(project_root: Path) -> str | None:
    """查找 L1 项目总览文件"""
    kb_paths = [
        project_root / "DeliverHQ" / "docs" / "knowledge-base" / "L1-项目总览" / "overview.md",
        project_root / "DeliverHQ" / "docs" / "knowledge-base" / "L1-项目总览" / "README.md",
        project_root / "docs" / "knowledge-base" / "L1-项目总览" / "overview.md",
    ]
    for p in kb_paths:
        if p.exists():
            return p.read_text(encoding="utf-8")
    return None


def find_module_wiki(project_root: Path) -> list[dict]:
    """查找所有 L2 模块 wiki 文件"""
    kb_paths = [
        project_root / "DeliverHQ" / "docs" / "knowledge-base" / "L2-模块级",
        project_root / "docs" / "knowledge-base" / "L2-模块级",
    ]
    modules = []
    for kb_path in kb_paths:
        if not kb_path.exists():
            continue
        for md_file in kb_path.glob("*.md"):
            if md_file.name == "README.md":
                continue
            content = md_file.read_text(encoding="utf-8")
            # 提取 module_id
            for line in content.split("\n"):
                if line.startswith("module_id:"):
                    module_id = line.split(":", 1)[1].strip()
                    modules.append({
                        "file": str(md_file),
                        "module_id": module_id
                    })
                    break
    return modules


def find_glossary(project_root: Path) -> str | None:
    """查找 L3 语义桥 glossary"""
    kb_paths = [
        project_root / "DeliverHQ" / "docs" / "knowledge-base" / "L3-语义桥" / "glossary.md",
        project_root / "docs" / "knowledge-base" / "L3-语义桥" / "glossary.md",
    ]
    for p in kb_paths:
        if p.exists():
            return p.read_text(encoding="utf-8")
    return None


def find_search_matrix(project_root: Path) -> str | None:
    """查找 L3 语义桥 search-matrix"""
    kb_paths = [
        project_root / "DeliverHQ" / "docs" / "knowledge-base" / "L3-语义桥" / "search-matrix.md",
        project_root / "docs" / "knowledge-base" / "L3-语义桥" / "search-matrix.md",
    ]
    for p in kb_paths:
        if p.exists():
            return p.read_text(encoding="utf-8")
    return None


# =============================================================================
# 核心逻辑
# =============================================================================

def run_five_step_locator(
    user_request: str,
    project_root: Path,
    output_json: bool = False
) -> dict:
    """
    执行五步定位法。

    返回：
        {
            "success": bool,
            "steps": [...],
            "final_location": {...},
            "knowledge_base_context": {...}
        }
    """

    result = {
        "success": False,
        "user_request": user_request,
        "steps": [],
        "final_location": None,
        "knowledge_base_context": {}
    }

    # 加载知识库上下文
    kb_context = {}
    overview = find_project_overview(project_root)
    if overview:
        kb_context["L1_overview"] = overview[:500]  # 截取前 500 字

    modules = find_module_wiki(project_root)
    kb_context["L2_modules"] = [m["module_id"] for m in modules]

    glossary = find_glossary(project_root)
    if glossary:
        kb_context["L3_glossary"] = glossary[:1000]  # 截取前 1000 字

    search_matrix = find_search_matrix(project_root)
    if search_matrix:
        kb_context["L3_search_matrix"] = search_matrix[:1000]  # 截取前 1000 字

    result["knowledge_base_context"] = kb_context

    # 输出引导信息
    print("=" * 60)
    print("五步定位法 — Five Step Locator")
    print("=" * 60)
    print(f"\n用户请求：{user_request}\n")

    print("=" * 60)
    print("步骤 1/5：意图消歧")
    print("=" * 60)
    print(f"知识库上下文（L1 overview）：")
    if overview:
        print(f"  ✓ 找到 L1 项目总览（{len(overview)} 字符）")
        print(f"  模块列表：{', '.join(kb_context['L2_modules']) or '未找到'}")
    else:
        print("  ✗ 未找到 L1 项目总览")
        print("  建议：创建 DeliverHQ/docs/knowledge-base/L1-项目总览/overview.md")
    print()

    print("=" * 60)
    print("步骤 2/5：模块定位")
    print("=" * 60)
    if modules:
        print(f"找到 {len(modules)} 个模块 wiki：")
        for m in modules[:10]:  # 最多显示 10 个
            print(f"  - {m['module_id']}")
        if len(modules) > 10:
            print(f"  ... 还有 {len(modules) - 10} 个模块")
    else:
        print("  ✗ 未找到 L2 模块 wiki")
        print("  建议：创建 DeliverHQ/docs/knowledge-base/L2-模块级/<module>.md")
    print()

    print("=" * 60)
    print("步骤 3/5：关键词搜索")
    print("=" * 60)
    print("请使用 grep/rg 工具进行搜索：")
    print("  1. 先从 L2 模块 wiki 确认可能的模块")
    print("  2. 使用 5 维搜索矩阵展开搜索：")
    print("     - 平台 API 事件方法")
    print("     - 功能语义英文同义词")
    print("     - 项目命名习惯")
    print("     - 协议/代理模式")
    print("     - 通知/回调模式")
    print()

    print("=" * 60)
    print("步骤 4/5：调用链追踪")
    print("=" * 60)
    print("找到目标文件后，进行调用链追踪：")
    print("  1. 读取文件内容（~10K token）")
    print("  2. 追踪上下游调用关系")
    print("  3. 确认最终改动点")
    print()

    print("=" * 60)
    print("步骤 5/5：验证确认")
    print("=" * 60)
    print("最终确认：")
    print("  - 文件路径：")
    print("  - 行号范围：")
    print("  - 改动理由：")
    print()

    # 输出 LLM 引导
    print("=" * 60)
    print("LLM 引导")
    print("=" * 60)
    print("""
基于以上知识库上下文，请按以下步骤执行五步定位：

1. 【意图消歧】分析用户请求 "{user_request}"，
   给出 4 种可能的技术解读。

2. 【模块定位】结合 L2 模块 wiki，
   选出 2-3 个最可能的候选模块。

3. 【关键词搜索】使用 5 维搜索矩阵展开搜索：
   - 维度①：平台 API 事件方法
   - 维度②：功能语义英文同义词
   - 维度③：项目命名习惯
   - 维度④：协议/代理模式
   - 维度⑤：通知/回调模式

4. 【调用链追踪】追踪完整调用链。

5. 【验证确认】给出最终文件 + 行号 + 理由。

⚠️ 禁止：
- 未读 L2 模块 wiki 就直接 grep 全项目
- 未确认调用链就声称定位成功
- 凭语义联想扩大改动范围
""".format(user_request=user_request))

    result["success"] = True
    return result


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="五步定位法 — 把大型项目代码定位拆成5个收敛步骤",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python five_step_locator.py "邮件列表顶部出现红色小条" --project-root .
  python five_step_locator.py "用户登录后跳转到首页" --project-root D:/Code/myapp --output result.json

前置条件：
  - 项目根目录存在 DeliverHQ/docs/knowledge-base/L1-项目总览/overview.md
  - 项目根目录存在 DeliverHQ/docs/knowledge-base/L2-模块级/*.md
  - （可选）L3 语义桥：glossary.md、search-matrix.md
        """
    )
    parser.add_argument(
        "request",
        help="用户的需求描述（产品语言）"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="项目根目录（默认：当前目录）"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="输出 JSON 结果到文件"
    )

    args = parser.parse_args()

    result = run_five_step_locator(
        user_request=args.request,
        project_root=args.project_root,
        output_json=args.output is not None
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"\n结果已保存到：{args.output}")

    # 返回退出码
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
