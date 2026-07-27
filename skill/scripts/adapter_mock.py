"""
Mock Adapter - 测试用固定行为实现。

行为:
    1. 从 run_id 提取 task_id
    2. 在 worktree 根目录写 agent-result.yml（固定内容）
    3. 创建 dummy 文件（mock-output.txt）
    4. 返回 success

用途:
    - 单元测试和集成测试
    - CI 环境（无需真实 agent）
    - 演示 adapter 接口
"""
import time
from pathlib import Path
from agent_adapter import BaseAdapter, AgentRunResult


class MockAdapter(BaseAdapter):
    """Mock adapter（测试用）。"""

    def name(self) -> str:
        return "mock"

    def run(
        self,
        session_pack: Path,
        worktree: Path,
        run_id: str,
        timeout: int = 1800,
    ) -> AgentRunResult:
        """
        模拟 agent 执行。

        固定行为:
            - 提取 task_id（从 run_id，如 "T1-r1" -> "T1"）
            - 写 agent-result.yml 到 worktree 根目录
            - 写 mock-output.txt
            - 返回 success
        """
        start = time.time()

        # 1. 提取 task_id（从 run_id）
        task_id = run_id.split("-r")[0] if "-r" in run_id else run_id

        # 2. 写 agent-result.yml 到 worktree 根目录
        result_yml = worktree / "agent-result.yml"
        result_yml.write_text(
            f"""task_id: {task_id}
status: done
changed_files:
  - mock-output.txt
test_command: echo "mock test passed"
notes: "Mock adapter 固定输出"
""",
            encoding="utf-8",
        )

        # 3. 写 dummy 文件
        output_file = worktree / "mock-output.txt"
        output_file.write_text(
            f"Mock output for {task_id}\n"
            f"Generated at: {time.strftime('%Y-%m-%dT%H:%M:%S')}\n",
            encoding="utf-8",
        )

        elapsed = time.time() - start

        return AgentRunResult(
            run_id=run_id,
            exit_kind="success",
            exit_code=0,
            elapsed_seconds=elapsed,
            stdout_tail="DONE (mock)",
            stderr_tail="",
            adapter_name="mock",
        )


class ConfigurableMockAdapter(MockAdapter):
    """
    可配置的 mock adapter（用于测试失败/超时场景）。

    用法:
        adapter = ConfigurableMockAdapter(
            exit_kind="timeout",  # 模拟超时
            exit_code=-1,
        )
    """

    def __init__(
        self,
        exit_kind: str = "success",
        exit_code: int = 0,
        elapsed_seconds: float = 0.1,
        write_result_yml: bool = True,
    ):
        self.mock_exit_kind = exit_kind
        self.mock_exit_code = exit_code
        self.mock_elapsed_seconds = elapsed_seconds
        self.mock_write_result_yml = write_result_yml

    def run(
        self,
        session_pack: Path,
        worktree: Path,
        run_id: str,
        timeout: int = 1800,
    ) -> AgentRunResult:
        """模拟配置的行为。"""
        task_id = run_id.split("-r")[0] if "-r" in run_id else run_id

        # 根据配置决定是否写 agent-result.yml
        if self.mock_write_result_yml:
            result_yml = worktree / "agent-result.yml"
            result_yml.write_text(f"task_id: {task_id}\nstatus: done\n")

        return AgentRunResult(
            run_id=run_id,
            exit_kind=self.mock_exit_kind,
            exit_code=self.mock_exit_code,
            elapsed_seconds=self.mock_elapsed_seconds,
            stdout_tail="",
            stderr_tail="",
            adapter_name="mock",
        )
