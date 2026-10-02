#!/usr/bin/env python3
"""Compatibility CLI for the modular DeliverHQ orchestrator."""

from orchestrator_core import *
from orchestrator_core import _has_gate_cache
from orchestrator_core import main
from runtime_support import configure_console


if __name__ == "__main__":
    configure_console()
    main()
