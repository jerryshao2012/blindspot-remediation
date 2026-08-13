"""
Primary Component 9 service.

The service performs orchestration only.

Notice what is absent:

    OpenAI client
    Azure OpenAI client
    prompt
    model selection logic
    code parser
    compiler
    test generator
    AI judge

Those responsibilities belong elsewhere.

The orchestrator coordinates components through typed ports and deterministic
state transitions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .budgets import BudgetManager
from .errors import (
    BudgetExceededError,
    OrchestratorError,
)
from .models import (
    FinalDisposition,
    GateDisposition,
    OrchestrationRun,
    RunOutcome,
    RunState,
    TaskRequest,
    UsageLedger,
)
from .ports import (
    ChangeExecutionPort,
    EvidencePort,
    ReleaseGatePort,
    ReleasePort,
)
from .registry import TaskDefinitionRegistry
from .state_machine import OrchestrationStateMachine


class EngineeringAutomationOrchestrator:
    """
    Deterministic control plane for one engineering automation task.

    POC workflow:

        validate
        execute change
        gate
        optionally gather another evidence cycle
        release OR reject OR request human review

    Human review is a terminal signal from this component.

    The human does NOT step inside ReleaseGateService.
    """

    def __init__(
        self,
        *,
        registry: TaskDefinitionRegistry,
        change_execution: ChangeExecutionPort,
        release_gate: ReleaseGatePort,
        evidence: EvidencePort,
        release: ReleasePort,
        state_machine: OrchestrationStateMachine | None = None,
        budget_manager: BudgetManager | None = None,
    ) -> None:
        self._registry = registry
        self._change_execution = change_execution
        self._release_gate = release_gate
        self._evidence = evidence
        self._release = release

        self._state_machine = (
            state_machine
            or OrchestrationStateMachine()
        )

        self._budget_manager = (
            budget_manager
            or BudgetManager()
        )

    def run(
        self,
        task: TaskRequest,
    ) -> RunOutcome:
        definition = self._registry.resolve(
            task.task_type
        )

        now = datetime.now(timezone.utc)

        run = OrchestrationRun(
            run_id=f"run-{uuid4()}",
            task=task,
            task_definition_version=definition.definition_version,
            state=RunState.CREATED,
            started_at=now,
            updated_at=now,
        )

        evidence_references: list[str] = []
        reason_codes: list[str] = []

        try:
            run = self._transition_and_record(
                run,
                RunState.VALIDATING,
                "Task definition resolved.",
                evidence_references,
            )

            self._validate_task_against_definition(
                task=task,
                allowed_patterns=definition.allowed_repository_patterns,
            )

            run = self._transition_and_record(
                run,
                RunState.READY,
                "Task validation completed.",
                evidence_references,
            )

            self._budget_manager.validate(
                budget=definition.budget,
                usage=run.usage,
                started_at=run.started_at,
            )

            run = self._transition_and_record(
                run,
                RunState.EXECUTING_CHANGE,
                "Invoking ChangeExecutionService.",
                evidence_references,
            )

            execution_result = self._change_execution.execute(
                run_id=run.run_id,
                task=task,
                definition=definition,
            )

            run = run.model_copy(
                update={
                    "usage": self._add_execution_usage(
                        run.usage,
                        execution_result.input_tokens,
                        execution_result.output_tokens,
                        execution_result.llm_requests,
                    )
                }
            )

            self._budget_manager.validate(
                budget=definition.budget,
                usage=run.usage,
                started_at=run.started_at,
            )

            if not execution_result.succeeded:
                reason_codes.append(
                    execution_result.failure_code
                    or "CHANGE_EXECUTION_FAILED"
                )

                run = self._transition_and_record(
                    run,
                    RunState.CHANGE_FAILED,
                    execution_result.failure_message
                    or "Change execution failed.",
                    evidence_references,
                )

                return self._outcome(
                    run=run,
                    disposition=FinalDisposition.REJECTED,
                    evidence_references=evidence_references,
                    reason_codes=reason_codes,
                )

            candidate = execution_result.candidate

            if candidate is None:
                raise OrchestratorError(
                    "ChangeExecutionService returned success "
                    "without a candidate."
                )

            run = run.model_copy(
                update={"candidate": candidate}
            )

            evidence_references.append(
                candidate.evidence_reference
            )

            run = self._transition_and_record(
                run,
                RunState.CANDIDATE_AVAILABLE,
                "Candidate patch produced.",
                evidence_references,
                evidence_reference=candidate.evidence_reference,
            )

            evidence_cycle = 0

            while True:
                self._budget_manager.validate(
                    budget=definition.budget,
                    usage=run.usage,
                    started_at=run.started_at,
                )

                run = self._transition_and_record(
                    run,
                    RunState.GATING,
                    "Invoking ReleaseGateService.",
                    evidence_references,
                )

                gate_result = self._release_gate.evaluate(
                    run_id=run.run_id,
                    task=task,
                    candidate=candidate,
                    definition=definition,
                    evidence_cycle=evidence_cycle,
                )

                run = run.model_copy(
                    update={
                        "usage": self._add_gate_usage(
                            run.usage,
                            gate_result.input_tokens,
                            gate_result.output_tokens,
                            gate_result.llm_requests,
                        )
                    }
                )

                evidence_references.append(
                    gate_result.evidence_reference
                )

                reason_codes.extend(
                    gate_result.reason_codes
                )

                self._budget_manager.validate(
                    budget=definition.budget,
                    usage=run.usage,
                    started_at=run.started_at,
                )

                if gate_result.disposition == GateDisposition.PASS:
                    run = self._transition_and_record(
                        run,
                        RunState.READY_FOR_RELEASE,
                        "Release gate passed.",
                        evidence_references,
                        evidence_reference=(
                            gate_result.evidence_reference
                        ),
                    )

                    if not definition.automatic_release_allowed:
                        reason_codes.append(
                            "AUTOMATIC_RELEASE_NOT_ALLOWED"
                        )

                        # The gate passed, but policy does not permit the POC
                        # to release autonomously.
                        #
                        # Human review is therefore an external workflow
                        # requirement rather than an activity occurring
                        # inside ReleaseGateService.

                        run = self._state_machine.transition(
                            run,
                            to_state=RunState.PIPELINE_ERROR,
                            reason=(
                                "Gate passed but automatic release is "
                                "disabled for this task definition."
                            ),
                        )

                        evidence_references.append(
                            self._evidence.record_run(run)
                        )

                        return self._outcome(
                            run=run,
                            disposition=(
                                FinalDisposition.PIPELINE_ERROR
                            ),
                            evidence_references=evidence_references,
                            reason_codes=reason_codes,
                        )

                    deployment_reference = self._release.release(
                        run_id=run.run_id,
                        task=task,
                        candidate=candidate,
                    )

                    evidence_references.append(
                        deployment_reference
                    )

                    run = self._transition_and_record(
                        run,
                        RunState.RELEASED,
                        "Candidate released through approved release port.",
                        evidence_references,
                        evidence_reference=deployment_reference,
                    )

                    return self._outcome(
                        run=run,
                        disposition=FinalDisposition.RELEASED,
                        evidence_references=evidence_references,
                        reason_codes=reason_codes,
                    )

                if gate_result.disposition == GateDisposition.FAIL:
                    run = self._transition_and_record(
                        run,
                        RunState.GATE_FAILED,
                        "Release gate rejected candidate.",
                        evidence_references,
                        evidence_reference=(
                            gate_result.evidence_reference
                        ),
                    )

                    return self._outcome(
                        run=run,
                        disposition=FinalDisposition.REJECTED,
                        evidence_references=evidence_references,
                        reason_codes=reason_codes,
                    )

                if (
                    gate_result.disposition
                    == GateDisposition.HUMAN_REVIEW_REQUIRED
                ):
                    run = self._transition_and_record(
                        run,
                        RunState.HUMAN_REVIEW_REQUIRED,
                        (
                            "Release gate requested external "
                            "human review."
                        ),
                        evidence_references,
                        evidence_reference=(
                            gate_result.evidence_reference
                        ),
                    )

                    return self._outcome(
                        run=run,
                        disposition=(
                            FinalDisposition.HUMAN_REVIEW_REQUIRED
                        ),
                        evidence_references=evidence_references,
                        reason_codes=reason_codes,
                    )

                if (
                    gate_result.disposition
                    == GateDisposition.MORE_EVIDENCE_REQUIRED
                ):
                    evidence_cycle += 1

                    if (
                        evidence_cycle
                        > definition.maximum_more_evidence_cycles
                    ):
                        reason_codes.append(
                            "MORE_EVIDENCE_LIMIT_REACHED"
                        )

                        run = self._transition_and_record(
                            run,
                            RunState.HUMAN_REVIEW_REQUIRED,
                            (
                                "Maximum additional-evidence cycles "
                                "were exhausted."
                            ),
                            evidence_references,
                            evidence_reference=(
                                gate_result.evidence_reference
                            ),
                        )

                        return self._outcome(
                            run=run,
                            disposition=(
                                FinalDisposition.HUMAN_REVIEW_REQUIRED
                            ),
                            evidence_references=evidence_references,
                            reason_codes=reason_codes,
                        )

                    run = run.model_copy(
                        update={
                            "usage": run.usage.model_copy(
                                update={
                                    "more_evidence_cycles": (
                                        evidence_cycle
                                    )
                                }
                            )
                        }
                    )

                    run = self._transition_and_record(
                        run,
                        RunState.MORE_EVIDENCE,
                        (
                            "Release gate requested an additional "
                            "evidence cycle."
                        ),
                        evidence_references,
                        evidence_reference=(
                            gate_result.evidence_reference
                        ),
                    )

                    # Component 3 owns evidence planning and evidence
                    # generation coordination.
                    #
                    # Component 9 merely authorizes another bounded gate
                    # cycle. It does not invent tests or evidence itself.

                    continue

                raise OrchestratorError(
                    "ReleaseGateService returned an unknown disposition."
                )

        except BudgetExceededError as exc:
            reason_codes.append("RESOURCE_BUDGET_EXCEEDED")

            if (
                run.state
                not in {
                    RunState.FAILED_VALIDATION,
                    RunState.CHANGE_FAILED,
                    RunState.GATE_FAILED,
                    RunState.HUMAN_REVIEW_REQUIRED,
                    RunState.RELEASED,
                    RunState.BUDGET_EXCEEDED,
                    RunState.PIPELINE_ERROR,
                    RunState.CANCELLED,
                }
            ):
                run = self._state_machine.transition(
                    run,
                    to_state=RunState.BUDGET_EXCEEDED,
                    reason=str(exc),
                )

                evidence_references.append(
                    self._evidence.record_run(run)
                )

            return self._outcome(
                run=run,
                disposition=FinalDisposition.BUDGET_EXCEEDED,
                evidence_references=evidence_references,
                reason_codes=reason_codes,
            )

        except Exception as exc:
            reason_codes.append(
                f"PIPELINE_EXCEPTION:{type(exc).__name__}"
            )

            if (
                run.state
                not in {
                    RunState.FAILED_VALIDATION,
                    RunState.CHANGE_FAILED,
                    RunState.GATE_FAILED,
                    RunState.HUMAN_REVIEW_REQUIRED,
                    RunState.RELEASED,
                    RunState.BUDGET_EXCEEDED,
                    RunState.PIPELINE_ERROR,
                    RunState.CANCELLED,
                }
            ):
                try:
                    run = self._state_machine.transition(
                        run,
                        to_state=RunState.PIPELINE_ERROR,
                        reason=(
                            "Unexpected orchestration failure: "
                            f"{type(exc).__name__}"
                        ),
                    )

                    evidence_references.append(
                        self._evidence.record_run(run)
                    )

                except Exception:
                    # Evidence persistence must never hide the original
                    # orchestration failure.
                    pass

            return self._outcome(
                run=run,
                disposition=FinalDisposition.PIPELINE_ERROR,
                evidence_references=evidence_references,
                reason_codes=reason_codes,
            )

    def _transition_and_record(
        self,
        run: OrchestrationRun,
        state: RunState,
        reason: str,
        evidence_references: list[str],
        evidence_reference: str | None = None,
    ) -> OrchestrationRun:
        updated = self._state_machine.transition(
            run,
            to_state=state,
            reason=reason,
            evidence_reference=evidence_reference,
        )

        persisted_reference = self._evidence.record_run(
            updated
        )

        evidence_references.append(
            persisted_reference
        )

        return updated

    @staticmethod
    def _validate_task_against_definition(
        *,
        task: TaskRequest,
        allowed_patterns: tuple[str, ...],
    ) -> None:
        """
        POC repository allow-list validation.

        Production matching should use canonical repository identities rather
        than naive substring matching.
        """

        if not any(
            pattern in task.repository_uri
            for pattern in allowed_patterns
        ):
            raise OrchestratorError(
                "Repository is not permitted by the task definition."
            )

    @staticmethod
    def _add_execution_usage(
        usage: UsageLedger,
        input_tokens: int,
        output_tokens: int,
        requests: int,
    ) -> UsageLedger:
        return usage.model_copy(
            update={
                "input_tokens": (
                    usage.input_tokens + input_tokens
                ),
                "output_tokens": (
                    usage.output_tokens + output_tokens
                ),
                "llm_requests": (
                    usage.llm_requests + requests
                ),
                "execution_attempts": (
                    usage.execution_attempts + 1
                ),
            }
        )

    @staticmethod
    def _add_gate_usage(
        usage: UsageLedger,
        input_tokens: int,
        output_tokens: int,
        requests: int,
    ) -> UsageLedger:
        return usage.model_copy(
            update={
                "input_tokens": (
                    usage.input_tokens + input_tokens
                ),
                "output_tokens": (
                    usage.output_tokens + output_tokens
                ),
                "llm_requests": (
                    usage.llm_requests + requests
                ),
                "gate_attempts": (
                    usage.gate_attempts + 1
                ),
            }
        )

    def _outcome(
        self,
        *,
        run: OrchestrationRun,
        disposition: FinalDisposition,
        evidence_references: list[str],
        reason_codes: list[str],
    ) -> RunOutcome:
        outcome = RunOutcome(
            run_id=run.run_id,
            task_id=run.task.task_id,
            task_type=run.task.task_type,
            final_state=run.state,
            disposition=disposition,
            candidate_id=(
                run.candidate.candidate_id
                if run.candidate is not None
                else None
            ),
            started_at=run.started_at,
            completed_at=datetime.now(timezone.utc),
            usage=run.usage,
            evidence_references=tuple(
                dict.fromkeys(evidence_references)
            ),
            reason_codes=tuple(
                dict.fromkeys(reason_codes)
            ),
        )

        outcome_reference = self._evidence.record_outcome(
            outcome
        )

        return outcome.model_copy(
            update={
                "evidence_references": (
                    *outcome.evidence_references,
                    outcome_reference,
                )
            }
        )
