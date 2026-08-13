"""
Cost allocation.

Cost allocation transforms a shared bill into costs attributable to useful
engineering units.

The allocator supports:

    direct work-item assignment
    run-based assignment
    token-share allocation
    equal-share allocation

Production implementations can ingest Azure Cost Management exports, FOCUS
records, model-provider invoices, or internal chargeback records and normalize
them into CostRecord.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .errors import CostAllocationError
from .models import (
    AIUsageRecord,
    CostAllocationMethod,
    CostRecord,
)


@dataclass(frozen=True)
class AllocatedCost:
    work_item_id: str
    amount: float
    source_cost_id: str
    allocation_method: CostAllocationMethod


class CostAllocator:
    """Allocate direct and shared cost records to work items."""

    def allocate(
        self,
        *,
        costs: tuple[CostRecord, ...],
        usage: tuple[AIUsageRecord, ...],
        eligible_work_item_ids: tuple[str, ...],
    ) -> tuple[AllocatedCost, ...]:
        eligible = set(eligible_work_item_ids)

        if not eligible:
            if costs:
                raise CostAllocationError(
                    "Costs exist but no eligible work items were supplied."
                )
            return ()

        usage_by_work_item: dict[str, int] = defaultdict(int)
        work_items_by_run: dict[str, set[str]] = defaultdict(set)

        for record in usage:
            if record.work_item_id not in eligible:
                continue

            usage_by_work_item[record.work_item_id] += (
                record.input_tokens
                + record.output_tokens
            )

            if record.run_id is not None:
                work_items_by_run[record.run_id].add(
                    record.work_item_id
                )

        allocations: list[AllocatedCost] = []

        for cost in costs:
            if cost.work_item_id is not None:
                if cost.work_item_id not in eligible:
                    raise CostAllocationError(
                        f"Cost {cost.cost_id!r} references an unknown "
                        "or ineligible work item."
                    )

                allocations.append(
                    AllocatedCost(
                        work_item_id=cost.work_item_id,
                        amount=cost.amount,
                        source_cost_id=cost.cost_id,
                        allocation_method=CostAllocationMethod.DIRECT,
                    )
                )
                continue

            if cost.run_id is not None:
                run_items = sorted(
                    work_items_by_run.get(cost.run_id, set())
                )

                if not run_items:
                    raise CostAllocationError(
                        f"Cost {cost.cost_id!r} references run "
                        f"{cost.run_id!r}, but no work item maps to that run."
                    )

                share = cost.amount / len(run_items)

                for work_item_id in run_items:
                    allocations.append(
                        AllocatedCost(
                            work_item_id=work_item_id,
                            amount=share,
                            source_cost_id=cost.cost_id,
                            allocation_method=CostAllocationMethod.RUN_SHARE,
                        )
                    )
                continue

            if cost.allocation_method == CostAllocationMethod.TOKEN_SHARE:
                total_tokens = sum(
                    usage_by_work_item.get(item, 0)
                    for item in eligible
                )

                if total_tokens == 0:
                    raise CostAllocationError(
                        f"Cost {cost.cost_id!r} requires token-share "
                        "allocation, but no attributable tokens exist."
                    )

                for work_item_id in sorted(eligible):
                    item_tokens = usage_by_work_item.get(
                        work_item_id,
                        0,
                    )

                    if item_tokens == 0:
                        continue

                    allocations.append(
                        AllocatedCost(
                            work_item_id=work_item_id,
                            amount=(
                                cost.amount
                                * item_tokens
                                / total_tokens
                            ),
                            source_cost_id=cost.cost_id,
                            allocation_method=(
                                CostAllocationMethod.TOKEN_SHARE
                            ),
                        )
                    )
                continue

            if cost.allocation_method == CostAllocationMethod.EQUAL_SHARE:
                share = cost.amount / len(eligible)

                for work_item_id in sorted(eligible):
                    allocations.append(
                        AllocatedCost(
                            work_item_id=work_item_id,
                            amount=share,
                            source_cost_id=cost.cost_id,
                            allocation_method=(
                                CostAllocationMethod.EQUAL_SHARE
                            ),
                        )
                    )
                continue

            raise CostAllocationError(
                f"Cost {cost.cost_id!r} has no supported allocation key. "
                "Supply work_item_id, run_id, TOKEN_SHARE, or EQUAL_SHARE."
            )

        allocated_total = sum(item.amount for item in allocations)
        source_total = sum(item.amount for item in costs)

        if abs(allocated_total - source_total) > 1e-6:
            raise CostAllocationError(
                "Allocated cost does not equal source cost. "
                f"Source={source_total}; allocated={allocated_total}."
            )

        return tuple(allocations)
