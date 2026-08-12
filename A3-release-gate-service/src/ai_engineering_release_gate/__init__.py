"""
Deterministic release-gating service.

The public façade is ``ReleaseGateService``.

This component independently reconstructs and evaluates a candidate patch in a
clean repository workspace. It does not trust executor-local test results as
release evidence.

Current scope
-------------
* Candidate and patch integrity validation.
* Clean-room candidate reconstruction.
* Repository-scope validation.
* Configurable deterministic controls.
* JUnit XML, Coverage.py JSON, and generic JSON metric extraction.
* Immutable evidence-package creation.
* Deterministic release-policy evaluation.
* PASS, FAIL, HUMAN_REVIEW_REQUIRED, or MORE_EVIDENCE_REQUIRED.

Deliberately excluded from this version
---------------------------------------
* LLM-based requirement interpretation.
* AI-generated tests.
* Mutation-guided test synthesis.
* Evidence-diversity mapping.
* AI evidence planning.
* Human activity inside the gate.
* Code merge or deployment.
"""

from .models import (
    DeterministicGateExecutionRequest,
    EvaluationSpecification,
    GateRuntimeSettings,
    ReleasePolicy,
    RequirementContract,
)
from .service import ReleaseGateService

__all__ = [
    "DeterministicGateExecutionRequest",
    "EvaluationSpecification",
    "GateRuntimeSettings",
    "ReleaseGateService",
    "ReleasePolicy",
    "RequirementContract",
]

__version__ = "0.1.0"
