"""
Agent Adapter 抽象接口。

DeliverHQ 是 agent-agnostic 框架，ARC 不绑定特定 agent。
所有 adapter 必须实现 BaseAdapter 接口。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass
class AgentRunResult:
    """Agent 执行结果（标准化返回格式）。"""

    run_id: str                    # 如 "T1-r1"
    exit_kind: Literal["success", "timeout", "error"]
    exit_code: int                 # agent 进程退出码（timeout 时为 -1）
    elapsed_seconds: float         # 实际执行时长
    stdout_tail: str               # stdout 最后 50 行
    stderr_tail: str               # stderr 最后 20 行
    adapter_name: str              # "mock" / "claude-code" / ...
    summary_path: str = ""
    changed_files: list[str] | None = None
    transcript_ref: str = ""
    budget_reason: str = ""

    def __post_init__(self):
        if self.changed_files is None:
            self.changed_files = []


class BaseAdapter(ABC):
    """Agent Adapter 基类（所有 adapter 必须继承）。"""

    @abstractmethod
    def run(
        self,
        session_pack: Path,
        worktree: Path,
        run_id: str,
        timeout: int = 1800,
    ) -> AgentRunResult:
        """
        执行 agent，阻塞直到完成或超时。

        Args:
            session_pack: session pack 文件路径（.md 格式）
            worktree: 工作目录（由调度器从 state.yml 的 worktree_path 传入）
            run_id: 运行 ID（如 "T1-r1"），adapter 直接使用，不需解析
            timeout: 超时秒数（默认 1800 = 30 分钟）

        Returns:
            AgentRunResult（标准化结果）

        Notes:
            - adapter 不关心 agent-result.yml 内容，只负责调用 agent CLI
            - agent-result.yml 由 agent 自行写入 worktree 根目录
            - Evidence Verifier 负责验证产物是否存在及内容是否合规
            - exit_kind 只报告进程级事实（success/timeout/error），
              不判断 agent-result.yml 是否存在（那是验证阶段的事）
        """
        pass

    @abstractmethod
    def name(self) -> str:
        """返回 adapter 名称（如 "mock" / "claude-code"）。"""
        pass


def tail_lines(text: str, n: int) -> str:
    """提取文本的最后 n 行。"""
    lines = text.splitlines()
    return "\n".join(lines[-n:]) if lines else ""
