from __future__ import annotations

from typing import Any

from ainative.model import (
    AcceptanceCheck,
    CallKind,
    CallTarget,
    CheckOperator,
    ExecutionChecklistItem,
    ExecutionResult,
    StageKind,
    StageRequest,
    TaskContract,
    TaskStatus,
    ToolCall,
    Workflow,
    WorkflowStep,
)


def call(
    owner: str,
    name: str,
    call_id: str,
    arguments: dict[str, Any] | None = None,
    depends_on: tuple[str, ...] = (),
    kind: CallKind = CallKind.MCP,
) -> ToolCall:
    """Build one declared call.

    @param owner: the Toolset id for a project Tool, or the MCP server name.
    @param name: the Tool id, or the MCP tool name on that server.
    @param call_id: the id this Workflow refers to the call by.
    @param arguments: the arguments the Agent will pass.
    @param depends_on: calls that must complete first.
    @param kind: where the call is executed.
    """

    return ToolCall(
        call_id=call_id,
        target=CallTarget(owner=owner, name=name),
        kind=kind,
        arguments=dict(arguments or {}),
        depends_on=depends_on,
    )


def stage_spec(
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


def workflow_for(
    task: TaskContract,
    steps: tuple[WorkflowStep, ...],
    *,
    guidance: str | None = None,
    revision: int = 1,
    workflow_id: str | None = None,
) -> Workflow:
    workflow = Workflow(
        guidance=guidance or task.guidance or "",
        route=task.route,
        steps=steps,
        workflow_id=workflow_id or f"{task.task_id}:workflow",
        revision=revision,
    )
    return workflow


def one_stage_workflow(
    task: TaskContract,
    stage: StageRequest,
    *,
    step_id: str = "step-1",
    step_purpose: str = "Execute the Agent-selected Stage",
) -> Workflow:
    return workflow_for(task, (WorkflowStep(step_id, step_purpose, (stage,)),))


def submit_call_result(
    session,
    call: ToolCall,
    status: TaskStatus = TaskStatus.SUCCEEDED,
    **evidence: Any,
) -> ExecutionResult:
    """Submit one declared call's result as the Agent would.

    This is the test stand-in for the Agent reporting what its own MCP call
    returned. It is deliberately not part of the product runtime: nothing here
    executes anything.

    @param session: the open session.
    @param call: the declared call this result belongs to.
    @param status: what the Agent reported.
    @param evidence: extra evidence fields (``outputs``, ``preserved_relations``, ...).
    @returns the recorded execution result.
    """

    session.check_call_ready(call.call_id)
    result = ExecutionResult(
        call_id=call.call_id,
        status=status,
        kind=call.kind,
        target=call.target,
        outputs=dict(evidence.pop("outputs", {})),
        artifacts=tuple(evidence.pop("artifacts", ())),
        warnings=tuple(evidence.pop("warnings", ())),
        errors=tuple(evidence.pop("errors", ())),
        preserved_relations=frozenset(evidence.pop("preserved_relations", ())),
        lost_relations=frozenset(evidence.pop("lost_relations", ())),
    )
    session.record_execution_result(result)
    return result
