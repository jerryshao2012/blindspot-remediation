"""
Offline qualification of the AI engineering automation pipeline.

Component 5 deliberately separates:

    execution
    grading
    measurement
    statistical inference
    readiness policy

This separation prevents a common evaluation mistake:

    "The benchmark score was 95%, therefore the system is ready."

A point estimate alone is not a readiness argument.

We also need:

    sample size
    uncertainty
    task composition
    failure severity
    release-decision correctness
    benchmark validity
"""

from .benchmark import BenchmarkFactory
from .campaign import EvaluationCampaignRunner, PipelineAdapter
from .grading import DeterministicOracleGrader
from .metrics import CampaignMetricsCalculator
from .readiness import ReadinessEvaluator
from .statistics import StatisticalAnalyzer

__all__ = [
    "BenchmarkFactory",
    "CampaignMetricsCalculator",
    "DeterministicOracleGrader",
    "EvaluationCampaignRunner",
    "PipelineAdapter",
    "ReadinessEvaluator",
    "StatisticalAnalyzer",
]

__version__ = "0.1.0"
