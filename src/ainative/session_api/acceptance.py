from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ainative.acceptance import StageAcceptanceEvaluator
from ainative.acceptance.confirmation import confirmation_gate
from ainative.model.checklists import (
    CheckOperator,
    CheckResult,
    ExecutionItemResult,
)
from ainative.model.results import (
    ExecutionResult,
    StageResult,
    TaskResult,
    TaskStatus,
)
from ainative.model.task import TaskContract
from ainative.model.workflow import (
    GateResult,
    StageRequest,
    Workflow,
    WorkflowStatus,
)
from ainative.reading import (
    WorkflowIntegrityError,
    validate_workflow_structure,
)

from .skill import AINativeSkill, SkillSession


class WorkflowError(RuntimeError):
    """The Agent supplied a Workflow that cannot be opened for validation."""


_TERMINAL_WORKFLOW_STATUSES = frozenset({
    WorkflowStatus.COMPLETED,
    WorkflowStatus.FAILED,
    WorkflowStatus.INVALID,
    WorkflowStatus.SUPERSEDED,
})


def _reject_unexecutable_revision(workflow: Workflow) -> None:
    """Refuse to open a Workflow revision that is no longer executable.

    @param workflow: the Agent-authored Workflow.
    @throws WorkflowError when the revision already reached a terminal state.
    """

    if workflow.status in _TERMINAL_WORKFLOW_STATUSES:
        raise WorkflowError(
            f"Workflow revision {workflow.revision_id} is not executable "
            f"in status {workflow.status.value}"
        )


