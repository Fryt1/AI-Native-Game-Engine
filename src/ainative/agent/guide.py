from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ainative.orchestration import RuntimeContext
from ainative.orchestration.acceptance import StageAcceptanceEvaluator
from ainative.orchestration.contracts.checklists import (
    CheckOperator,
    CheckResult,
    ExecutionItemResult,
)
from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.orchestration.contracts.plan import (
    ExecutionPlan,
    GateResult,
    StageRequest,
    WorkflowPlanStatus,
)
from ainative.orchestration.contracts.results import (
    ExecutionResult,
    StageResult,
    TaskResult,
    TaskStatus,
)
from ainative.orchestration.contracts.task import TaskContract
from ainative.orchestration.contracts.tools import McpCall, ToolCall
from ainative.orchestration.planning import (
    PlanIntegrityError,
    ToolPlanIssue,
    check_workflow_tools,
    validate_plan_structure,
)
from ainative.orchestration.route_guards import ROUTE_AUTHORITIES
from ainative.registry import ToolResolutionError, ToolsetRegistry

from .intent import IntentInterpreter
from .skill import AINativeWorkflowSkill, SkillSession


class WorkflowPlanError(RuntimeError):
    """The Agent supplied a plan that cannot be opened for validation."""


@dataclass(slots=True)
class WorkflowSession:
    """Validation/recording session for an Agent-authored WorkflowPlan.

    The Agent executes Tools/MCP directly and submits structured raw results
    through ``record_execution_result``. This class never invokes a Tool or an
    MCP Server itself. It validates structure, records evidence, evaluates each
    Stage deterministically, and aggregates the final WorkflowResult.
    """

    skill: SkillSession
    task: TaskContract
    plan: ExecutionPlan
    runtime: RuntimeContext
    registry: ToolsetRegistry
    manifest: TransferManifest | None = None
    gate: GateResult = field(default_factory=lambda: GateResult(True))
    tool_issues: tuple[ToolPlanIssue, ...] = ()
    acceptance_evaluator: StageAcceptanceEvaluator = field(default_factory=StageAcceptanceEvaluator)
    state: dict[str, Any] = field(default_factory=dict)
    _call_executions: dict[str, ExecutionResult] = field(default_factory=dict, init=False)
    _task_results: dict[str, TaskResult] = field(default_factory=dict, init=False)
    _execution_item_results: dict[tuple[str, str], ExecutionItemResult] = field(default_factory=dict, init=False)
    _check_results: dict[tuple[str, str], CheckResult] = field(default_factory=dict, init=False)
    _call_locations: dict[str, tuple[str, StageRequest]] = field(default_factory=dict, init=False)
    _tool_definitions: dict[str, Any] = field(default_factory=dict, init=False)
    _completed_stages: list[str] = field(default_factory=list, init=False)
    _stage_results: dict[str, StageResult] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        for step in self.plan.workflow.steps:
            for stage in step.stages:
                for call in stage.calls:
                    self._call_locations[call.call_id] = (step.step_id, stage)
                    if isinstance(call, ToolCall):
                        try:
                            self._tool_definitions[call.call_id] = self.registry.describe_tool(call.toolset_id, call.tool_id)
                        except ToolResolutionError:
                            # Invalid plan tools are already represented by
                            # ``tool_issues``; keep their blocked result recordable.
                            pass

    @property
    def ready(self) -> bool:
        return not self.tool_issues and self.gate.ready

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
            for step in self.plan.workflow.steps
            if all(stage.stage_id in completed for stage in step.stages)
        )

    @property
    def stage_results(self) -> tuple[StageResult, ...]:
        return tuple(self._stage_results.values())

    # -- Toolset discovery remains read-only and available to the Agent. --

    def list_toolsets(self):
        return self.registry.list_toolsets()

    def describe_toolset(self, toolset_id: str):
        return self.registry.describe_toolset(toolset_id)

    def list_tools(self, toolset_id: str):
        return self.registry.list_tools(toolset_id)

    def search_tools(self, toolset_id: str, query: str):
        return self.registry.search_tools(toolset_id, query)

    # -- Evidence recording (Agent submits results; Python validates) --

    def record_execution_item(self, stage_id: str, result: ExecutionItemResult) -> ExecutionItemResult:
        stage = self._stage(stage_id)
        item = next((item for item in stage.execution_checklist if item.item_id == result.item_id), None)
        if item is None:
            raise WorkflowPlanError(f"Execution checklist item is not declared in {stage_id}: {result.item_id}")
        if item.call_ids:
            raise WorkflowPlanError(
                f"Execution checklist item {result.item_id} is derived from ExecutionResults and cannot be overridden"
            )
        self._execution_item_results[(stage_id, result.item_id)] = result
        self._invalidate_stage_result(stage_id)
        return result

    def record_check_result(self, stage_id: str, result: CheckResult) -> CheckResult:
        stage = self._stage(stage_id)
        check = next((check for check in stage.acceptance_checklist if check.check_id == result.check_id), None)
        if check is None:
            raise WorkflowPlanError(f"Acceptance check is not declared in {stage_id}: {result.check_id}")
        if check.operator is not CheckOperator.MANUAL:
            raise WorkflowPlanError(
                f"Acceptance check {result.check_id} uses deterministic operator {check.operator.value} and cannot be overridden"
            )
        self._check_results[(stage_id, result.check_id)] = result
        self._invalidate_stage_result(stage_id)
        return result

    def check_call_ready(self, call_id: str) -> None:
        """Fail closed when an Agent tries to run a call before its dependencies."""

        location = self._call_locations.get(call_id)
        if location is None:
            raise WorkflowPlanError(f"Call is not declared in the WorkflowPlan: {call_id}")
        step_id, stage = location
        step = next(step for step in self.plan.workflow.steps if step.step_id == step_id)
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
            raise WorkflowPlanError(f"Call {call_id} cannot execute; " + "; ".join(reasons))

    def record_execution_result(self, result: ExecutionResult) -> ExecutionResult:
        """Record a raw Tool/MCP result returned by the Agent's tool client.

        This is the only execution entry point of this Session. Python never
        invokes the Tool or MCP Server; it validates the submitted contract,
        target, dependency order, and shape, then records it as evidence for the
        Stage.
        """
        location = self._call_locations.get(result.call_id)
        if location is None:
            raise WorkflowPlanError(f"Execution result references an undeclared call: {result.call_id}")
        if result.call_id in self._call_executions:
            raise WorkflowPlanError(f"Execution result has already been recorded: {result.call_id}")
        _, stage = location
        call = next(call for call in stage.calls if call.call_id == result.call_id)
        self.check_call_ready(result.call_id)
        expected_kind = "mcp" if isinstance(call, McpCall) else "tool"
        if result.kind != expected_kind:
            raise WorkflowPlanError(
                f"Execution result kind mismatch for {result.call_id}: expected {expected_kind}, got {result.kind}"
            )
        if isinstance(call, McpCall):
            if result.server_id != call.server_id or result.tool_name != call.tool_name:
                raise WorkflowPlanError(f"MCP target mismatch for {result.call_id}")
        elif result.toolset_id != call.toolset_id or result.tool_id != call.tool_id:
            raise WorkflowPlanError(f"Project Tool target mismatch for {result.call_id}")
        if not isinstance(result.outputs, dict):
            raise WorkflowPlanError(f"Execution result outputs must be an object: {result.call_id}")
        if isinstance(call, ToolCall) and not any(issue.call_id == call.call_id for issue in self.tool_issues):
            try:
                self.registry.validate_output(call, result.outputs, self._tool_definitions.get(call.call_id))
            except ToolResolutionError as exc:
                raise WorkflowPlanError(str(exc)) from exc
        task_result = TaskResult(
            status=result.status,
            route=self.plan.route.value,
            workflow_id=self.plan.workflow_id,
            plan_id=self.plan.plan_id,
            plan_revision=self.plan.revision,
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
        step = next(step for step in self.plan.workflow.steps if step.step_id == step_id)

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
                for step in self.plan.workflow.steps
                for stage in step.stages
                if stage.stage_id == stage_id
            ),
            None,
        )
        if located is None:
            raise WorkflowPlanError(f"Stage is not present in the Agent-authored WorkflowPlan: {stage_id}")
        return located

    def _stage(self, stage_id: str) -> StageRequest:
        return self._stage_location(stage_id)[1]

    def _invalidate_stage_result(self, stage_id: str) -> None:
        self._stage_results.pop(stage_id, None)
        if stage_id in self._completed_stages:
            self._completed_stages.remove(stage_id)

    def finish(self) -> TaskResult:
        """Aggregate recorded Tool/Stage results; execute nothing."""

        required_stages = {stage.stage_id for stage in self.plan.workflow.stage_requests if stage.required}
        completed = set(self._completed_stages)
        stage_statuses = {result.status for result in self._stage_results.values()}
        if self.tool_issues:
            status = TaskStatus.BLOCKED
            plan_status = WorkflowPlanStatus.INVALID
        elif not self.gate.ready:
            status = TaskStatus.BLOCKED
            plan_status = WorkflowPlanStatus.SUSPENDED
        elif TaskStatus.NEEDS_APPROVAL in stage_statuses:
            status = TaskStatus.NEEDS_APPROVAL
            plan_status = WorkflowPlanStatus.SUSPENDED
        elif TaskStatus.FAILED in stage_statuses:
            status = TaskStatus.FAILED
            plan_status = WorkflowPlanStatus.SUSPENDED
        elif TaskStatus.BLOCKED in stage_statuses:
            status = TaskStatus.BLOCKED
            plan_status = WorkflowPlanStatus.SUSPENDED
        elif required_stages - completed:
            status = TaskStatus.BLOCKED
            plan_status = WorkflowPlanStatus.RUNNING
        elif TaskStatus.DEGRADED in stage_statuses:
            status = TaskStatus.DEGRADED
            plan_status = WorkflowPlanStatus.COMPLETED
        else:
            status = TaskStatus.SUCCEEDED
            plan_status = WorkflowPlanStatus.COMPLETED

        artifacts = []
        warnings: list[str] = []
        errors: list[str] = [issue.message for issue in self.tool_issues] + list(self.gate.blocked_reasons)
        preserved_relations: set[str] = set()
        lost_relations: set[str] = set()
        resume_pointer = self.plan.recovery_pointer
        for stage_result in self._stage_results.values():
            if stage_result.status not in {TaskStatus.SUCCEEDED, TaskStatus.DEGRADED}:
                resume_pointer = stage_result.resume_pointer or stage_result.stage_id
                break
        if self.tool_issues:
            resume_pointer = self.tool_issues[0].call_id or resume_pointer
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
        if self.tool_issues:
            details["tool_issues"] = [issue.to_dict() for issue in self.tool_issues]
        return TaskResult(
            status=status,
            route=self.plan.route.value,
            workflow_id=self.plan.workflow_id,
            profile=self.plan.profile,
            authority_id=self.plan.authority_id,
            plan_id=self.plan.plan_id,
            plan_revision=self.plan.revision,
            plan_revision_id=self.plan.revision_id,
            plan_status=plan_status.value,
            supersedes_plan_id=self.plan.supersedes_plan_id,
            backend=self.plan.transfer_backend.value if self.plan.transfer_backend else None,
            call_surface=self.plan.host_call_surface or (self.plan.blender_call_surface.value if self.plan.blender_call_surface else None),
            modification_method=self.plan.modification_method,
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
                "Agent should repair the selected Tool/MCP calls or entry gate before executing"
                if status is TaskStatus.BLOCKED and (self.tool_issues or not self.gate.ready)
                else (
                    "Agent should collect missing checklist evidence before continuing"
                    if status is TaskStatus.BLOCKED
                    else (
                        "Agent should obtain the required human decision"
                        if status is TaskStatus.NEEDS_APPROVAL
                        else (
                            "Agent should retry the selected Tool or author a new plan revision"
                            if status is TaskStatus.FAILED
                            else None
                        )
                    )
                )
            ),
        )


