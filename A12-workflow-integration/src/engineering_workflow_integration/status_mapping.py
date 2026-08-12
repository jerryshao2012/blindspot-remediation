"""
Deterministic mapping from Component 3 outcomes to workflow status.

Important:

HUMAN_REVIEW_REQUIRED is NOT PASS.

It must remain blocking until the external engineering workflow performs the
human-review process.

MORE_EVIDENCE is also not PASS.

The gate has not yet established sufficient evidence.
"""

from __future__ import annotations

from .models import (
    ExternalStatus,
    ExternalStatusState,
    GatePublication,
)


DEFAULT_STATUS_GENRE = "ai-engineering-assurance"
DEFAULT_STATUS_NAME = "release-gate"


def map_gate_publication(
    publication: GatePublication,
) -> ExternalStatus:

    if publication.outcome.value == "pass":
        state = ExternalStatusState.SUCCEEDED

    elif publication.outcome.value == "fail":
        state = ExternalStatusState.FAILED

    elif publication.outcome.value == "more_evidence":
        state = ExternalStatusState.PENDING

    elif publication.outcome.value == "human_review_required":
        state = ExternalStatusState.PENDING

    else:
        # Defensive programming.
        #
        # GateOutcome is currently an enum, so this branch should not normally
        # be reachable. Keeping the failure explicit protects this code if the
        # contract evolves later.
        state = ExternalStatusState.ERROR

    return ExternalStatus(
        state=state,
        context_genre=DEFAULT_STATUS_GENRE,
        context_name=DEFAULT_STATUS_NAME,
        description=publication.summary,
        target_url=publication.evidence_uri,
    )
