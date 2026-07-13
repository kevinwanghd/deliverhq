#!/usr/bin/env python3
"""Shared Python script execution with deterministic cross-platform results."""

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys
from typing import Iterable, Mapping, Optional, Tuple


@dataclass(frozen=True)
class ExecutionResult:
    command: Tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


def run_script(
    script: Path,
    args: Optional[Iterable[str]] = None,
    *,
    cwd: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
    timeout: float = 300,
) -> ExecutionResult:
    """Execute a Python script without a shell and capture UTF-8 output."""
    command = (sys.executable, str(Path(script)), *(str(arg) for arg in (args or ())))
    process_env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        **dict(env or {}),
    }

    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd is not None else None,
            env=process_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
        )
        return ExecutionResult(
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        timeout_message = f"Execution timed out after {timeout} seconds"
        stderr = f"{stderr.rstrip()}\n{timeout_message}" if stderr else timeout_message
        return ExecutionResult(
            command=command,
            returncode=-1,
            stdout=stdout,
            stderr=stderr,
            timed_out=True,
        )
