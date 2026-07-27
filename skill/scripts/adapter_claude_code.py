"""
Claude Code Adapter - 真实 Claude Code CLI 调用实现。

说明:
    这是参考实现，不强制要求 Phase 1 提交。
    用户可根据环境修改命令或改为其他 agent。

命令格式:
    claude -p <session-pack.md>

环境要求:
    - claude CLI 已安装（~/.local/bin/claude）
    - worktree 路径正确（由 state.yml 提供）
"""
import os
import subprocess
import sys
import time
from pathlib import Path
from agent_adapter import BaseAdapter, AgentRunResult, tail_lines


class ClaudeCodeAdapter(BaseAdapter):
    """Claude Code CLI adapter。"""

    def __init__(self, command: list[str] | None = None):
        """
        Args:
            command: 覆盖默认命令（["claude", "-p"]）
        """
        self.command = command or ["claude", "-p"]

    def name(self) -> str:
        return "claude-code"

    def run(
        self,
        session_pack: Path,
        worktree: Path,
        run_id: str,
        timeout: int = 1800,
    ) -> AgentRunResult:
        """
        调用 claude CLI 执行 session pack。

        命令:
            claude -p <session-pack-path>

        超时处理:
            - subprocess.TimeoutExpired -> exit_kind: timeout

        错误处理:
            - returncode != 0 -> exit_kind: error

        Notes:
            adapter 不检查 agent-result.yml 是否存在，
            那是 Evidence Verifier 的职责。
        """
        start = time.time()

        # 环境变量（确保 UTF-8）
        env = os.environ.copy()
        env.update({
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        })

        try:
            session_pack = Path(session_pack).resolve()
            worktree = Path(worktree).resolve()
            if not session_pack.is_file():
                raise FileNotFoundError(f"session pack not found: {session_pack}")
            if not worktree.is_dir():
                raise FileNotFoundError(f"worktree not found: {worktree}")
            # 必须在修改 cwd 前解析为绝对路径，否则相对 pack 会在 worktree 中失效。
            cmd = self.command + [str(session_pack)]
            result = subprocess.run(
                cmd,
                cwd=str(worktree),
                timeout=timeout,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                shell=False,  # 安全：不使用 shell
            )

            elapsed = time.time() - start

            # 判断 exit_kind（只报告进程级事实）
            exit_kind = "success" if result.returncode == 0 else "error"

            return AgentRunResult(
                run_id=run_id,
                exit_kind=exit_kind,
                exit_code=result.returncode,
                elapsed_seconds=elapsed,
                stdout_tail=tail_lines(result.stdout, 50),
                stderr_tail=tail_lines(result.stderr, 20),
                adapter_name="claude-code",
                summary_path=str(worktree / "agent-result.yml") if (worktree / "agent-result.yml").exists() else "",
                transcript_ref=f"stdout://{run_id}",
                budget_reason="",
            )

        except subprocess.TimeoutExpired as e:
            elapsed = time.time() - start

            # 收集已有输出
            stdout = e.stdout.decode("utf-8", errors="replace") if e.stdout else ""
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""

            return AgentRunResult(
                run_id=run_id,
                exit_kind="timeout",
                exit_code=-1,
                elapsed_seconds=elapsed,
                stdout_tail=tail_lines(stdout, 50),
                stderr_tail=tail_lines(stderr, 20),
                adapter_name="claude-code",
                transcript_ref=f"timeout://{run_id}",
                budget_reason="timeout",
            )

        except OSError as e:
            elapsed = time.time() - start
            return AgentRunResult(
                run_id=run_id,
                exit_kind="error",
                exit_code=127,
                elapsed_seconds=elapsed,
                stdout_tail="",
                stderr_tail=str(e),
                adapter_name="claude-code",
                transcript_ref=f"error://{run_id}",
                budget_reason="",
            )
