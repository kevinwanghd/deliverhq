#!/usr/bin/env python3
"""Compatibility wrapper for deliverhq.runtime."""

from pathlib import Path
import sys


SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from deliverhq.runtime import ExecutionResult, run_script  # noqa: E402,F401

