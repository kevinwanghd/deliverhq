#!/usr/bin/env python3
"""
grill.py —— 需求澄清拷问（借 Matt Pocock grilling，填 DeliverHQ 输入端对齐空洞）

把"需求澄清"从口头散漫对话变成显式、可审计的工件化步骤。在生成 acceptance-spec
**之前**逐条拷问用户，把模糊想法逼成清晰需求。

为什么需要这个（DeliverHQ 的架构空洞）：
  DeliverHQ 的门禁保证"给定 spec，交付质量可控"，但无法保证"给定模糊想法，spec 质量可控"。
  最常见的失败不是"没写 spec"，而是"需求本身没想清楚"——然后垃圾进、(合规的)垃圾出。
  SpecGate 只检查 spec 格式完备性（有没有占位符），不检查 spec 是否建立在模糊需求上。

  Pocock grilling 的洞察：最常见的失败是人和 agent 的对齐缺口，修复手段是开发**之前**
  的结构化拷问（一次一问+推荐答案+能查代码就查不问人）。

产出工件：request-clarifications.md（Q&A 格式，Spec Agent 消费它生成更精准的 acceptance-spec）

用法：
  python grill.py <CR目录>          # 读 CR/request.md，产出 CR/request-clarifications.md
  python grill.py <request.md路径>  # 直接指定 request 文件

设计纪律：
  - 一次一问（不能一口气抛 5 个问题，bewildering）
  - 每问给推荐答案（agent 不能只提问不给建议）
  - 能查代码就查，不问人（减少人的负担）
  - 产出留痕（Q&A 存成工件，不是口头散了就没）
  - 条件启用（如果 request 已经很清晰 / 用户选择跳过，orchestrator 会 skip 这步）

跨平台 / Python 3.10+。
"""

import sys
from pathlib import Path


class Color:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    END = "\033[0m"


def resolve_request_path(arg: str) -> tuple[Path, Path]:
    """解析参数，返回 (request.md 路径, CR 目录)。

    参数可以是 CR 目录或 request.md 文件路径。
    """
    p = Path(arg).resolve()
    if p.is_dir():
        # CR 目录
        cr_dir = p
        request_file = cr_dir / "request.md"
    elif p.is_file() and p.name == "request.md":
        # 直接指定 request.md
        request_file = p
        cr_dir = p.parent
    else:
        raise ValueError(f"参数必须是 CR 目录或 request.md 文件: {arg}")

    if not request_file.exists():
        raise FileNotFoundError(f"request.md 不存在: {request_file}")

    return request_file, cr_dir


def load_request(request_file: Path) -> str:
    """读取 request.md 内容。"""
    return request_file.read_text(encoding="utf-8")


def save_clarifications(cr_dir: Path, qa_pairs: list[tuple[str, str]]) -> Path:
    """保存 Q&A 到 request-clarifications.md。

    Args:
        cr_dir: CR 目录
        qa_pairs: [(question, answer), ...]

    Returns:
        写入的文件路径
    """
    output = cr_dir / "request-clarifications.md"

    lines = [
        "# Request Clarifications",
        "",
        "此文件由 `grill.py` 生成，记录需求澄清拷问的 Q&A。",
        "Spec Agent 在生成 acceptance-spec 时会消费此文件，产出更精准的规格。",
        "",
        "---",
        "",
    ]

    for i, (q, a) in enumerate(qa_pairs, 1):
        lines.append(f"## Q{i}: {q}")
        lines.append("")
        lines.append(f"**A**: {a}")
        lines.append("")

    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def grill_request(request_content: str, cr_dir: Path) -> list[tuple[str, str]]:
    """对 request 进行逐条拷问，返回 Q&A pairs。

    这里是简化版实现：真实版应该是交互式的（一次一问、等用户回答），
    或者调用一个 Agent 来完成拷问循环。

    当前实现：生成一组典型澄清问题的占位符（供后续完善成交互式 / Agent 驱动）。
    """
    print(f"{Color.BLUE}=== 需求澄清拷问 ==={Color.END}\n")
    print("正在分析 request.md 并生成澄清问题...\n")

    # TODO: 这里应该是一个交互式循环或 Agent 调用。
    # 当前占位符实现：根据 request 生成典型问题模板。
    # 真实版可以用 Agent 读 request + 查代码，生成针对性问题。

    qa_pairs = [
        (
            "这个需求要解决的核心问题是什么？（不是'怎么做'，而是'为什么做'）",
            "[待用户回答 —— 此处应由交互式 grill 或 Agent 填充]"
        ),
        (
            "成功的可验证标准是什么？（怎样算'做完了'？）",
            "[待用户回答]"
        ),
        (
            "这个需求的边界在哪？（哪些明确不做？）",
            "[待用户回答]"
        ),
        (
            "有没有依赖的现有代码/模块？（查代码库）",
            "[待 Agent 查代码后回答，或询问用户]"
        ),
        (
            "失败时的降级方案是什么？",
            "[待用户回答]"
        ),
    ]

    print(f"{Color.YELLOW}注意: 当前是占位符实现。{Color.END}")
    print(f"{Color.YELLOW}真实版应该是交互式拷问（一次一问+等回答）或 Agent 驱动。{Color.END}\n")

    for i, (q, _) in enumerate(qa_pairs, 1):
        print(f"{Color.CYAN}Q{i}: {q}{Color.END}")

    return qa_pairs


def main():
    if len(sys.argv) < 2:
        print(f"用法: python {Path(__file__).name} <CR目录 或 request.md>")
        print("\n示例:")
        print(f"  python {Path(__file__).name} change-requests/CR-001")
        print(f"  python {Path(__file__).name} change-requests/CR-001/request.md")
        sys.exit(1)

    try:
        request_file, cr_dir = resolve_request_path(sys.argv[1])
        print(f"{Color.BLUE}读取: {request_file}{Color.END}")

        request_content = load_request(request_file)
        qa_pairs = grill_request(request_content, cr_dir)

        output_file = save_clarifications(cr_dir, qa_pairs)
        print(f"\n{Color.GREEN}✅ 澄清问题已保存: {output_file}{Color.END}")
        print(f"{Color.CYAN}→ Spec Agent 生成 acceptance-spec 时会消费此文件{Color.END}")

        # 记录状态（如果 CR 有 state.yml）
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from cr_state import record_from_arg
            # grill 本身不是 gate，不记录 pass/fail；只标记"已拷问"
            record_from_arg(str(cr_dir), "grill", True)
        except Exception:
            pass  # 状态记录失败不影响主流程

        sys.exit(0)

    except (ValueError, FileNotFoundError) as e:
        print(f"{Color.RED}❌ {e}{Color.END}")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n{Color.YELLOW}⚠ 用户中断{Color.END}")
        sys.exit(130)
    except Exception as e:
        print(f"{Color.RED}❌ 意外错误: {e}{Color.END}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
