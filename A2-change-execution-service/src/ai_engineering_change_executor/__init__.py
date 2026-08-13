"""
Deterministic change-execution service.

The public façade is ``ChangeExecutionService``. This initial implementation
accepts a manually authored unified Git patch. It intentionally does not call
an LLM.

Architectural boundary
----------------------
The executor produces a candidate implementation. It does not determine whether
the candidate is safe to release.

Executor-local checks are useful feedback, but they remain executor claims.
ReleaseGateService must independently clone the candidate commit and rerun all
authoritative release checks in a clean environment.
"""

from .models import (
    ExecutorSettings,
    LocalCheckSpec,
    ManualPatchExecutionRequest,
)
from .service import ChangeExecutionService

__all__ = [
    "ChangeExecutionService",
    "ExecutorSettings",
    "LocalCheckSpec",
    "ManualPatchExecutionRequest",
]

__version__ = "0.1.0"
