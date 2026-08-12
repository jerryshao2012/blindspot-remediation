"""
Canonical AI/resource usage accounting.

WHY SHARE THIS MODEL?
---------------------

Components 2 and 3 PRODUCE usage.

Component 9 ACCUMULATES usage.

Component 4 PRESERVES usage.

Component 5 ANALYZES usage during qualification.

Component 8 calculates ECONOMICS from usage.

Those components therefore need one vocabulary.

Component 8 may have richer cost records internally; those do NOT need to move
into this shared package.
"""

from __future__ import annotations

from pydantic import Field
from typing_extensions import Annotated

from .base import ContractModel


class AIUsage(ContractModel):
    input_tokens: Annotated[
        int,
        Field(ge=0),
    ] = 0

    output_tokens: Annotated[
        int,
        Field(ge=0),
    ] = 0

    cached_input_tokens: Annotated[
        int,
        Field(ge=0),
    ] = 0

    request_count: Annotated[
        int,
        Field(ge=0),
    ] = 0

    def plus(
        self,
        other: "AIUsage",
    ) -> "AIUsage":
        """
        Pure helper used to accumulate usage without mutating evidence objects.
        """

        return AIUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cached_input_tokens=(
                self.cached_input_tokens
                + other.cached_input_tokens
            ),
            request_count=(
                self.request_count
                + other.request_count
            ),
        )


class RunUsageLedger(ContractModel):
    """
    Cumulative resource accounting for one orchestrated engineering run.

    Sandbox execution seconds are included because our earlier analysis showed
    that release gating—especially mutation testing—may incur significant
    non-LLM compute cost.
    """

    ai: AIUsage = Field(
        default_factory=AIUsage
    )

    execution_attempts: Annotated[
        int,
        Field(ge=0),
    ] = 0

    gate_attempts: Annotated[
        int,
        Field(ge=0),
    ] = 0

    more_evidence_cycles: Annotated[
        int,
        Field(ge=0),
    ] = 0

    sandbox_execution_seconds: Annotated[
        float,
        Field(ge=0.0),
    ] = 0.0


class ResourceBudget(ContractModel):
    """
    Hard orchestration ceilings.

    These are controls, not performance targets.

    The budget belongs in the qualified TaskSpecification and is enforced by
    Component 9.

    Components 2 and 3 may additionally have tighter LOCAL limits.
    """

    maximum_execution_attempts: Annotated[
        int,
        Field(ge=1),
    ] = 2

    maximum_gate_attempts: Annotated[
        int,
        Field(ge=1),
    ] = 3

    maximum_more_evidence_cycles: Annotated[
        int,
        Field(ge=0),
    ] = 2

    maximum_llm_input_tokens: Annotated[
        int,
        Field(ge=0),
    ] = 500_000

    maximum_llm_output_tokens: Annotated[
        int,
        Field(ge=0),
    ] = 100_000

    maximum_llm_requests: Annotated[
        int,
        Field(ge=0),
    ] = 200

    maximum_wall_clock_seconds: Annotated[
        int,
        Field(ge=1),
    ] = 7_200

    # Cost ceilings are optional because authoritative cost information may not
    # be available synchronously during every POC run.
    #
    # When configured, currency must also be configured.
    maximum_total_cost: Annotated[
        float | None,
        Field(ge=0.0),
    ] = None

    cost_currency: Annotated[
        str | None,
        Field(min_length=3, max_length=3),
    ] = None

