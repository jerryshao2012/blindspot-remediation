"""
Attribution assessment.

This module is intentionally conservative.

A deployment identifier gives us correlation.

A before/after comparison gives us somewhat more information.

A concurrent control gives us stronger evidence.

Randomization can provide stronger causal identification when the experiment
is correctly designed.

Component 7 does not pretend these designs are equivalent.
"""

from __future__ import annotations

from .models import (
    AttributionAssessment,
    AttributionDesign,
    AttributionStrength,
    KPIObservation,
)
from .statistics import safe_relative_difference


class AttributionAssessor:
    """Create an explicit statement about the strength of outcome evidence."""

    def assess_association(
        self,
        *,
        deployment_id: str,
        treatment: KPIObservation,
        confidence_level: float = 0.95,
    ) -> AttributionAssessment:
        return AttributionAssessment(
            deployment_id=deployment_id,
            metric_name=treatment.metric_name,
            design=AttributionDesign.ASSOCIATION,
            strength=AttributionStrength.DESCRIPTIVE_ONLY,
            baseline_value=None,
            treatment_value=treatment.value,
            absolute_difference=None,
            relative_difference=None,
            baseline_sample_size=None,
            treatment_sample_size=treatment.sample_size,
            confidence_level=confidence_level,
            notes=(
                "The KPI was observed in association with the deployment.",
                "No comparison group or baseline was supplied.",
                "No causal conclusion should be drawn.",
            ),
        )

    def assess_before_after(
        self,
        *,
        deployment_id: str,
        baseline: KPIObservation,
        treatment: KPIObservation,
        confidence_level: float = 0.95,
    ) -> AttributionAssessment:
        self._validate_comparable(
            baseline=baseline,
            treatment=treatment,
        )

        absolute_difference = (
            treatment.value - baseline.value
        )

        relative_difference = safe_relative_difference(
            baseline=baseline.value,
            treatment=treatment.value,
        )

        return AttributionAssessment(
            deployment_id=deployment_id,
            metric_name=treatment.metric_name,
            design=AttributionDesign.BEFORE_AFTER,
            strength=AttributionStrength.WEAK,
            baseline_value=baseline.value,
            treatment_value=treatment.value,
            absolute_difference=absolute_difference,
            relative_difference=relative_difference,
            baseline_sample_size=baseline.sample_size,
            treatment_sample_size=treatment.sample_size,
            confidence_level=confidence_level,
            notes=(
                "A historical before/after comparison was performed.",
                "Temporal confounding remains possible.",
                "Workload, seasonality, policy, dependency, and population "
                "changes may explain part or all of the difference.",
                "Treat this as evidence of association, not proof of causality.",
            ),
        )

    def assess_concurrent_control(
        self,
        *,
        deployment_id: str,
        control: KPIObservation,
        treatment: KPIObservation,
        confidence_level: float = 0.95,
    ) -> AttributionAssessment:
        self._validate_comparable(
            baseline=control,
            treatment=treatment,
        )

        absolute_difference = (
            treatment.value - control.value
        )

        relative_difference = safe_relative_difference(
            baseline=control.value,
            treatment=treatment.value,
        )

        return AttributionAssessment(
            deployment_id=deployment_id,
            metric_name=treatment.metric_name,
            design=AttributionDesign.CONCURRENT_CONTROL,
            strength=AttributionStrength.MODERATE,
            baseline_value=control.value,
            treatment_value=treatment.value,
            absolute_difference=absolute_difference,
            relative_difference=relative_difference,
            baseline_sample_size=control.sample_size,
            treatment_sample_size=treatment.sample_size,
            confidence_level=confidence_level,
            notes=(
                "A contemporaneous comparison group was supplied.",
                "This is stronger than a historical before/after comparison.",
                "Selection bias or other group differences may remain.",
                "Strong causal language requires a defensible assignment design.",
            ),
        )

    def assess_randomized(
        self,
        *,
        deployment_id: str,
        control: KPIObservation,
        treatment: KPIObservation,
        confidence_level: float = 0.95,
    ) -> AttributionAssessment:
        self._validate_comparable(
            baseline=control,
            treatment=treatment,
        )

        absolute_difference = (
            treatment.value - control.value
        )

        relative_difference = safe_relative_difference(
            baseline=control.value,
            treatment=treatment.value,
        )

        return AttributionAssessment(
            deployment_id=deployment_id,
            metric_name=treatment.metric_name,
            design=AttributionDesign.RANDOMIZED,
            strength=AttributionStrength.STRONG,
            baseline_value=control.value,
            treatment_value=treatment.value,
            absolute_difference=absolute_difference,
            relative_difference=relative_difference,
            baseline_sample_size=control.sample_size,
            treatment_sample_size=treatment.sample_size,
            confidence_level=confidence_level,
            notes=(
                "The caller declared randomized assignment.",
                "Randomization can support stronger causal interpretation.",
                "This class does not verify that randomization was correctly "
                "implemented or that the experiment was free of interference, "
                "attrition, instrumentation bias, or other design failures.",
            ),
        )

    @staticmethod
    def _validate_comparable(
        *,
        baseline: KPIObservation,
        treatment: KPIObservation,
    ) -> None:
        if baseline.metric_name != treatment.metric_name:
            raise ValueError(
                "KPI metric names differ."
            )

        if baseline.metric_version != treatment.metric_version:
            raise ValueError(
                "KPI metric versions differ."
            )

        if baseline.unit != treatment.unit:
            raise ValueError(
                "KPI units differ."
            )

        if baseline.metric_type != treatment.metric_type:
            raise ValueError(
                "KPI metric types differ."
            )
