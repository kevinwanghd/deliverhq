#!/usr/bin/env python3
"""
grill.py —— 需求澄清拷问（借 Matt Pocock grilling，填 DeliverHQ 输入端对齐空洞）

把"需求澄清"从口头散漫对话变成显式、可审计的工件化步骤。
在生成 acceptance-spec **之前**逐条拷问用户，把模糊想法逼成清晰需求。

产出：request-clarifications.md（Q&A 格式，Spec Agent 消费它生成更精准的 acceptance-spec）

设计纪律：
  - 一次一问（不能一口气抛 5 个问题）
  - 每问给推荐答案（agent 不能只提问不给建议）
  - 能查代码就不问人（减少人的负担）
  - 产出留痕（Q&A 存成工件，不是口头散了就没）
  - 条件启用（如果 request 已经很清晰，跳过 grilling）

用法：
  python grill.py <CR目录>           # 读 CR/request.md，产出 CR/request-clarifications.md
  python grill.py <request.md路径>   # 直接指定 request 文件
  python grill.py <CR目录> --dry-run # 不交互，只打印问题模板
  python grill.py <CR目录> --auto   # 自动生成问题（不等待用户输入，用于测试）

跨平台 / Python 3.10+。
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from common import Color


# ---------------------------------------------------------------------------
# 问题模板（来自 grill-the-user SKILL.md）
# ---------------------------------------------------------------------------

@dataclass
class Question:
    id: int
    template: str
    hint: str = ""
    recommended_answer: str = ""
    answered: bool = False
    user_answer: str = ""

    def format(self) -> str:
        q = f"[Round {self.id}]"
        if self.hint:
            q += f" [{self.hint}]"
        q += f"\nQ: {self.template}"
        if self.recommended_answer:
            q += f"\n  推荐: {self.recommended_answer}"
        return q


# ---------------------------------------------------------------------------
# 问题库（按场景分类）
# ---------------------------------------------------------------------------

class QuestionBank:
    """按阶段/场景分类的问题库。"""

    # 通用澄清问题（所有 request 都适用）
    GENERIC = [
        ("这个需求要解决的核心问题是什么？（不是'怎么做'，而是'为什么做'）",
         "problem",
         "参考 PRD.md 的「问题陈述」格式"),
        ("成功的可验证标准是什么？（怎样算'做完了'？）",
         "success",
         "写成 Given/When/Then 格式，如「Given 用户已登录，When 点击支付，Then 订单状态变为已支付」"),
        ("这个需求的边界在哪？（哪些明确不做？）",
         "boundary",
         "列举至少 3 个「不做」场景"),
        ("有没有依赖的现有代码/模块？（查代码库，不凭空设计）",
         "dependency",
         "引用现有模块名称，不要凭空新增接口"),
        ("失败时的降级方案是什么？",
         "degradation",
         "描述降级路径和回滚策略"),
    ]

    # PRD 锚点相关问题
    PRD_ANCHOR = [
        ("这个功能对应哪个 PRD 锚点？",
         "prd-link",
         "引用 PRD.md 中的锚点 ID，如 [PRD-XXX]"),
        ("PRD 中对这部分有没有具体指标要求？",
         "metric",
         "性能/可用性/转化率等可量化指标"),
    ]

    # 边界条件问题
    EDGE_CASES = [
        ("正常流程是什么？一步一步描述用户操作路径",
         "happy-path",
         "从用户视角写出完整操作步骤"),
        ("异常流程是什么？（网络失败/权限不足/数据不存在）",
         "error-path",
         "每种异常场景给出明确处理方式"),
        ("边界条件有哪些？（空数据/最大输入/并发）",
         "edge-cases",
         "列举至少 3 个边界场景"),
    ]

    # 验收条件问题
    ACCEPTANCE = [
        ("谁来验证这个功能？（人工/自动化/两者都有）",
         "validator",
         "对应 QualityGate 的 test_command"),
        ("如果自动化验收，需要什么测试命令或覆盖率门槛？",
         "test-cmd",
         "描述测试命令和最低覆盖率，如 pytest + 80%"),
        ("这个功能对现有功能有没有破坏性影响？",
         "regression",
         "描述需要回归测试的区域"),
    ]

    # 设计决策问题
    DESIGN = [
        ("有没有备选方案被否决了？为什么选当前方案？",
         "alternatives",
         "记录权衡过程，防止以后重蹈覆辙"),
        ("这个决策最难回滚的部分是什么？",
         "reversibility",
         "描述高耦合/高风险的技术决策"),
        ("谁来做出最终技术决策？（AI/人类/共同决策）",
         "decision-maker",
         "明确 human-in-the-loop 节点"),
    ]


# ---------------------------------------------------------------------------
# 歧义检测
# ---------------------------------------------------------------------------

# risk:todo-no-context reason:TODO literal in FUZZY_WORDS/PLACEHOLDER_PATTERNS is detection pattern data, not real TODO owner:kevin reviewed:2026-08-28

FUZZY_WORDS = [
    "可能", "大概", "优化", "改进", "完善", "调整",
    "也许", "似乎", "差不多", "基本上", "原则上",
    "待定", "TBD", "TODO", "后续", "再议",
    "待确认", "需讨论", "视情况", "灵活处理",
    "尽快", "适当", "合理", "正常", "常规",
]

PLACEHOLDER_PATTERNS = [
    # risk:todo-no-context reason:TODO regex in PLACEHOLDER_PATTERNS is detection pattern, not real TODO owner:kevin reviewed:2026-08-28
    r"\[待确认\]",
    r"\[NEEDS?\s+CLARIFICATION",
    r"\{\{.*?\}\}",
    r"<.*?>",
    r"TODO",
]


def detect_fuzzy_phrases(content: str) -> list[str]:
    """检测模糊词和占位符。"""
    found = []
    for word in FUZZY_WORDS:
        # 简单词匹配
        pattern = re.escape(word)
        matches = re.findall(rf".{{0,30}}{pattern}.{{0,30}}", content, re.IGNORECASE)
        for m in matches:
            found.append(f"[模糊词] {m.strip()}")
    for pattern in PLACEHOLDER_PATTERNS:
        matches = re.findall(rf".{{0,40}}{pattern}.{{0,40}}", content)
        for m in matches:
            found.append(f"[占位符] {m.strip()}")
    return found


def detect_missing_prd_anchors(content: str) -> list[str]:
    """检测没有 PRD 锚点的功能描述。"""
    # 找到所有标题（## 开头）和段落
    sections = re.findall(r"(^#{1,6}\s+.+)$", content, re.MULTILINE)
    # 粗略检查：是否有 [PRD-XXX] 引用
    has_anchor = bool(re.search(r"\[PRD-\w+\]", content))
    if not has_anchor:
        return ["request.md 中没有 PRD 锚点引用 [PRD-XXX]，可能需求来源不明"]
    return []


def detect_missing_ac(content: str) -> list[str]:
    """检测缺少验收条件的地方。"""
    # 检查是否有 Given/When/Then 格式
    has_gwt = bool(re.search(r"(Given|When|Then|AC-|验收条件|acceptance)", content, re.IGNORECASE))
    if not has_gwt:
        return ["request.md 中没有找到明确的验收条件或 AC- 标记"]
    return []


def detect_ambiguity(content: str) -> list[str]:
    """综合歧义检测。"""
    issues = []
    issues.extend(detect_fuzzy_phrases(content))
    issues.extend(detect_missing_prd_anchors(content))
    issues.extend(detect_missing_ac(content))
    return issues[:10]  # 最多 10 个


# ---------------------------------------------------------------------------
# Grill Engine
# ---------------------------------------------------------------------------

@dataclass
class GrillSession:
    cr_dir: Path
    request_file: Path
    questions: list[Question] = field(default_factory=list)
    answers: dict[int, str] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    dry_run: bool = False
    auto_mode: bool = False

    def load_request(self) -> str:
        return self.request_file.read_text(encoding="utf-8")

    def analyze(self, content: str):
        """分析 request 内容，生成问题列表。"""
        self.issues = detect_ambiguity(content)
        all_q = []

        # 1. 通用问题（每个 request 都问）
        for i, (q, hint, rec) in enumerate(QuestionBank.GENERIC, 1):
            all_q.append(Question(i, q, hint, rec))

        # 2. 如果没有 PRD 锚点，加问
        for issue in self.issues:
            if "PRD" in issue:
                for j, (q, hint, rec) in enumerate(QuestionBank.PRD_ANCHOR, len(all_q) + 1):
                    all_q.append(Question(j, q, hint, rec))
                break

        # 3. 如果有模糊词，加边界问题
        fuzzy_issues = [i for i in self.issues if "[模糊词]" in i]
        if fuzzy_issues:
            base = len(all_q) + 1
            for k, (q, hint, rec) in enumerate(QuestionBank.EDGE_CASES, base):
                all_q.append(Question(k, q, hint, rec))

        # 4. 缺少验收条件时，加 AC 问题
        ac_issues = [i for i in self.issues if "验收条件" in i or "AC-" in i]
        if ac_issues:
            base = len(all_q) + 1
            for m, (q, hint, rec) in enumerate(QuestionBank.ACCEPTANCE, base):
                all_q.append(Question(m, q, hint, rec))

        self.questions = all_q

    def ask_question(self, q: Question) -> str:
        """问一个问题，返回用户回答。"""
        print()
        print(Color.CYAN + q.format() + Color.END)

        if q.hint:
            print(f"{Color.DIM}提示: {q.hint}{Color.END}")

        if self.auto_mode:
            # 自动模式：打印推荐答案作为回答
            answer = q.recommended_answer or "[auto — 推荐答案]"
            print(f"{Color.YELLOW}auto > {answer}{Color.END}")
            return answer

        try:
            print(f"\n{Color.GREEN}你的回答 (直接回车使用推荐答案):{Color.END} ", end="")
            answer = input().strip()
            if not answer:
                answer = q.recommended_answer or "[未回答]"
            return answer
        except EOFError:
            return "[输入中断]"

    def run_interactive(self):
        """运行交互式烤问。"""
        content = self.load_request()

        print(f"\n{Color.BOLD}=== 需求澄清烤问 ==={Color.END}")
        print(f"CR: {self.cr_dir.name}")
        print(f"文件: {self.request_file}")

        # 分析歧义
        print(f"\n{Color.BLUE}正在分析 request.md...{Color.END}")
        self.analyze(content)

        if self.issues:
            print(f"\n{Color.YELLOW}检测到 {len(self.issues)} 个潜在问题:{Color.END}")
            for issue in self.issues[:5]:
                print(f"  - {issue}")

        # 如果 request 很清晰，提示跳过
        if len(self.questions) <= 3 and not self.issues:
            print(f"\n{Color.GREEN}request.md 看起来比较清晰。{Color.END}")
            print(f"按 Ctrl+C 跳过，或回车继续 {len(self.questions)} 个问题: ", end="")
            try:
                input()
            except EOFError:
                pass

        print(f"\n{Color.BOLD}开始烤问（共 {len(self.questions)} 个问题）{Color.END}")

        for q in self.questions:
            if self.dry_run:
                print(f"\n{Color.DIM}[dry-run] {q.format()}{Color.END}")
            else:
                answer = self.ask_question(q)
                q.user_answer = answer
                self.answers[q.id] = answer

        self.save_clarifications()

    def run_dry_run(self):
        """dry-run 模式：只打印问题，不等待输入。"""
        content = self.load_request()
        self.analyze(content)
        print(f"\n{Color.BOLD}=== Dry Run: 烤问问题预览 ==={Color.END}")
        print(f"CR: {self.cr_dir.name}\n")
        for q in self.questions:
            print(q.format())
            print()

    def save_clarifications(self) -> Path:
        """保存 Q&A 到 request-clarifications.md。"""
        output = self.cr_dir / "request-clarifications.md"

        lines = [
            "# Request Clarifications",
            "",
            f"> 由 `grill.py` 生成于 {self._timestamp()}",
            f"> 共 {len(self.answers)} 个问题被回答",
            "",
            "---\n",
        ]

        # 如果有歧义问题，先列出
        if self.issues:
            lines.append("## 歧义检测")
            lines.append("")
            lines.append("以下问题由自动检测发现（模糊词/占位符/缺少 PRD 锚点等）：")
            lines.append("")
            for issue in self.issues:
                lines.append(f"- {issue}")
            lines.append("")

        # Q&A 正文
        lines.append("## 澄清问答")
        lines.append("")

        for q in self.questions:
            lines.append(f"### Q{q.id}: {q.template}")
            lines.append("")
            if q.hint:
                lines.append(f"**提示**: {q.hint}")
                lines.append("")
            lines.append(f"**推荐答案**: {q.recommended_answer or '[无推荐]'}")
            lines.append("")
            lines.append(f"**用户回答**: {self.answers.get(q.id, '[未回答]')}")
            lines.append("")
            lines.append("---")
            lines.append("")

        output.write_text("\n".join(lines), encoding="utf-8")
        return output

    def _timestamp(self) -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def resolve_request_path(arg: str) -> tuple[Path, Path]:
    """解析参数，返回 (request.md 路径, CR 目录)。"""
    p = Path(arg).resolve()
    if p.is_dir():
        cr_dir = p
        request_file = cr_dir / "request.md"
    elif p.is_file() and p.name == "request.md":
        request_file = p
        cr_dir = p.parent
    else:
        raise ValueError(f"参数必须是 CR 目录或 request.md 文件: {arg}")

    if not request_file.exists():
        raise FileNotFoundError(f"request.md 不存在: {request_file}")

    return request_file, cr_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="DeliverHQ 需求澄清烤问工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python grill.py change-requests/CR-001
  python grill.py change-requests/CR-001/request.md
  python grill.py change-requests/CR-001 --dry-run   # 预览问题，不交互
  python grill.py change-requests/CR-001 --auto      # 自动回答（测试用）
        """
    )
    parser.add_argument(
        "target",
        help="CR 目录或 request.md 文件路径"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印问题模板，不交互"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="自动模式（使用推荐答案，适合测试)"
    )
    args = parser.parse_args()

    try:
        request_file, cr_dir = resolve_request_path(args.target)
        print(f"{Color.BLUE}读取: {request_file}{Color.END}")

        session = GrillSession(
            cr_dir=cr_dir,
            request_file=request_file,
            dry_run=args.dry_run,
            auto_mode=args.auto,
        )

        if args.dry_run:
            session.run_dry_run()
        else:
            session.run_interactive()

            print(f"\n{Color.GREEN}✅ 澄清问答已保存: {cr_dir / 'request-clarifications.md'}{Color.END}")
            print(f"{Color.CYAN}→ Spec Agent 生成 acceptance-spec 时会消费此文件{Color.END}")

            # 记录状态（如果 CR 有 state.yml）
            try:
                from cr_state import record_from_arg
                record_from_arg(str(cr_dir), "grill", True)
            except Exception:
                pass  # 状态记录失败不影响主流程

        return 0

    except (ValueError, FileNotFoundError) as e:
        print(f"{Color.RED}❌ {e}{Color.END}")
        return 1
    except KeyboardInterrupt:
        print(f"\n{Color.YELLOW}⚠ 用户中断{Color.END}")
        return 130
    except Exception as e:
        print(f"{Color.RED}❌ 意外错误: {e}{Color.END}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
