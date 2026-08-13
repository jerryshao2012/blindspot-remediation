from datetime import datetime, timezone

from ai_engineering_economics.allocation import (
    CostAllocator,
)
from ai_engineering_economics.models import (
    AIUsageRecord,
    CostAllocationMethod,
    CostCategory,
    CostRecord,
)


NOW = datetime.now(timezone.utc)


def usage(
    identifier: str,
    work_item_id: str,
    tokens: int,
) -> AIUsageRecord:
    return AIUsageRecord(
        usage_id=identifier,
        work_item_id=work_item_id,
        component_name="ChangeExecutionService",
        provider="azure-openai",
        model_name="configured-model",
        input_tokens=tokens,
        output_tokens=0,
        request_count=1,
        timestamp=NOW,
    )


def test_shared_ai_cost_is_allocated_by_token_share() -> None:
    cost = CostRecord(
        cost_id="cost-1",
        category=CostCategory.AI_API,
        amount=300.0,
        incurred_at=NOW,
        allocation_method=CostAllocationMethod.TOKEN_SHARE,
        source="test",
    )

    allocations = CostAllocator().allocate(
        costs=(cost,),
        usage=(
            usage("u1", "task-1", 100),
            usage("u2", "task-2", 200),
        ),
        eligible_work_item_ids=(
            "task-1",
            "task-2",
        ),
    )

    by_task = {
        item.work_item_id: item.amount
        for item in allocations
    }

    assert by_task["task-1"] == 100.0
    assert by_task["task-2"] == 200.0


def test_direct_cost_remains_direct() -> None:
    cost = CostRecord(
        cost_id="cost-1",
        category=CostCategory.COMPUTE,
        amount=12.5,
        incurred_at=NOW,
        work_item_id="task-1",
        source="test",
    )

    allocations = CostAllocator().allocate(
        costs=(cost,),
        usage=(),
        eligible_work_item_ids=("task-1",),
    )

    assert len(allocations) == 1
    assert allocations[0].amount == 12.5
