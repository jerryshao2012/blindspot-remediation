"""
Component 11 — Task Specification & Capability Registry.

This package defines and resolves versioned engineering task contracts.

The registry is deliberately deterministic.

No LLM is used to decide which specification applies or whether a
specification is valid.
"""

from .service import TaskSpecificationRegistry

__all__ = ["TaskSpecificationRegistry"]

__version__ = "0.1.0"