@dataclass(slots=True)
class AcceptanceSession:
    """Validation/recording session for an Agent-authored Workflow.

    The Agent executes Tools/MCP directly and submits structured raw results
    through ``record_execution_result``. This class never invokes a Tool or an
    MCP Server itself. It validates structure, records evidence, evaluates each
    Stage deterministically, and aggregates the final result.
    """

    skill: SkillSession
    task: TaskContract
    workflow: Workflow
    gate: GateResult = field(default_factory=lambda: GateResult(True))
    acceptance_evaluator: StageAcceptanceEvaluator = field(default_factory=StageAcceptanceEvaluator)
    state: dict[str, Any] = field(default_factory=dict)
    _call_executions: dict[str, ExecutionResult] = field(default_factory=dict, init=False)
    _task_results: dict[str, TaskResult] = field(default_factory=dict, init=False)
    _execution_item_results: dict[tuple[str, str], ExecutionItemResult] = field(default_factory=dict, init=False)
    _check_results: dict[tuple[str, str], CheckResult] = field(default_factory=dict, init=False)
    _call_locations: dict[str, tuple[str, StageRequest]] = field(default_factory=dict, init=False)
    _completed_stages: list[str] = field(default_factory=list, init=False)
    _stage_results: dict[str, StageResult] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        for step in self.workflow.steps:
            for stage in step.stages:
                for call in stage.calls:
                    self._call_locations[call.call_id] = (step.step_id, stage)

    @property
    def ready(self) -> bool:
        return self.gate.ready

    @property
    def completed_call_ids(self) -> tuple[str, ...]:
        return tuple(self._call_executions)

    @property
    def completed_stage_ids(self) -> tuple[str, ...]:
        return tuple(self._completed_stages)

    @property
    def completed_step_ids(self) -> tuple[str, ...]:
        completed = set(self._completed_stages)
        return tuple(
            step.step_id
            for step in self.workflow.steps
            if all(stage.stage_id in completed for stage in step.stages)
        )

    @property
    def stage_results(self) -> tuple[StageResult, ...]:
        return tuple(self._stage_results.values())

    # -- Evidence recording (Agent submits results; Python validates) --

    def record_execution_item(self, stage_id: str, result: ExecutionItemResult) -> ExecutionItemResult:
        stage = self._stage(stage_id)
        item = next((item for item in stage.execution_checklist if item.item_id == result.item_id), None)
        if item is None:
            raise WorkflowError(f"Execution checklist item is not declared in {stage_id}: {result.item_id}")
        if item.call_ids:
            raise WorkflowError(
                f"Execution checklist item {result.item_id} is derived from ExecutionResults and cannot be overridden"
            )
        self._execution_item_results[(stage_id, result.item_id)] = result
        self._invalidate_stage_result(stage_id)
        return result

    def record_check_result(self, stage_id: str, result: CheckResult) -> CheckResult:
        stage = self._stage(stage_id)
        check = next((check for check in stage.acceptance_checklist if check.check_id == result.check_id), None)
        if check is None:
            raise WorkflowError(f"Acceptance check is not declared in {stage_id}: {result.check_id}")
        if check.operator is not CheckOperator.MANUAL:
            raise WorkflowError(
                f"Acceptance check {result.check_id} uses deterministic operator {check.operator.value} and cannot be overridden"
            )
        self._check_results[(stage_id, result.check_id)] = result
        self._invalidate_stage_result(stage_id)
        return result

    def check_call_ready(self, call_id: str) -> None:
        """Fail closed when an Agent tries to run a call before its dependencies."""

        location = self._call_locations.get(call_id)
        if location is None:
            raise WorkflowError(f"Call is not declared in the Workflow: {call_id}")
        step_id, stage = location
        step = next(step for step in self.workflow.steps if step.step_id == step_id)
        call = next(call for call in stage.calls if call.call_id == call_id)
        missing: list[str] = []
        failed: list[str] = []
        missing_steps = set(step.depends_on) - set(self.completed_step_ids)
        if missing_steps:
            missing.append("step:" + ",step:".join(sorted(missing_steps)))
        missing_stages = set(stage.depends_on) - set(self._completed_stages)
        if missing_stages:
            missing.append("stage:" + ",stage:".join(sorted(missing_stages)))
        for dependency in call.depends_on:
            dependency_result = self._call_executions.get(dependency)
            if dependency_result is None:
                missing.append(dependency)
            elif dependency_result.status not in {TaskStatus.SUCCEEDED, TaskStatus.DEGRADED}:
                failed.append(dependency)
        if missing or failed:
            reasons = []
            if missing:
                reasons.append("incomplete dependencies: " + ", ".join(missing))
            if failed:
                reasons.append("failed dependencies: " + ", ".join(failed))
            raise WorkflowError(f"Call {call_id} cannot execute; " + "; ".join(reasons))

    def record_execution_result(self, result: ExecutionResult) -> ExecutionResult:
        """Record a raw Tool result returned by the Agent's tool client.

        This is the only execution entry point of this Session. Python never
        invokes the Tool; it validates the submitted contract, target,
        dependency order, and shape, then records it as evidence for the Stage.
        """
        location = self._call_locations.get(result.call_id)
        if location is None:
            raise WorkflowError(f"Execution result references an undeclared call: {result.call_id}")
        if result.call_id in self._call_executions:
            raise WorkflowError(f"Execution result has already been recorded: {result.call_id}")
        _, stage = location
        call = next(call for call in stage.calls if call.call_id == result.call_id)
        self.check_call_ready(result.call_id)
        if result.target is not None and result.target != call.target:
            raise WorkflowError(
                f"Execution result target mismatch for {result.call_id}: "
                f"declared {call.qualified_name}, got {result.target.owner}/{result.target.name}"
            )
        if not isinstance(result.outputs, dict):
            raise WorkflowError(f"Execution result outputs must be an object: {result.call_id}")
        task_result = TaskResult(
            status=result.status,
            route=self.workflow.route.value,
            guidance=self.workflow.guidance,
            workflow_id=self.workflow.workflow_id,
            workflow_revision=self.workflow.revision,
            details=dict(result.outputs),
            artifacts=result.artifacts,
            warnings=result.warnings,
            errors=result.errors,
            resume_pointer=result.resume_pointer,
            preserved_relations=frozenset(result.preserved_relations),
            lost_relations=frozenset(result.lost_relations),
        )
        self._call_executions[result.call_id] = result
        self._task_results[result.call_id] = task_result
        self.state.setdefault("recorded_execution_results", {})[result.call_id] = result.to_dict()
        self._invalidate_stage_result(stage.stage_id)
        return result

    # -- Stage / Workflow evaluation --

    def complete_stage(self, stage_id: str) -> StageResult:
        if stage_id in self._stage_results:
            return self._stage_results[stage_id]
        step_id, stage = self._stage_location(stage_id)
        step = next(step for step in self.workflow.steps if step.step_id == step_id)

        missing_step_dependencies = set(step.depends_on) - set(self.completed_step_ids)
        if missing_step_dependencies:
            return StageResult(
                stage_id=stage_id,
                step_id=step_id,
                status=TaskStatus.BLOCKED,
                errors=(
                    (
                        f"Stage {stage_id} belongs to Step {step_id}, which depends on incomplete Steps: "
                        f"{', '.join(sorted(missing_step_dependencies))}"
                    ),
                ),
                resume_pointer=stage_id,
            )

        missing_stage_dependencies = set(stage.depends_on) - set(self._completed_stages)
        if missing_stage_dependencies:
            return StageResult(
                stage_id=stage_id,
                step_id=step_id,
                status=TaskStatus.BLOCKED,
                errors=(
                    (
                        f"Stage {stage_id} depends on incomplete Stages: "
                        f"{', '.join(sorted(missing_stage_dependencies))}"
                    ),
                ),
                resume_pointer=stage_id,
            )

        execution_results = tuple(
            self._call_executions[call.call_id]
            for call in stage.calls
            if call.call_id in self._call_executions
        )
        explicit_execution = tuple(
            result
            for (result_stage_id, _), result in self._execution_item_results.items()
            if result_stage_id == stage_id
        )
        explicit_checks = tuple(
            result
            for (result_stage_id, _), result in self._check_results.items()
            if result_stage_id == stage_id
        )
        acceptance = self.acceptance_evaluator.evaluate(
            stage,
            execution_results,
            explicit_execution,
            explicit_checks,
        )

        outputs: dict[str, Any] = {}
        artifacts = []
        warnings: list[str] = list(acceptance.warnings)
        errors: list[str] = list(acceptance.errors)
        resume_pointer = acceptance.resume_pointer
        for execution_result in execution_results:
            outputs.update(execution_result.outputs)
            artifacts.extend(execution_result.artifacts)
            warnings.extend(execution_result.warnings)
            errors.extend(execution_result.errors)
            if execution_result.status not in {TaskStatus.SUCCEEDED, TaskStatus.DEGRADED}:
                resume_pointer = execution_result.resume_pointer or resume_pointer or stage_id

        result = StageResult(
            stage_id=stage_id,
            step_id=step_id,
            status=acceptance.status,
            execution_results=execution_results,
            execution_item_results=acceptance.execution_results,
            check_results=acceptance.check_results,
            execution_summary=acceptance.execution_summary,
            acceptance_summary=acceptance.acceptance_summary,
            outputs=outputs,
            artifacts=tuple(artifacts),
            warnings=tuple(warnings),
            errors=tuple(errors),
            resume_pointer=resume_pointer,
        )
        self._stage_results[stage_id] = result
        if result.status in {TaskStatus.SUCCEEDED, TaskStatus.DEGRADED}:
            self._completed_stages.append(stage_id)
        return result

    def _stage_location(self, stage_id: str) -> tuple[str, StageRequest]:
        located = next(
            (
                (step.step_id, stage)
                for step in self.workflow.steps
                for stage in step.stages
                if stage.stage_id == stage_id
            ),
            None,
        )
        if located is None:
            raise WorkflowError(f"Stage is not present in the Agent-authored Workflow: {stage_id}")
        return located

    def _stage(self, stage_id: str) -> StageRequest:
        return self._stage_location(stage_id)[1]

    def _invalidate_stage_result(self, stage_id: str) -> None:
        self._stage_results.pop(stage_id, None)
        if stage_id in self._completed_stages:
            self._completed_stages.remove(stage_id)

    def finish(self) -> TaskResult:
        """Aggregate recorded Tool/Stage results; execute nothing."""

        required_stages = {stage.stage_id for stage in self.workflow.stage_requests if stage.required}
        completed = set(self._completed_stages)
        stage_statuses = {result.status for result in self._stage_results.values()}
        if not self.gate.ready:
            status = TaskStatus.BLOCKED
            workflow_status = WorkflowStatus.SUSPENDED
        elif TaskStatus.NEEDS_APPROVAL in stage_statuses:
            status = TaskStatus.NEEDS_APPROVAL
            workflow_status = WorkflowStatus.SUSPENDED
        elif TaskStatus.FAILED in stage_statuses:
            status = TaskStatus.FAILED
            workflow_status = WorkflowStatus.SUSPENDED
        elif TaskStatus.BLOCKED in stage_statuses:
            status = TaskStatus.BLOCKED
            workflow_status = WorkflowStatus.SUSPENDED
        elif required_stages - completed:
            status = TaskStatus.BLOCKED
            workflow_status = WorkflowStatus.RUNNING
        elif TaskStatus.DEGRADED in stage_statuses:
            status = TaskStatus.DEGRADED
            workflow_status = WorkflowStatus.COMPLETED
        else:
            status = TaskStatus.SUCCEEDED
            workflow_status = WorkflowStatus.COMPLETED

        artifacts = []
        warnings: list[str] = []
        errors: list[str] = list(self.gate.blocked_reasons)
        preserved_relations: set[str] = set()
        lost_relations: set[str] = set()
        resume_pointer = self.workflow.recovery_pointer
        for stage_result in self._stage_results.values():
            if stage_result.status not in {TaskStatus.SUCCEEDED, TaskStatus.DEGRADED}:
                resume_pointer = stage_result.resume_pointer or stage_result.stage_id
                break
        for task_result in self._task_results.values():
            preserved_relations.update(task_result.preserved_relations)
            lost_relations.update(task_result.lost_relations)
        for result in self._stage_results.values():
            artifacts.extend(result.artifacts)
            warnings.extend(result.warnings)
            errors.extend(result.errors)
        details = dict(self.state)
        details["agent_execution"] = {
            "completed_calls": list(self.completed_call_ids),
            "completed_stages": list(self.completed_stage_ids),
        }
        return TaskResult(
            status=status,
            route=self.workflow.route.value,
            guidance=self.workflow.guidance,
            workflow_id=self.workflow.workflow_id,
            workflow_revision=self.workflow.revision,
            workflow_revision_id=self.workflow.revision_id,
            workflow_status=workflow_status.value,
            supersedes_workflow_id=self.workflow.supersedes_workflow_id,
            preserved_relations=frozenset(preserved_relations),
            lost_relations=frozenset(lost_relations),
            stages_completed=tuple(self._completed_stages),
            steps_completed=self.completed_step_ids,
            stage_results=tuple(self._stage_results.values()),
            artifacts=tuple(artifacts),
            details=details,
            warnings=tuple(warnings),
            errors=tuple(errors),
            resume_pointer=resume_pointer,
            next_action=(
                "Agent should repair the Workflow or entry gate before executing"
                if status is TaskStatus.BLOCKED and not self.gate.ready
                else (
                    "Agent should collect missing checklist evidence before continuing"
                    if status is TaskStatus.BLOCKED
                    else (
                        "Agent should obtain the required human decision"
                        if status is TaskStatus.NEEDS_APPROVAL
                        else (
                            "Agent should retry the selected Tool or author a new Workflow revision"
                            if status is TaskStatus.FAILED
                            else None
                        )
                    )
                )
            ),
        )


class AcceptanceGuide:
    """Loads Skill guidance and opens a validation-only AcceptanceSession."""

    def __init__(self, skill: AINativeSkill | None = None) -> None:
        self.skill = skill or AINativeSkill()

    def load_skill(self, task: TaskContract) -> SkillSession:
        return self.skill.load(task)

    def start(
        self,
        task: TaskContract,
        workflow: Workflow,
    ) -> AcceptanceSession:
        """Open an Agent-authored Workflow for structured validation and recording.

        @param task: the Agent-authored task contract.
        @param workflow: the Agent-authored Workflow, already deserialized.
        @returns a session ready to record evidence and evaluate Stages.
        @throws WorkflowError when the Workflow cannot be opened.
        """

        skill_session = self.load_skill(task)
        _reject_unexecutable_revision(workflow)
        if workflow.route is not task.route:
            raise WorkflowError(
                f"workflow route {workflow.route.value} does not match task route {task.route.value}"
            )
        try:
            validate_workflow_structure(workflow)
        except WorkflowIntegrityError as exc:
            raise WorkflowError(str(exc)) from exc
        gate = confirmation_gate(task)
        return AcceptanceSession(
            skill=skill_session,
            task=task,
            workflow=workflow,
            gate=gate,
        )
