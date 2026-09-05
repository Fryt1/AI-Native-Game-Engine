from __future__ import annotations

from typing import Any

from ainative.orchestration.contracts import (
    AcceptanceCheck,
    CheckOperator,
    ExecutionChecklistItem,
    ExecutionPlan,
    ExecutionResult,
    StageKind,
    StageRequest,
    StepPlan,
    TaskContract,
    TaskStatus,
    ToolCall,
    ToolCallUsage,
    WorkflowPlan,
)
from ainative.orchestration.planning import select_workflow
from ainative.registry import tool_id_for


def call(
    toolset_id: str,
    provider_id: str,
    operation: str,
    call_id: str,
    arguments: dict[str, Any] | None = None,
    depends_on: tuple[str, ...] = (),
    usage: ToolCallUsage = ToolCallUsage.EXECUTE,
) -> ToolCall:
    return ToolCall(
        call_id=call_id,
        toolset_id=toolset_id,
        tool_id=tool_id_for(toolset_id, operation),
        arguments=dict(arguments or {}),
        depends_on=depends_on,
        usage=usage,
    )


def stage_plan(
    stage_id: str,
    purpose: str,
    operation: str = "",
    calls: tuple[ToolCall, ...] = (),
    *,
    stage_kind: StageKind = StageKind.CHANGE,
    depends_on: tuple[str, ...] = (),
    required: bool = True,
) -> StageRequest:
    execution_item = ExecutionChecklistItem(
        item_id=f"{stage_id}.executed",
        description=f"Required work for {purpose}",
        required=required,
        call_ids=tuple(call.call_id for call in calls),
        evidence_required=bool(calls),
    )
    source_call_id = calls[-1].call_id if calls else None
    acceptance_check = AcceptanceCheck(
        check_id=f"{stage_id}.completed",
        description=f"Completion evidence for {purpose}",
        required=required,
        call_ids=(source_call_id,) if source_call_id else (),
        source_call_id=source_call_id,
        operator=CheckOperator.TOOL_SUCCEEDED if source_call_id else CheckOperator.MANUAL,
        evidence_required=bool(source_call_id),
    )
    return StageRequest(
        stage_id=stage_id,
        purpose=purpose,
        operation=operation,
        calls=calls,
        stage_kind=stage_kind,
        execution_checklist=(execution_item,),
        acceptance_checklist=(acceptance_check,),
        depends_on=depends_on,
        required=required,
    )


def plan_for(
    task: TaskContract,
    steps: tuple[StepPlan, ...],
    *,
    plan_id: str | None = None,
    revision: int = 1,
    workflow_id: str | None = None,
) -> ExecutionPlan:
    selection = select_workflow(task)
    workflow = WorkflowPlan(
        workflow_id=workflow_id or selection.workflow_id,
        route=selection.route,
        profile=selection.profile,
        authority_id=selection.authority_id,
        steps=steps,
        plan_id=plan_id or f"{task.task_id}:plan",
        revision=revision,
    )
    return ExecutionPlan(
        workflow=workflow,
        transfer_backend=selection.transfer_backend,
        blender_call_surface=selection.blender_call_surface,
        modification_method=selection.modification_method,
        host_app=selection.host_app,
        host_call_surface=selection.host_call_surface,
    )


def one_stage_plan(
    task: TaskContract,
    stage: StageRequest,
    *,
    step_id: str = "step-1",
    step_purpose: str = "Execute the Agent-selected Stage",
) -> ExecutionPlan:
    return plan_for(task, (StepPlan(step_id, step_purpose, (stage,)),))


def tool_result_to_execution(call: ToolCall, result) -> ExecutionResult:
    """Convert a local TaskResult into the ExecutionResult the Agent submits.

    Used by tests and E2E runners as the stand-in for the real Agent submitting
    a raw Tool result. This helper is not part of the product runtime.
    """
    return ExecutionResult(
        call_id=call.call_id,
        kind="tool",
        toolset_id=call.toolset_id,
        tool_id=call.tool_id,
        status=result.status if isinstance(result.status, TaskStatus) else TaskStatus(result.status),
        outputs=dict(getattr(result, "details", {})),
        artifacts=getattr(result, "artifacts", ()),
        warnings=getattr(result, "warnings", ()),
        errors=getattr(result, "errors", ()),
        resume_pointer=getattr(result, "resume_pointer", None),
        preserved_relations=frozenset(getattr(result, "preserved_relations", ())),
        lost_relations=frozenset(getattr(result, "lost_relations", ())),
    )



def execute_local_tool_and_submit(session, stage: StageRequest, call: ToolCall) -> ExecutionResult:
    """Execute one Project ToolCall and submit its result as the Agent would.

    Thin wrapper over the product CLI execution module. This keeps the test
    stand-in identical to what ``python -m ainative.tools`` does for project
    Tools, while remaining outside WorkflowSession validation.
    """
    from ainative.cli.execute import (
        ToolExecutionContext,
        execute_resolved,
        to_execution_result,
    )
    from ainative.registry import ToolResolutionError

    try:
        resolved = session.runtime.resolve_tool(call)
    except ToolResolutionError as exc:
        result = ExecutionResult(
            call_id=call.call_id,
            kind="tool",
            toolset_id=call.toolset_id,
            tool_id=call.tool_id,
            status=TaskStatus.BLOCKED,
            errors=(str(exc),),
        )
        session.record_execution_result(result)
        return result
    ctx = ToolExecutionContext(
        task=session.task,
        stage=stage,
        manifest=session.manifest,
        plan_route=session.plan.route.value,
        plan_host_app=session.plan.host_app,
        plan_host_call_surface=session.plan.host_call_surface,
        plan_blender_call_surface=session.plan.blender_call_surface.value if session.plan.blender_call_surface else None,
        plan_transfer_backend=session.plan.transfer_backend.value if session.plan.transfer_backend else None,
        task_metadata=dict(session.task.metadata),
    )
    task_result = execute_resolved(session.runtime, call, resolved, ctx)
    result = to_execution_result(call, task_result)
    session.record_execution_result(result)
    return result
