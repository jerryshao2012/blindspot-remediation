"""
Typed contracts exchanged by the AI engineering platform services.

Design principles
-----------------
* The executor produces a candidate patch, not a release decision.
* Executor-local tests are claims and are never authoritative release evidence.
* The release gate independently generates and executes evidence.
* The gate emits a recommendation; it does not merge or deploy code.
* Human review occurs outside the gate.
* The pipeline evaluator sees hidden benchmark truth only after the gate has
  finalized its decision.
* Many tests against one patch improve artifact-level fault search but do not
  become many independent task-level observations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Self

from pydantic import (
    Field,
    PositiveInt,
    field_validator,
    model_validator,
)

from .base import (
    ContractModel,
    ensure_timezone_aware,
    utc_now,
    validate_metadata,
    validate_relative_glob,
    validate_uri,
)
from .constants import (
    CONTRACT_PACKAGE_VERSION,
    GIT_COMMIT_PATTERN,
    MAX_DESCRIPTION_LENGTH,
    MAX_ESTIMATED_COST,
    MAX_IDENTIFIER_LENGTH,
    MAX_ITERATIONS,
    MAX_LLM_CALLS,
    MAX_LIST_ITEMS,
    MAX_REASON_LENGTH,
    MAX_RUNTIME_SECONDS,
    MAX_SHORT_TEXT_LENGTH,
    MAX_TOKEN_BUDGET,
    MAX_TOOL_CALLS,
    SAFE_IDENTIFIER_PATTERN,
    SEMANTIC_VERSION_PATTERN,
)
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

Identifier = Annotated[
    str,
    Field(
        min_length=1,
        max_length=MAX_IDENTIFIER_LENGTH,
        pattern=SAFE_IDENTIFIER_PATTERN,
    ),
]

SemanticVersion = Annotated[
    str,
    Field(
        min_length=5,
        max_length=128,
        pattern=SEMANTIC_VERSION_PATTERN,
    ),
]

GitCommit = Annotated[
    str,
    Field(pattern=GIT_COMMIT_PATTERN),
]

ShortText = Annotated[
    str,
    Field(min_length=1, max_length=MAX_SHORT_TEXT_LENGTH),
]

Description = Annotated[
    str,
    Field(min_length=1, max_length=MAX_DESCRIPTION_LENGTH),
]

ReasonText = Annotated[
    str,
    Field(min_length=1, max_length=MAX_REASON_LENGTH),
]

Probability = Annotated[float, Field(ge=0.0, le=1.0)]
NonNegativeFloat = Annotated[float, Field(ge=0.0)]
NonNegativeInt = Annotated[int, Field(ge=0)]
Percentage = Annotated[float, Field(ge=0.0, le=100.0)]


class TokenUsage(ContractModel):
    """
    Token and cost ledger for one component or activity.

    ``cached_input_tokens`` are included in ``input_tokens``. They are recorded
    separately to support cost and caching analysis but must not be added again
    when calculating total processed tokens.
    """

    input_tokens: NonNegativeInt = 0
    output_tokens: NonNegativeInt = 0
    cached_input_tokens: NonNegativeInt = 0
    reasoning_tokens: NonNegativeInt = 0
    llm_calls: NonNegativeInt = 0
    estimated_cost: NonNegativeFloat = 0.0
    currency: Annotated[str, Field(min_length=3, max_length=3)] = "USD"

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """Normalize ISO-style currency codes to uppercase."""
        if not value.isalpha():
            raise ValueError("currency must contain exactly three letters.")
        return value.upper()

    @model_validator(mode="after")
    def validate_token_relationships(self) -> Self:
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError(
                "cached_input_tokens cannot exceed input_tokens because cached "
                "tokens are a subset of input tokens."
            )
        if self.llm_calls == 0 and (
            self.input_tokens > 0
            or self.output_tokens > 0
            or self.reasoning_tokens > 0
        ):
            raise ValueError(
                "llm_calls must be greater than zero when token counts are present."
            )
        if self.llm_calls > 0 and self.input_tokens == 0:
            raise ValueError(
                "input_tokens must be greater than zero when llm_calls is positive."
            )
        return self

    @property
    def processed_tokens(self) -> int:
        """Total non-duplicated input, output, and reported reasoning tokens."""
        return self.input_tokens + self.output_tokens + self.reasoning_tokens

    def add(self, other: "TokenUsage") -> "TokenUsage":
        """
        Add two ledgers that use the same currency.

        The method returns a new immutable instance.
        """
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot add token costs in {self.currency} and {other.currency}."
            )
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cached_input_tokens=(
                self.cached_input_tokens + other.cached_input_tokens
            ),
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
            llm_calls=self.llm_calls + other.llm_calls,
            estimated_cost=self.estimated_cost + other.estimated_cost,
            currency=self.currency,
        )


class ExecutionBudget(ContractModel):
    """
    Maximum resources available to ChangeExecutionService.

    These values are ceilings, not targets. The executor should stop as soon as
    it has produced a valid candidate or determined that it cannot proceed.
    """

    maximum_llm_calls: Annotated[int, Field(ge=0, le=MAX_LLM_CALLS)]
    maximum_input_tokens: Annotated[int, Field(ge=0, le=MAX_TOKEN_BUDGET)]
    maximum_output_tokens: Annotated[int, Field(ge=0, le=MAX_TOKEN_BUDGET)]
    maximum_tool_calls: Annotated[int, Field(ge=0, le=MAX_TOOL_CALLS)]
    maximum_repair_iterations: Annotated[int, Field(ge=0, le=MAX_ITERATIONS)]
    maximum_runtime_seconds: Annotated[int, Field(gt=0, le=MAX_RUNTIME_SECONDS)]
    maximum_estimated_cost: Annotated[
        float,
        Field(ge=0.0, le=MAX_ESTIMATED_COST),
    ]
    currency: Annotated[str, Field(min_length=3, max_length=3)] = "USD"

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("currency must contain exactly three letters.")
        return value.upper()

    @model_validator(mode="after")
    def validate_llm_budget(self) -> Self:
        if self.maximum_llm_calls == 0:
            if self.maximum_input_tokens != 0 or self.maximum_output_tokens != 0:
                raise ValueError(
                    "Token budgets must be zero when maximum_llm_calls is zero."
                )
            if self.maximum_estimated_cost != 0.0:
                raise ValueError(
                    "maximum_estimated_cost must be zero when LLM use is disabled."
                )
        return self


class EvidenceBudget(ContractModel):
    """
    Resource and iteration budget available to ReleaseGateService.

    A release gate may consume more tokens than the executor when it performs
    independent, mutation-guided or adversarial test synthesis. The contract
    therefore records gate resources independently of execution resources.
    """

    maximum_llm_calls: Annotated[int, Field(ge=0, le=MAX_LLM_CALLS)]
    maximum_input_tokens: Annotated[int, Field(ge=0, le=MAX_TOKEN_BUDGET)]
    maximum_output_tokens: Annotated[int, Field(ge=0, le=MAX_TOKEN_BUDGET)]
    maximum_evidence_rounds: Annotated[int, Field(gt=0, le=MAX_ITERATIONS)]
    maximum_generated_tests: Annotated[int, Field(ge=0, le=MAX_LIST_ITEMS)]
    maximum_mutants: Annotated[int, Field(ge=0, le=MAX_LIST_ITEMS)]
    maximum_tool_calls: Annotated[int, Field(ge=0, le=MAX_TOOL_CALLS)]
    maximum_runtime_seconds: Annotated[int, Field(gt=0, le=MAX_RUNTIME_SECONDS)]
    maximum_estimated_cost: Annotated[
        float,
        Field(ge=0.0, le=MAX_ESTIMATED_COST),
    ]
    currency: Annotated[str, Field(min_length=3, max_length=3)] = "USD"
    allowed_strategies: list[EvidenceStrategy] = Field(
        min_length=1,
        max_length=len(EvidenceStrategy),
    )

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("currency must contain exactly three letters.")
        return value.upper()

    @field_validator("allowed_strategies")
    @classmethod
    def reject_duplicate_strategies(
        cls,
        value: list[EvidenceStrategy],
    ) -> list[EvidenceStrategy]:
        if len(value) != len(set(value)):
            raise ValueError("allowed_strategies must not contain duplicates.")
        return value

    @model_validator(mode="after")
    def validate_ai_budget(self) -> Self:
        ai_strategies = {
            EvidenceStrategy.REQUIREMENT_FIRST_TEST_SYNTHESIS,
            EvidenceStrategy.BOUNDARY_TEST_SYNTHESIS,
            EvidenceStrategy.ARTIFACT_AWARE_TEST_SYNTHESIS,
            EvidenceStrategy.MUTATION_TARGETED_TEST_SYNTHESIS,
            EvidenceStrategy.AI_SEMANTIC_REVIEW,
        }
        if self.maximum_llm_calls == 0:
            if any(strategy in ai_strategies for strategy in self.allowed_strategies):
                raise ValueError(
                    "AI-assisted evidence strategies cannot be allowed when "
                    "maximum_llm_calls is zero."
                )
            if self.maximum_input_tokens != 0 or self.maximum_output_tokens != 0:
                raise ValueError(
                    "Token budgets must be zero when maximum_llm_calls is zero."
                )
            if self.maximum_estimated_cost != 0.0:
                raise ValueError(
                    "maximum_estimated_cost must be zero when LLM use is disabled."
                )
        return self


class ModelConfiguration(ContractModel):
    """
    Reproducibility record for an LLM deployment.

    ``deployment_name`` is the enterprise deployment identifier. ``model_name``
    and ``model_version`` identify the underlying model when that information is
    available. No API key, bearer token, or connection secret belongs here.
    """

    provider: Identifier
    deployment_name: Identifier
    model_name: Identifier
    model_version: ShortText
    endpoint_region: ShortText | None = None
    temperature: Annotated[float, Field(ge=0.0, le=2.0)] = 0.0
    top_p: Probability = 1.0
    seed: int | None = None
    maximum_output_tokens_per_call: Annotated[
        int,
        Field(gt=0, le=MAX_TOKEN_BUDGET),
    ]
    configuration_metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("configuration_metadata")
    @classmethod
    def validate_configuration_metadata(
        cls,
        value: dict[str, str],
    ) -> dict[str, str]:
        return validate_metadata(value)


class ArtifactReference(ContractModel):
    """
    Immutable reference to an external artifact.

    Large content is stored outside the contract. ``sha256`` verifies content
    integrity after retrieval. A SHA-256 value is strongly recommended for
    release evidence and mandatory for artifacts marked immutable.
    """

    artifact_id: Identifier
    kind: ArtifactKind
    uri: Annotated[str, Field(min_length=1, max_length=4_096)]
    sha256: Annotated[
        str,
        Field(pattern=r"^[0-9a-fA-F]{64}$"),
    ] | None = None
    media_type: Annotated[str, Field(min_length=3, max_length=255)]
    size_bytes: NonNegativeInt | None = None
    created_at: datetime = Field(default_factory=utc_now)
    immutable: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("uri")
    @classmethod
    def validate_artifact_uri(cls, value: str) -> str:
        return validate_uri(value, "uri")

    @field_validator("sha256")
    @classmethod
    def normalize_sha256(cls, value: str | None) -> str | None:
        return value.lower() if value is not None else None

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return ensure_timezone_aware(value, "created_at")

    @field_validator("metadata")
    @classmethod
    def validate_artifact_metadata(
        cls,
        value: dict[str, str],
    ) -> dict[str, str]:
        return validate_metadata(value)

    @model_validator(mode="after")
    def require_digest_for_immutable_artifact(self) -> Self:
        if self.immutable and self.sha256 is None:
            raise ValueError(
                "Immutable artifacts must include a SHA-256 digest."
            )
        return self


class CheckResult(ContractModel):
    """
    Result reported by the executor for a local feedback check.

    This is retained as an executor claim. ReleaseGateService must independently
    rerun authoritative checks in a clean environment.
    """

    check_id: Identifier
    name: ShortText
    status: CheckStatus
    started_at: datetime
    completed_at: datetime
    command_name: ShortText | None = None
    exit_code: int | None = None
    summary: ReasonText
    report: ArtifactReference | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    is_authoritative_release_evidence: bool = False

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return ensure_timezone_aware(value, "check timestamp")

    @field_validator("metrics")
    @classmethod
    def validate_finite_metrics(
        cls,
        value: dict[str, float],
    ) -> dict[str, float]:
        import math

        for key, metric in value.items():
            if not key.strip():
                raise ValueError("Metric names must not be blank.")
            if not math.isfinite(metric):
                raise ValueError(f"Metric {key!r} must be finite.")
        return value

    @model_validator(mode="after")
    def validate_timing_and_status(self) -> Self:
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at.")
        if self.status in {CheckStatus.PASSED, CheckStatus.FAILED}:
            if self.exit_code is None:
                raise ValueError(
                    "A passed or failed command check must include exit_code."
                )
        if self.is_authoritative_release_evidence:
            raise ValueError(
                "Executor CheckResult records cannot be marked as authoritative "
                "release evidence. Authoritative evidence must be generated by "
                "ReleaseGateService."
            )
        return self


class ToolUsageRecord(ContractModel):
    """Auditable summary of one executor or gate tool invocation."""

    call_id: Identifier
    tool_name: Identifier
    started_at: datetime
    completed_at: datetime
    succeeded: bool
    input_fingerprint: Annotated[
        str,
        Field(pattern=r"^[0-9a-fA-F]{64}$"),
    ]
    output_fingerprint: Annotated[
        str,
        Field(pattern=r"^[0-9a-fA-F]{64}$"),
    ] | None = None
    error_type: ShortText | None = None
    error_message: ReasonText | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return ensure_timezone_aware(value, "tool timestamp")

    @field_validator("input_fingerprint", "output_fingerprint")
    @classmethod
    def normalize_fingerprint(cls, value: str | None) -> str | None:
        return value.lower() if value is not None else None

    @field_validator("metadata")
    @classmethod
    def validate_tool_metadata(
        cls,
        value: dict[str, str],
    ) -> dict[str, str]:
        return validate_metadata(value)

    @model_validator(mode="after")
    def validate_tool_outcome(self) -> Self:
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at.")
        if self.succeeded:
            if self.error_type is not None or self.error_message is not None:
                raise ValueError(
                    "Successful tool calls cannot include error fields."
                )
            if self.output_fingerprint is None:
                raise ValueError(
                    "Successful tool calls must include output_fingerprint."
                )
        elif self.error_type is None:
            raise ValueError("Failed tool calls must include error_type.")
        return self


class TaskRunRequest(ContractModel):
    """
    Formal request for one bounded code-change execution.

    During the POC this record may be authored manually. A future Jira intake
    service may generate it without changing the executor interface.
    """

    contract_version: SemanticVersion = CONTRACT_PACKAGE_VERSION
    run_id: Identifier
    task_type: Identifier
    task_package_version: SemanticVersion
    repository_url: Annotated[str, Field(min_length=1, max_length=4_096)]
    base_commit: GitCommit
    target_branch: ShortText
    task_description: Description
    acceptance_criteria: list[Description] = Field(
        min_length=1,
        max_length=1_000,
    )
    permitted_paths: list[ShortText] = Field(
        min_length=1,
        max_length=10_000,
    )
    prohibited_paths: list[ShortText] = Field(
        default_factory=list,
        max_length=10_000,
    )
    execution_budget: ExecutionBudget
    requested_at: datetime = Field(default_factory=utc_now)
    requested_by: ShortText
    correlation_id: Identifier | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("repository_url")
    @classmethod
    def validate_repository_url(cls, value: str) -> str:
        return validate_uri(value, "repository_url")

    @field_validator("target_branch")
    @classmethod
    def validate_target_branch(cls, value: str) -> str:
        if value.startswith("-"):
            raise ValueError("target_branch must not begin with '-'.")
        if value.endswith("/") or value.startswith("/"):
            raise ValueError("target_branch must not begin or end with '/'.")
        if ".." in value or "@{" in value or "\\" in value:
            raise ValueError("target_branch contains a prohibited Git ref sequence.")
        return value

    @field_validator("acceptance_criteria")
    @classmethod
    def reject_duplicate_acceptance_criteria(
        cls,
        value: list[str],
    ) -> list[str]:
        normalized = [item.casefold() for item in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("acceptance_criteria must not contain duplicates.")
        return value

    @field_validator("permitted_paths", "prohibited_paths")
    @classmethod
    def validate_path_patterns(cls, value: list[str]) -> list[str]:
        validated = [
            validate_relative_glob(item, "repository path pattern")
            for item in value
        ]
        if len(validated) != len(set(validated)):
            raise ValueError("Repository path patterns must not contain duplicates.")
        return validated

    @field_validator("requested_at")
    @classmethod
    def validate_requested_at(cls, value: datetime) -> datetime:
        return ensure_timezone_aware(value, "requested_at")

    @field_validator("metadata")
    @classmethod
    def validate_request_metadata(
        cls,
        value: dict[str, str],
    ) -> dict[str, str]:
        return validate_metadata(value)

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        exact_overlap = set(self.permitted_paths) & set(self.prohibited_paths)
        if exact_overlap:
            raise ValueError(
                "The same path pattern cannot be both permitted and prohibited: "
                f"{sorted(exact_overlap)}."
            )
        return self


class ExecutionResult(ContractModel):
    """
    Immutable output of ChangeExecutionService.

    The presence of a candidate commit does not imply release approval.
    ``local_check_results`` remain non-authoritative executor claims.
    """

    contract_version: SemanticVersion = CONTRACT_PACKAGE_VERSION
    run_id: Identifier
    executor_version: SemanticVersion
    status: ExecutionStatus
    base_commit: GitCommit
    candidate_commit: GitCommit | None = None
    patch_artifact: ArtifactReference | None = None
    changed_files: list[ShortText] = Field(
        default_factory=list,
        max_length=MAX_LIST_ITEMS,
    )
    local_check_results: list[CheckResult] = Field(
        default_factory=list,
        max_length=MAX_LIST_ITEMS,
    )
    model_configuration: ModelConfiguration | None = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    tool_usage: list[ToolUsageRecord] = Field(
        default_factory=list,
        max_length=MAX_LIST_ITEMS,
    )
    execution_trace: ArtifactReference
    started_at: datetime
    completed_at: datetime
    failure_reason: ReasonText | None = None
    incomplete_reason: ReasonText | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("changed_files")
    @classmethod
    def validate_changed_files(cls, value: list[str]) -> list[str]:
        validated = [
            validate_relative_glob(item, "changed file")
            for item in value
        ]
        if len(validated) != len(set(validated)):
            raise ValueError("changed_files must not contain duplicates.")
        return validated

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return ensure_timezone_aware(value, "execution timestamp")

    @field_validator("metadata")
    @classmethod
    def validate_result_metadata(
        cls,
        value: dict[str, str],
    ) -> dict[str, str]:
        return validate_metadata(value)

    @model_validator(mode="after")
    def validate_execution_outcome(self) -> Self:
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at.")
        completed = self.status == ExecutionStatus.COMPLETED
        if completed:
            if self.candidate_commit is None:
                raise ValueError(
                    "A completed execution must include candidate_commit."
                )
            if self.patch_artifact is None:
                raise ValueError(
                    "A completed execution must include patch_artifact."
                )
            if self.failure_reason is not None or self.incomplete_reason is not None:
                raise ValueError(
                    "A completed execution cannot include failure or incomplete reasons."
                )
        else:
            if self.status in {
                ExecutionStatus.FAILED,
                ExecutionStatus.INVALID_REQUEST,
            } and self.failure_reason is None:
                raise ValueError(
                    f"Execution status {self.status.value!r} requires failure_reason."
                )
            if self.status in {
                ExecutionStatus.INCOMPLETE,
                ExecutionStatus.BUDGET_EXHAUSTED,
                ExecutionStatus.CANCELLED,
            } and self.incomplete_reason is None:
                raise ValueError(
                    f"Execution status {self.status.value!r} requires incomplete_reason."
                )
        if self.model_configuration is None and self.token_usage.llm_calls > 0:
            raise ValueError(
                "model_configuration is required when LLM usage is recorded."
            )
        if self.model_configuration is not None and self.token_usage.llm_calls == 0:
            raise ValueError(
                "LLM model_configuration was supplied but no LLM calls were recorded."
            )
        return self


class GateRequest(ContractModel):
    """
    Request for independent assurance of one immutable candidate commit.
    """

    contract_version: SemanticVersion = CONTRACT_PACKAGE_VERSION
    run_id: Identifier
    task_type: Identifier
    task_package_version: SemanticVersion
    gate_version: SemanticVersion
    repository_url: Annotated[str, Field(min_length=1, max_length=4_096)]
    base_commit: GitCommit
    candidate_commit: GitCommit
    requirement_contract: ArtifactReference
    evaluation_specification: ArtifactReference
    release_policy: ArtifactReference
    evidence_budget: EvidenceBudget
    requested_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("repository_url")
    @classmethod
    def validate_repository_url(cls, value: str) -> str:
        return validate_uri(value, "repository_url")

    @field_validator("requested_at")
    @classmethod
    def validate_requested_at(cls, value: datetime) -> datetime:
        return ensure_timezone_aware(value, "requested_at")

    @field_validator("metadata")
    @classmethod
    def validate_gate_request_metadata(
        cls,
        value: dict[str, str],
    ) -> dict[str, str]:
        return validate_metadata(value)

    @model_validator(mode="after")
    def validate_gate_artifacts(self) -> Self:
        expected_kinds = {
            "requirement_contract": (
                self.requirement_contract,
                ArtifactKind.REQUIREMENT_CONTRACT,
            ),
            "evaluation_specification": (
                self.evaluation_specification,
                ArtifactKind.EVALUATION_SPECIFICATION,
            ),
            "release_policy": (
                self.release_policy,
                ArtifactKind.RELEASE_POLICY,
            ),
        }
        for field_name, (artifact, expected_kind) in expected_kinds.items():
            if artifact.kind != expected_kind:
                raise ValueError(
                    f"{field_name} must reference artifact kind "
                    f"{expected_kind.value!r}, not {artifact.kind.value!r}."
                )
        if self.base_commit == self.candidate_commit:
            raise ValueError(
                "candidate_commit must differ from base_commit; otherwise there is "
                "no candidate change to evaluate."
            )
        return self


class ControlResult(ContractModel):
    """
    Result of one authoritative gate control.

    Controls can be deterministic or AI-assisted, but a mechanically decidable
    fact should always be established by deterministic execution.
    """

    control_id: Identifier
    name: ShortText
    status: CheckStatus
    severity: ControlSeverity
    strategy: EvidenceStrategy
    deterministic_authority: bool
    summary: ReasonText
    started_at: datetime
    completed_at: datetime
    evidence_artifacts: list[ArtifactReference] = Field(
        default_factory=list,
        max_length=1_000,
    )
    metrics: dict[str, float] = Field(default_factory=dict)
    reasons: list[ReasonText] = Field(
        default_factory=list,
        max_length=1_000,
    )

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return ensure_timezone_aware(value, "control timestamp")

    @field_validator("metrics")
    @classmethod
    def validate_finite_metrics(
        cls,
        value: dict[str, float],
    ) -> dict[str, float]:
        import math

        for key, metric in value.items():
            if not key.strip():
                raise ValueError("Metric names must not be blank.")
            if not math.isfinite(metric):
                raise ValueError(f"Metric {key!r} must be finite.")
        return value

    @model_validator(mode="after")
    def validate_control(self) -> Self:
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at.")
        if (
            self.severity == ControlSeverity.DOMINANT_FAILURE
            and self.status not in {CheckStatus.FAILED, CheckStatus.ERROR}
        ):
            raise ValueError(
                "DOMINANT_FAILURE severity is valid only for a failed or errored "
                "control."
            )
        return self


class GateResult(ContractModel):
    """
    Immutable output of ReleaseGateService.

    The decision is produced by a deterministic policy engine from qualified
    evidence. AI may propose tests, hypotheses, or semantic interpretations,
    but it must not directly override mechanically decidable facts or emit the
    final release decision.
    """

    contract_version: SemanticVersion = CONTRACT_PACKAGE_VERSION
    run_id: Identifier
    gate_version: SemanticVersion
    policy_version: SemanticVersion
    decision: GateDecision
    base_commit: GitCommit
    candidate_commit: GitCommit
    evidence_package: ArtifactReference
    hard_control_results: list[ControlResult] = Field(
        default_factory=list,
        max_length=MAX_LIST_ITEMS,
    )
    evidence_metrics: dict[str, float] = Field(default_factory=dict)
    unmet_obligations: list[ReasonText] = Field(
        default_factory=list,
        max_length=MAX_LIST_ITEMS,
    )
    contradictions: list[ReasonText] = Field(
        default_factory=list,
        max_length=MAX_LIST_ITEMS,
    )
    decision_reasons: list[ReasonText] = Field(
        min_length=1,
        max_length=MAX_LIST_ITEMS,
    )
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    evidence_rounds_completed: PositiveInt
    generated_tests_considered: NonNegativeInt = 0
    qualified_generated_tests: NonNegativeInt = 0
    mutants_generated: NonNegativeInt = 0
    meaningful_mutants_survived: NonNegativeInt = 0
    started_at: datetime
    completed_at: datetime
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return ensure_timezone_aware(value, "gate timestamp")

    @field_validator("evidence_metrics")
    @classmethod
    def validate_finite_metrics(
        cls,
        value: dict[str, float],
    ) -> dict[str, float]:
        import math

        for key, metric in value.items():
            if not key.strip():
                raise ValueError("Metric names must not be blank.")
            if not math.isfinite(metric):
                raise ValueError(f"Metric {key!r} must be finite.")
        return value

    @field_validator("metadata")
    @classmethod
    def validate_gate_result_metadata(
        cls,
        value: dict[str, str],
    ) -> dict[str, str]:
        return validate_metadata(value)

    @model_validator(mode="after")
    def validate_gate_outcome(self) -> Self:
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at.")
        if self.base_commit == self.candidate_commit:
            raise ValueError("base_commit and candidate_commit must differ.")
        if self.evidence_package.kind != ArtifactKind.EVIDENCE_PACKAGE:
            raise ValueError(
                "evidence_package must reference an EVIDENCE_PACKAGE artifact."
            )
        if self.qualified_generated_tests > self.generated_tests_considered:
            raise ValueError(
                "qualified_generated_tests cannot exceed generated_tests_considered."
            )
        if self.meaningful_mutants_survived > self.mutants_generated:
            raise ValueError(
                "meaningful_mutants_survived cannot exceed mutants_generated."
            )
        dominant_failure_present = any(
            result.severity == ControlSeverity.DOMINANT_FAILURE
            and result.status in {CheckStatus.FAILED, CheckStatus.ERROR}
            for result in self.hard_control_results
        )
        mandatory_failure_present = any(
            result.severity == ControlSeverity.MANDATORY
            and result.status in {CheckStatus.FAILED, CheckStatus.ERROR}
            for result in self.hard_control_results
        )
        if dominant_failure_present and self.decision != GateDecision.FAIL:
            raise ValueError(
                "A dominant failure requires a FAIL gate decision."
            )
        if self.decision == GateDecision.PASS:
            if dominant_failure_present or mandatory_failure_present:
                raise ValueError(
                    "PASS is invalid when a dominant or mandatory control failed."
                )
            if self.unmet_obligations:
                raise ValueError(
                    "PASS is invalid while mandatory obligations remain unmet."
                )
            if self.contradictions:
                raise ValueError(
                    "PASS is invalid while unresolved contradictions remain."
                )
        if self.decision == GateDecision.MORE_EVIDENCE_REQUIRED:
            if dominant_failure_present:
                raise ValueError(
                    "MORE_EVIDENCE_REQUIRED is invalid after a dominant failure."
                )
            if not self.unmet_obligations and not self.contradictions:
                raise ValueError(
                    "MORE_EVIDENCE_REQUIRED requires at least one unmet obligation "
                    "or unresolved contradiction."
                )
        return self


class HumanReviewResult(ContractModel):
    """
    Structured outcome of a human review performed outside ReleaseGateService.
    """

    contract_version: SemanticVersion = CONTRACT_PACKAGE_VERSION
    review_id: Identifier
    run_id: Identifier
    reviewer_id: Identifier
    disposition: ReviewDisposition
    review_minutes: Annotated[float, Field(ge=0.0, le=100_000.0)]
    substantive_code_change_required: bool
    reviewer_reasons: list[ReasonText] = Field(
        min_length=1,
        max_length=1_000,
    )
    reviewed_at: datetime = Field(default_factory=utc_now)
    review_artifact: ArtifactReference | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("reviewed_at")
    @classmethod
    def validate_reviewed_at(cls, value: datetime) -> datetime:
        return ensure_timezone_aware(value, "reviewed_at")

    @field_validator("metadata")
    @classmethod
    def validate_review_metadata(
        cls,
        value: dict[str, str],
    ) -> dict[str, str]:
        return validate_metadata(value)

    @model_validator(mode="after")
    def validate_disposition(self) -> Self:
        substantive_dispositions = {
            ReviewDisposition.ACCEPTED_WITH_SUBSTANTIVE_CHANGE,
            ReviewDisposition.REJECTED_INCORRECT_IMPLEMENTATION,
            ReviewDisposition.REJECTED_UNSAFE_CHANGE,
        }
        if (
            self.disposition in substantive_dispositions
            and not self.substantive_code_change_required
        ):
            raise ValueError(
                f"Disposition {self.disposition.value!r} requires "
                "substantive_code_change_required=True."
            )
        if (
            self.disposition == ReviewDisposition.ACCEPTED_WITHOUT_CHANGE
            and self.substantive_code_change_required
        ):
            raise ValueError(
                "ACCEPTED_WITHOUT_CHANGE is incompatible with a substantive change."
            )
        return self


class BenchmarkCase(ContractModel):
    """
    One validated benchmark problem.

    Deterministic execution is necessary but not sufficient for ground truth.
    The validation record must establish that the clean repository passes, the
    defective repository fails appropriately, the reference solution passes,
    and plausible wrong solutions are rejected by the hidden oracle.
    """

    contract_version: SemanticVersion = CONTRACT_PACKAGE_VERSION
    benchmark_id: Identifier
    benchmark_version: SemanticVersion
    task_type: Identifier
    origin: BenchmarkOrigin
    repository_artifact: ArtifactReference
    base_commit: GitCommit
    task_request: TaskRunRequest
    reference_solution: ArtifactReference
    hidden_oracle: ArtifactReference
    known_bad_variants: list[ArtifactReference] = Field(
        min_length=1,
        max_length=1_000,
    )
    validation_record: ArtifactReference
    difficulty_attributes: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("difficulty_attributes")
    @classmethod
    def validate_difficulty_attributes(
        cls,
        value: dict[str, str],
    ) -> dict[str, str]:
        return validate_metadata(value)

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return ensure_timezone_aware(value, "created_at")

    @model_validator(mode="after")
    def validate_benchmark_artifacts(self) -> Self:
        expected = {
            "repository_artifact": (
                self.repository_artifact,
                ArtifactKind.REPOSITORY_SNAPSHOT,
            ),
            "reference_solution": (
                self.reference_solution,
                ArtifactKind.REFERENCE_SOLUTION,
            ),
            "hidden_oracle": (
                self.hidden_oracle,
                ArtifactKind.HIDDEN_ORACLE,
            ),
            "validation_record": (
                self.validation_record,
                ArtifactKind.VALIDATION_RECORD,
            ),
        }
        for field_name, (artifact, expected_kind) in expected.items():
            if artifact.kind != expected_kind:
                raise ValueError(
                    f"{field_name} must reference {expected_kind.value!r}, "
                    f"not {artifact.kind.value!r}."
                )
        if any(
            artifact.kind not in {
                ArtifactKind.PATCH,
                ArtifactKind.REFERENCE_SOLUTION,
            }
            for artifact in self.known_bad_variants
        ):
            raise ValueError(
                "known_bad_variants must be patch or reference-solution artifacts."
            )
        if self.task_request.task_type != self.task_type:
            raise ValueError(
                "Benchmark task_type must match task_request.task_type."
            )
        if self.task_request.base_commit != self.base_commit:
            raise ValueError(
                "Benchmark base_commit must match task_request.base_commit."
            )
        return self


class PipelineConfiguration(ContractModel):
    """
    Exact executor/gate configuration evaluated by a qualification campaign.
    """

    configuration_id: Identifier
    executor_version: SemanticVersion
    gate_version: SemanticVersion
    task_package_version: SemanticVersion
    benchmark_version: SemanticVersion
    executor_model: ModelConfiguration | None = None
    gate_models: list[ModelConfiguration] = Field(
        default_factory=list,
        max_length=100,
    )
    configuration_artifact: ArtifactReference
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def validate_pipeline_metadata(
        cls,
        value: dict[str, str],
    ) -> dict[str, str]:
        return validate_metadata(value)


class CampaignRequest(ContractModel):
    """
    Request to evaluate one frozen pipeline configuration.

    Repetitions help estimate nondeterminism within a benchmark case. They must
    not be treated as entirely independent benchmark problems.
    """

    contract_version: SemanticVersion = CONTRACT_PACKAGE_VERSION
    campaign_id: Identifier
    task_type: Identifier
    pipeline_configuration: PipelineConfiguration
    benchmark_cases: list[ArtifactReference] = Field(
        min_length=1,
        max_length=MAX_LIST_ITEMS,
    )
    repetitions_per_case: Annotated[int, Field(gt=0, le=1_000)]
    random_seed: int
    maximum_parallel_runs: Annotated[int, Field(gt=0, le=10_000)]
    requested_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("requested_at")
    @classmethod
    def validate_requested_at(cls, value: datetime) -> datetime:
        return ensure_timezone_aware(value, "requested_at")

    @field_validator("benchmark_cases")
    @classmethod
    def validate_benchmark_references(
        cls,
        value: list[ArtifactReference],
    ) -> list[ArtifactReference]:
        if any(item.kind != ArtifactKind.OTHER for item in value):
            # BenchmarkCase is itself a structured contract, not a binary artifact.
            # Until a dedicated BENCHMARK_CASE artifact kind is introduced, its
            # serialized JSON is represented with OTHER and a descriptive media type.
            raise ValueError(
                "Serialized BenchmarkCase references must currently use "
                "ArtifactKind.OTHER."
            )
        if len({item.artifact_id for item in value}) != len(value):
            raise ValueError("benchmark_cases must not contain duplicate IDs.")
        return value

    @field_validator("metadata")
    @classmethod
    def validate_campaign_metadata(
        cls,
        value: dict[str, str],
    ) -> dict[str, str]:
        return validate_metadata(value)


class StatisticalEstimate(ContractModel):
    """
    Point estimate with a confidence interval and explicit sample accounting.

    ``independent_case_count`` identifies the number of distinct underlying
    benchmark cases. ``total_observation_count`` can be larger because a case
    may be executed repeatedly to estimate stochastic variation.
    """

    metric_name: Identifier
    point_estimate: Probability
    confidence_level: Probability
    lower_bound: Probability
    upper_bound: Probability
    independent_case_count: PositiveInt
    total_observation_count: PositiveInt
    method: ShortText
    notes: ReasonText | None = None

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        if not 0.0 < self.confidence_level < 1.0:
            raise ValueError("confidence_level must be strictly between 0 and 1.")
        if self.lower_bound > self.point_estimate:
            raise ValueError("lower_bound cannot exceed point_estimate.")
        if self.point_estimate > self.upper_bound:
            raise ValueError("point_estimate cannot exceed upper_bound.")
        if self.independent_case_count > self.total_observation_count:
            raise ValueError(
                "independent_case_count cannot exceed total_observation_count."
            )
        return self


class CampaignResult(ContractModel):
    """
    Pipeline-level qualification result for one frozen configuration.

    Confusion-matrix counts refer to gate behaviour after the hidden oracle has
    independently graded the candidate. Infrastructure errors and invalid
    benchmark cases are reported separately and must not be silently counted as
    correct or incorrect gate decisions.
    """

    contract_version: SemanticVersion = CONTRACT_PACKAGE_VERSION
    campaign_id: Identifier
    pipeline_configuration: PipelineConfiguration
    unique_cases_attempted: PositiveInt
    total_executions_attempted: PositiveInt
    oracle_graded_executions: NonNegativeInt
    true_acceptances: NonNegativeInt
    false_acceptances: NonNegativeInt
    true_rejections: NonNegativeInt
    false_rejections: NonNegativeInt
    executor_failures: NonNegativeInt = 0
    gate_failures: NonNegativeInt = 0
    infrastructure_failures: NonNegativeInt = 0
    invalid_benchmark_cases: NonNegativeInt = 0
    task_success_rate: StatisticalEstimate
    gate_precision: StatisticalEstimate
    false_acceptance_rate: StatisticalEstimate
    total_token_usage: TokenUsage
    average_cost_per_oracle_confirmed_correct_change: NonNegativeFloat | None
    readiness_decision: ReadinessDecision
    readiness_reasons: list[ReasonText] = Field(
        min_length=1,
        max_length=1_000,
    )
    report: ArtifactReference
    started_at: datetime
    completed_at: datetime
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return ensure_timezone_aware(value, "campaign timestamp")

    @field_validator("metadata")
    @classmethod
    def validate_result_metadata(
        cls,
        value: dict[str, str],
    ) -> dict[str, str]:
        return validate_metadata(value)

    @model_validator(mode="after")
    def validate_campaign_counts(self) -> Self:
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at.")
        confusion_matrix_total = (
            self.true_acceptances
            + self.false_acceptances
            + self.true_rejections
            + self.false_rejections
        )
        if confusion_matrix_total != self.oracle_graded_executions:
            raise ValueError(
                "The confusion-matrix total must equal oracle_graded_executions."
            )
        accounted_executions = (
            self.oracle_graded_executions
            + self.executor_failures
            + self.gate_failures
            + self.infrastructure_failures
        )
        if accounted_executions > self.total_executions_attempted:
            raise ValueError(
                "Accounted executions cannot exceed total_executions_attempted."
            )
        if self.unique_cases_attempted > self.total_executions_attempted:
            raise ValueError(
                "unique_cases_attempted cannot exceed total_executions_attempted."
            )
        estimates = (
            self.task_success_rate,
            self.gate_precision,
            self.false_acceptance_rate,
        )
        for estimate in estimates:
            if estimate.total_observation_count != self.oracle_graded_executions:
                raise ValueError(
                    f"{estimate.metric_name} total_observation_count must equal "
                    "oracle_graded_executions."
                )
            if estimate.independent_case_count > self.unique_cases_attempted:
                raise ValueError(
                    f"{estimate.metric_name} independent_case_count cannot exceed "
                    "unique_cases_attempted."
                )
        if self.report.kind != ArtifactKind.CAMPAIGN_REPORT:
            raise ValueError(
                "report must reference a CAMPAIGN_REPORT artifact."
            )
        confirmed_correct_changes = self.true_acceptances + self.false_rejections
        if (
            confirmed_correct_changes == 0
            and self.average_cost_per_oracle_confirmed_correct_change is not None
        ):
            raise ValueError(
                "Average cost per correct change must be None when no correct "
                "changes were observed."
            )
        if (
            confirmed_correct_changes > 0
            and self.average_cost_per_oracle_confirmed_correct_change is None
        ):
            raise ValueError(
                "Average cost per correct change is required when correct changes "
                "were observed."
            )
        return self
