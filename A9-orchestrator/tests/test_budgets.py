from datetime import datetime, timezone

import pytest

from ai_engineering_orchestrator.budgets import (
    BudgetManager,
)
from ai_engineering_orchestrator.errors import (
    BudgetExceededError,
)
from ai_engineering_orchestrator.models import (
    ResourceBudget,
    UsageLedger,
)


NOW = datetime.now(timezone.utc)


def test_token_budget_is_enforced() -> None:
    budget = ResourceBudget(
        maximum_total_llm_input_tokens=100,
        maximum_total_llm_output_tokens=100,
        maximum_total_llm_requests=10,
    )

    usage = UsageLedger(
        input_tokens=101,
    )

    with pytest.raises(BudgetExceededError):
        BudgetManager().validate(
            budget=budget,
            usage=usage,
            started_at=NOW,
        )


def test_usage_inside_budget_passes() -> None:
    budget = ResourceBudget(
        maximum_total_llm_input_tokens=1000,
        maximum_total_llm_output_tokens=1000,
        maximum_total_llm_requests=10,
    )

    usage = UsageLedger(
        input_tokens=100,
        output_tokens=50,
        llm_requests=2,
    )

    BudgetManager().validate(
        budget=budget,
        usage=usage,
        started_at=NOW,
    )
