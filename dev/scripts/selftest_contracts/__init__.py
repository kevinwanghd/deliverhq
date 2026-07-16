"""Contract catalog for the DeliverHQ selftest suite."""

from .core import CONTRACTS as CORE_CONTRACTS
from .workflow import CONTRACTS as WORKFLOW_CONTRACTS
from .governance import CONTRACTS as GOVERNANCE_CONTRACTS


ALL_CONTRACTS = CORE_CONTRACTS + WORKFLOW_CONTRACTS + GOVERNANCE_CONTRACTS
