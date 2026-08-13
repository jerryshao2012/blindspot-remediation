"""
Component 10 — Execution Environment & Sandbox Service.

This package provides a common execution boundary for:

    ChangeExecutionService
    ReleaseGateService
    EvaluationCampaignRunner

The service deliberately separates execution policy from execution mechanism.

A caller specifies WHAT should be executed.

The environment service determines whether the request is permitted and
delegates the actual isolated execution to an approved runner.

The package itself contains no LLM client.
"""

from .service import ExecutionEnvironmentService

__all__ = ["ExecutionEnvironmentService"]

__version__ = "0.1.0"