class WorkflowGuide:
    """Loads Skill guidance and opens a validation-only WorkflowSession."""

    def __init__(self, skill: AINativeWorkflowSkill | None = None, interpreter: IntentInterpreter | None = None) -> None:
        self.skill = skill or AINativeWorkflowSkill()
        self.interpreter = interpreter

    def load_skill(self, task: TaskContract) -> SkillSession:
        return self.skill.load(task)

    def start(
        self,
        task: TaskContract,
        plan: ExecutionPlan,
        runtime: RuntimeContext,
        manifest: TransferManifest | None = None,
    ) -> WorkflowSession:
        """Open an Agent-authored plan for structured validation and recording."""
        skill_session = self.load_skill(task)
        self._validate_plan_matches_selection(task, plan, skill_session)
        try:
            validate_plan_structure(plan)
        except PlanIntegrityError as exc:
            raise WorkflowPlanError(str(exc)) from exc
        registry = runtime.tool_registry()
        tool_issues = check_workflow_tools(plan, registry)
        authority = ROUTE_AUTHORITIES.get(plan.route)
        if authority is None:
            raise WorkflowPlanError(f"No Route authority is registered for: {plan.route.value}")
        gate = authority.check_preconditions(task, plan, runtime)
        return WorkflowSession(
            skill=skill_session,
            task=task,
            plan=plan,
            runtime=runtime,
            registry=registry,
            manifest=manifest,
            gate=gate,
            tool_issues=tool_issues,
        )

    def task_from_prompt(self, prompt: str, task_id: str) -> TaskContract:
        if self.interpreter is None:
            raise WorkflowPlanError(
                "No Agent-owned IntentInterpreter is configured; construct TaskContract explicitly "
                "or inject an Agent/LLM interpreter"
            )
        return self.interpreter.interpret(prompt, task_id)

    @staticmethod
    def _validate_plan_matches_selection(task: TaskContract, plan: ExecutionPlan, session: SkillSession) -> None:
        mismatches: list[str] = []
        selection = session.selection
        if plan.route is not task.route:
            mismatches.append(f"plan route {plan.route.value} does not match task route {task.route.value}")
        if plan.workflow_id != selection.workflow_id:
            mismatches.append(f"plan workflow {plan.workflow_id} does not match selected Workflow {selection.workflow_id}")
        if plan.profile != selection.profile:
            mismatches.append(f"plan profile {plan.profile} does not match selected profile {selection.profile}")
        if plan.authority_id != selection.authority_id:
            mismatches.append(f"plan authority {plan.authority_id} does not match selected authority {selection.authority_id}")
        if plan.transfer_backend != selection.transfer_backend:
            mismatches.append(
                f"plan transfer backend {getattr(plan.transfer_backend, 'value', None)} does not match "
                f"selected backend {getattr(selection.transfer_backend, 'value', None)}"
            )
        if plan.blender_call_surface != selection.blender_call_surface:
            mismatches.append(
                f"plan Blender call surface {getattr(plan.blender_call_surface, 'value', None)} does not match "
                f"selected surface {getattr(selection.blender_call_surface, 'value', None)}"
            )
        if plan.modification_method != selection.modification_method:
            mismatches.append(
                f"plan modification method {plan.modification_method} does not match selected method {selection.modification_method}"
            )
        if plan.host_app != selection.host_app:
            mismatches.append(f"plan host app {plan.host_app} does not match selected host app {selection.host_app}")
        if plan.host_call_surface != selection.host_call_surface:
            mismatches.append(
                f"plan host call surface {plan.host_call_surface} does not match selected surface {selection.host_call_surface}"
            )
        if plan.plan_status in {
            WorkflowPlanStatus.COMPLETED,
            WorkflowPlanStatus.FAILED,
            WorkflowPlanStatus.INVALID,
            WorkflowPlanStatus.SUPERSEDED,
        }:
            mismatches.append(f"plan revision {plan.revision_id} is not executable in status {plan.plan_status.value}")
        if mismatches:
            raise WorkflowPlanError("; ".join(mismatches))
