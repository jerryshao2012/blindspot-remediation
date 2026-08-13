"""
Public API for the shared-contracts package.

Only stable, cross-service data contracts should be exported here. This package
must not contain Azure clients, Git operations, LLM calls, release decisions,
benchmark execution logic, or persistence implementations.

The three principal services communicate through these models:

    TaskRunRequest
        -> ChangeExecutionService
        -> ExecutionResult

    GateRequest
        -> ReleaseGateService
        -> GateResult

    CampaignRequest
        -> PipelineEvaluationService
        -> CampaignResult

The models are frozen. Treat an emitted contract as an immutable historical
record. To create a changed record, call ``model_copy(update={...})`` and store
the result as a new artifact rather than mutating the original object.
"""

from .enums import (
    ArtifactKind,
    BenchmarkOrigin,
    CheckStatus,
    ControlSeverity,
    EvidenceStrategy,
    ExecutionStatus,
    GateDecision,
    ReadinessDecision,
    ReviewDisposition,
)
from .models import (
    ArtifactReference,
    BenchmarkCase,
    CampaignRequest,
    CampaignResult,
    CheckResult,
    ControlResult,
    EvidenceBudget,
    ExecutionBudget,
    ExecutionResult,
    HumanReviewResult,
    ModelConfiguration,
    PipelineConfiguration,
    StatisticalEstimate,
    TaskRunRequest,
    TokenUsage,
    ToolUsageRecord,
    GateRequest,
    GateResult,
)

__all__ = [
    "ArtifactKind",
    "ArtifactReference",
    "BenchmarkCase",
    "BenchmarkOrigin",
    "CampaignRequest",
    "CampaignResult",
    "CheckResult",
    "CheckStatus",
    "ControlResult",
    "ControlSeverity",
    "EvidenceBudget",
    "EvidenceStrategy",
    "ExecutionBudget",
    "ExecutionResult",
    "ExecutionStatus",
    "GateDecision",
    "GateRequest",
    "GateResult",
    "HumanReviewResult",
    "ModelConfiguration",
    "PipelineConfiguration",
    "ReadinessDecision",
    "ReviewDisposition",
    "StatisticalEstimate",
    "TaskRunRequest",
    "TokenUsage",
    "ToolUsageRecord",
]

__version__ = "0.1.0"
