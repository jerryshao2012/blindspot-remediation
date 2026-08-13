"""
Resource-budget enforcement.

Token budgets belong at the orchestration level because Components 2 and 3 may
each behave correctly locally while their combined retries produce an
economically or operationally unreasonable run.

Budget enforcement is deterministic.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .errors import BudgetExceededError
from .models import (
    ResourceBudget,
    UsageLedger,
)


class BudgetManager:
    """Validate cumulative resource consumption."""

    def validate(
        self,
        *,
        budget: ResourceBudget,
        usage: UsageLedger,
        started_at: datetime,
    ) -> None:
        if (
            usage.execution_attempts
            > budget.maximum_execution_attempts
        ):
            raise BudgetExceededError(
                "Maximum change-execution attempts exceeded."
            )

        if (
            usage.gate_attempts
            > budget.maximum_gate_attempts
        ):
            raise BudgetExceededError(
                "Maximum release-gate attempts exceeded."
            )

        if (
            usage.input_tokens
            > budget.maximum_total_llm_input_tokens
        ):
            raise BudgetExceededError(
                "Maximum LLM input-token budget exceeded."
            )

        if (
            usage.output_tokens
            > budget.maximum_total_llm_output_tokens
        ):
            raise BudgetExceededError(
                "Maximum LLM output-token budget exceeded."
            )

        if (
            usage.llm_requests
            > budget.maximum_total_llm_requests
        ):
            raise BudgetExceededError(
                "Maximum LLM request budget exceeded."
            )

        elapsed = (
            datetime.now(timezone.utc) - started_at
        ).total_seconds()

        if elapsed > budget.maximum_elapsed_seconds:
            raise BudgetExceededError(
                "Maximum orchestration elapsed-time budget exceeded."
            )
