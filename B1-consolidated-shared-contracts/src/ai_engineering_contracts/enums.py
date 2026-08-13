"""
Canonical cross-component enumerations.

IMPORTANT CONSOLIDATION
-----------------------

Previous components introduced both:

    GateOutcome

and:

    GateDisposition

with almost identical meanings.

That is exactly the kind of duplication B1 removes.

There is now only:

    GateDisposition

Every component must import it from this package.

Do NOT recreate a local enum merely because an external provider uses different
words. Component 12 should translate the provider vocabulary into this one.
"""

from enum import StrEnum


class GateDisposition(StrEnum):
    """
    The four meaningful results of ReleaseGateService.

    PASS
        Existing evidence supports autonomous progression according to the
        applicable gate policy.

    FAIL
        Evidence provides a dominant failure signal or violates a mandatory
        gate requirement.

    MORE_EVIDENCE_REQUIRED
        The candidate has neither passed nor failed conclusively and another
        bounded evidence cycle may be justified.

    HUMAN_REVIEW_REQUIRED
        The autonomous gate cannot justify further autonomous progression.
        The actual human remains OUTSIDE ReleaseGateService.
    """

    PASS = "pass"
    FAIL = "fail"
    MORE_EVIDENCE_REQUIRED = "more_evidence_required"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


class RunState(StrEnum):
    """
    Canonical online orchestration states.

    RELEASE_APPROVAL_REQUIRED is included explicitly.

    This corrects the temporary Component 9 POC behaviour where a technically
    successful gate with auto-release disabled had to be represented as a
    PIPELINE_ERROR. That was useful while avoiding an unimplemented workflow,
    but it is not the correct final domain model.
    """

    CREATED = "created"
    VALIDATING = "validating"
    READY = "ready"

    EXECUTING_CHANGE = "executing_change"
    CANDIDATE_AVAILABLE = "candidate_available"

    GATING = "gating"
    MORE_EVIDENCE = "more_evidence"

    READY_FOR_RELEASE = "ready_for_release"
    RELEASE_APPROVAL_REQUIRED = "release_approval_required"

    HUMAN_REVIEW_REQUIRED = "human_review_required"

    RELEASED = "released"

    FAILED_VALIDATION = "failed_validation"
    CHANGE_FAILED = "change_failed"
    GATE_FAILED = "gate_failed"

    BUDGET_EXCEEDED = "budget_exceeded"
    PIPELINE_ERROR = "pipeline_error"
    CANCELLED = "cancelled"


class FinalDisposition(StrEnum):
    """
    Stable terminal classification independent of the detailed state machine.
    """

    RELEASED = "released"
    REJECTED = "rejected"

    HUMAN_REVIEW_REQUIRED = "human_review_required"
    RELEASE_APPROVAL_REQUIRED = "release_approval_required"

    BUDGET_EXCEEDED = "budget_exceeded"
    PIPELINE_ERROR = "pipeline_error"
    CANCELLED = "cancelled"


class TaskSourceKind(StrEnum):
    """
    Where a task entered the automation core.

    Component 5 normally uses BENCHMARK.
    Component 12 normally produces WORKFLOW.
    Manual demonstrations can use OPERATOR.
    """

    WORKFLOW = "workflow"
    OPERATOR = "operator"
    BENCHMARK = "benchmark"


class SpecificationStatus(StrEnum):
    DRAFT = "draft"
    QUALIFYING = "qualifying"
    APPROVED = "approved"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class RiskTier(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class SandboxRole(StrEnum):
    CHANGE_EXECUTION = "change_execution"
    RELEASE_GATE = "release_gate"
    BENCHMARK = "benchmark"


class ExecutionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    COMMAND_FAILED = "command_failed"
    TIMED_OUT = "timed_out"
    POLICY_DENIED = "policy_denied"
    INFRASTRUCTURE_FAILED = "infrastructure_failed"

