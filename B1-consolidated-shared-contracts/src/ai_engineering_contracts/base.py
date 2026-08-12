"""
Common Pydantic behaviour for all cross-component contracts.

WHY THIS FILE EXISTS
--------------------

During early prototyping it is easy for one component to accept unexpected
fields while another silently ignores them. That is undesirable in an
assurance-oriented platform because contract drift can remain invisible.

All shared contracts therefore:

    * reject unknown fields;
    * are immutable after construction;
    * strip surrounding whitespace;
    * validate default values.

Immutability is especially useful for objects such as GateDecision,
TaskSpecification and ExecutionReceipt. If evidence is later changed, the
platform should create a NEW object rather than silently mutating the historical
one.

This does not make the objects cryptographically immutable. Component 4 remains
responsible for durable evidence integrity.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
)

from typing_extensions import Annotated


CONTRACT_SCHEMA_VERSION = "1.0.0"


def _require_timezone(value: datetime) -> datetime:
    """
    Reject timezone-naive timestamps.

    A distributed platform can span Azure services, developer workstations,
    build systems and possibly multiple regions.

    A timestamp such as:

        2026-08-07 10:30

    is ambiguous.

    A timestamp such as:

        2026-08-07T10:30:00-04:00

    is not.

    We do NOT force timestamps to UTC at the schema boundary. Keeping the
    original offset can sometimes be useful for evidence. Applications may
    normalize to UTC for storage/querying.
    """

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            "Cross-component timestamps must include timezone information."
        )

    return value


AwareDatetime = Annotated[
    datetime,
    AfterValidator(_require_timezone),
]


class ContractModel(BaseModel):
    """
    Base class for canonical shared contracts.

    Do not loosen `extra="forbid"` merely because a provider sends additional
    data.

    Provider-specific payloads should first be normalized by an adapter such as
    Component 12.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

