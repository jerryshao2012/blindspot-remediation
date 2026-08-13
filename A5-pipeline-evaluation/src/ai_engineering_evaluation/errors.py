"""Typed failures for pipeline-level evaluation."""


class PipelineEvaluationError(Exception):
    """Base class for expected Component 5 failures."""


class BenchmarkValidationError(PipelineEvaluationError):
    """Benchmark structure or provenance is invalid."""


class OracleIntegrityError(PipelineEvaluationError):
    """Hidden oracle evidence is missing, altered, or invalid."""


class CampaignExecutionError(PipelineEvaluationError):
    """A qualification campaign cannot execute correctly."""


class GradingError(PipelineEvaluationError):
    """A benchmark candidate cannot be graded deterministically."""


class StatisticalAnalysisError(PipelineEvaluationError):
    """Requested statistical analysis is mathematically invalid."""


class ReadinessPolicyError(PipelineEvaluationError):
    """Readiness policy is internally inconsistent."""
