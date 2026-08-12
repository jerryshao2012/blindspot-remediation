"""
Canonical public API for Component 1.

IMPORT RULE
-----------

Other components should import shared objects FROM THIS PACKAGE.

Preferred:

    from ai_engineering_contracts import GateDecision

Avoid:

    from ai_engineering_contracts.gate import GateDecision

The first approach makes later internal file reorganization easier.

Do not export component-private implementation classes here.
"""

from .base import (
    AwareDatetime,
    CONTRACT_SCHEMA_VERSION,
    ContractModel,
)
from .candidate import CandidateArtifact
from .correlation import CorrelationContext
from .enums import (
    ExecutionStatus,
    FinalDisposition,
    GateDisposition,
    RiskTier,
    RunState,
    SandboxRole,
    SpecificationStatus,
    TaskSourceKind,
)
from .evidence import (
    EvidenceReference,
    EvidenceRequirement,
    UncertaintyStatement,
)
from .execution import (
    ExecutionCommand,
    ExecutionOutput,
    ExecutionReceipt,
    ExecutionRequest,
)
from .gate import (
    GateDecision,
    HumanReviewSignal,
)
from .hashing import (
    canonical_json_bytes,
    content_sha256,
    sha256_bytes,
)
from .orchestration import (
    OrchestrationRun,
    RunOutcome,
    StateTransition,
    TERMINAL_RUN_STATES,
)
from .references import (
    ArtifactReference,
    DeploymentReference,
    ExternalResourceReference,
    PullRequestReference,
    ReleaseReference,
    RepositoryReference,
    TaskSpecificationReference,
)
from .task import (
    RequestedCapability,
    TaskRequest,
)
from .task_specification import (
    BenchmarkContract,
    ChangeContract,
    EvidenceContract,
    ExecutionContract,
    GateContract,
    GovernanceContract,
    PathRule,
    RegisteredTaskSpecification,
    RepositoryScope,
    ResolvedTaskContract,
    SkillContract,
    TaskSpecification,
)
from .usage import (
    AIUsage,
    ResourceBudget,
    RunUsageLedger,
)

__all__ = [
    "AIUsage",
    "ArtifactReference",
    "AwareDatetime",
    "BenchmarkContract",
    "CONTRACT_SCHEMA_VERSION",
    "CandidateArtifact",
    "ChangeContract",
    "ContractModel",
    "CorrelationContext",
    "DeploymentReference",
    "EvidenceContract",
    "EvidenceReference",
    "EvidenceRequirement",
    "ExecutionCommand",
    "ExecutionContract",
    "ExecutionOutput",
    "ExecutionReceipt",
    "ExecutionRequest",
    "ExecutionStatus",
    "ExternalResourceReference",
    "FinalDisposition",
    "GateContract",
    "GateDecision",
    "GateDisposition",
    "GovernanceContract",
    "HumanReviewSignal",
    "OrchestrationRun",
    "PathRule",
    "PullRequestReference",
    "RegisteredTaskSpecification",
    "ReleaseReference",
    "RepositoryReference",
    "RequestedCapability",
    "ResolvedTaskContract",
    "ResourceBudget",
    "RiskTier",
    "RunOutcome",
    "RunState",
    "RunUsageLedger",
    "SandboxRole",
    "SkillContract",
    "SpecificationStatus",
    "StateTransition",
    "TERMINAL_RUN_STATES",
    "TaskRequest",
    "TaskSourceKind",
    "TaskSpecification",
    "TaskSpecificationReference",
    "UncertaintyStatement",
    "canonical_json_bytes",
    "content_sha256",
    "sha256_bytes",
]

__version__ = "1.0.0"

