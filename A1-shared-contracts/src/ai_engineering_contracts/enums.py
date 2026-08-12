"""
Enumerations shared by the three services.

String-valued enums are used because their serialized values remain readable
in JSON, YAML, logs, Azure Blob Storage, and pipeline output.
"""

from enum import StrEnum


class ExecutionStatus(StrEnum):
    """Final status of one change-execution attempt."""

    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    BUDGET_EXHAUSTED = "budget_exhausted"
    INVALID_REQUEST = "invalid_request"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GateDecision(StrEnum):
    """
    Release-gate recommendation.

    HUMAN_REVIEW_REQUIRED is a signal emitted to an external workflow. A human
    does not operate inside ReleaseGateService.

    MORE_EVIDENCE_REQUIRED means the current run did not establish a dominant
    failure, but the available evidence is insufficient and another automated
    evidence round may still be justified.
    """

    PASS = "pass"
    FAIL = "fail"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    MORE_EVIDENCE_REQUIRED = "more_evidence_required"


class ReadinessDecision(StrEnum):
    """Qualification level assigned to an executor/gate configuration."""

    NOT_QUALIFIED = "not_qualified"
    SHADOW_MODE = "shadow_mode"
    HUMAN_GATED = "human_gated"
    CONDITIONAL_AUTOMATION = "conditional_automation"


class CheckStatus(StrEnum):
    """Normalized status for a deterministic or qualified check."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"
    ERROR = "error"
    NOT_APPLICABLE = "not_applicable"


class ControlSeverity(StrEnum):
    """Importance of a control result to release policy."""

    INFORMATIONAL = "informational"
    ADVISORY = "advisory"
    MANDATORY = "mandatory"
    DOMINANT_FAILURE = "dominant_failure"


class ArtifactKind(StrEnum):
    """Recognized artifact types exchanged by the services."""

    TASK_PACKAGE = "task_package"
    REQUIREMENT_CONTRACT = "requirement_contract"
    EVALUATION_SPECIFICATION = "evaluation_specification"
    RELEASE_POLICY = "release_policy"
    REPOSITORY_SNAPSHOT = "repository_snapshot"
    PATCH = "patch"
    EXECUTION_TRACE = "execution_trace"
    EXECUTION_RESULT = "execution_result"
    TEST_RESULTS = "test_results"
    COVERAGE_REPORT = "coverage_report"
    MUTATION_REPORT = "mutation_report"
    STATIC_ANALYSIS_REPORT = "static_analysis_report"
    SECURITY_REPORT = "security_report"
    CHANGE_EVIDENCE_MODEL = "change_evidence_model"
    EVIDENCE_PACKAGE = "evidence_package"
    GATE_RESULT = "gate_result"
    HIDDEN_ORACLE = "hidden_oracle"
    REFERENCE_SOLUTION = "reference_solution"
    VALIDATION_RECORD = "validation_record"
    CAMPAIGN_REPORT = "campaign_report"
    HUMAN_REVIEW = "human_review"
    OTHER = "other"


class EvidenceStrategy(StrEnum):
    """Evidence-generation or evidence-collection strategy."""

    EXISTING_TESTS = "existing_tests"
    HIDDEN_REGRESSION_TESTS = "hidden_regression_tests"
    COMPILATION = "compilation"
    TYPE_CHECKING = "type_checking"
    STATIC_ANALYSIS = "static_analysis"
    SECURITY_SCANNING = "security_scanning"
    DEPENDENCY_SCANNING = "dependency_scanning"
    REQUIREMENT_FIRST_TEST_SYNTHESIS = "requirement_first_test_synthesis"
    BOUNDARY_TEST_SYNTHESIS = "boundary_test_synthesis"
    ARTIFACT_AWARE_TEST_SYNTHESIS = "artifact_aware_test_synthesis"
    MUTATION_TESTING = "mutation_testing"
    MUTATION_TARGETED_TEST_SYNTHESIS = "mutation_targeted_test_synthesis"
    PROPERTY_BASED_TESTING = "property_based_testing"
    FUZZING = "fuzzing"
    DIFFERENTIAL_TESTING = "differential_testing"
    METAMORPHIC_TESTING = "metamorphic_testing"
    PERFORMANCE_TESTING = "performance_testing"
    FOCUSED_STATIC_QUERY = "focused_static_query"
    AI_SEMANTIC_REVIEW = "ai_semantic_review"


class BenchmarkOrigin(StrEnum):
    """How a benchmark case was created."""

    CURATED_REAL = "curated_real"
    MECHANICALLY_MUTATED = "mechanically_mutated"
    AI_ASSISTED_SYNTHETIC = "ai_assisted_synthetic"
    FULLY_SYNTHETIC = "fully_synthetic"


class ReviewDisposition(StrEnum):
    """Structured outcome of an external human review."""

    ACCEPTED_WITHOUT_CHANGE = "accepted_without_change"
    ACCEPTED_WITH_MINOR_CHANGE = "accepted_with_minor_change"
    ACCEPTED_WITH_SUBSTANTIVE_CHANGE = "accepted_with_substantive_change"
    REJECTED_INCORRECT_IMPLEMENTATION = "rejected_incorrect_implementation"
    REJECTED_UNSAFE_CHANGE = "rejected_unsafe_change"
    REJECTED_OUT_OF_SCOPE = "rejected_out_of_scope"
    REJECTED_INSUFFICIENT_EVIDENCE = "rejected_insufficient_evidence"
    DEFERRED = "deferred"
