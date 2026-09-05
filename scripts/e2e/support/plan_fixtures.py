"""Static Agent-authored plans used only by end-to-end fixtures.

The production runtime never derives a WorkflowPlan from a TaskContract. These
helpers stand in for the real Agent so host acceptance scripts can exercise the
same ``WorkflowGuide.start`` validation API with a reproducible plan. Project
ToolCalls are executed through the product CLI execution module and submitted as
ExecutionResults.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ainative.agent import WorkflowGuide
from ainative.orchestration.contracts import (
    AcceptanceCheck,
    CheckOperator,
    ExecutionChecklistItem,
    ExecutionPlan,
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


def selected_call(
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


def checked_stage(
    stage_id: str,
    purpose: str,
    operation: str,
    calls: tuple[ToolCall, ...],
    *,
    stage_kind: StageKind = StageKind.CHANGE,
    acceptance_operator: CheckOperator = CheckOperator.TOOL_SUCCEEDED,
    actual_path: tuple[str, ...] = (),
    expected: Any = None,
) -> StageRequest:
    source_call_id = calls[-1].call_id if calls else None
    return StageRequest(
        stage_id=stage_id,
        purpose=purpose,
        operation=operation,
        calls=calls,
        stage_kind=stage_kind,
        execution_checklist=(
            ExecutionChecklistItem(
                item_id=f"{stage_id}.execution",
                description=f"Execute all required work for {purpose}",
                call_ids=tuple(call.call_id for call in calls),
                evidence_required=bool(calls),
            ),
        ),
        acceptance_checklist=(
            AcceptanceCheck(
                check_id=f"{stage_id}.acceptance",
                description=f"Verify completion of {purpose}",
                call_ids=(source_call_id,) if source_call_id else (),
                source_call_id=source_call_id,
                actual_path=actual_path,
                operator=acceptance_operator,
                expected=expected,
                evidence_required=bool(source_call_id),
            ),
        ),
        recovery=stage_id,
    )


def agent_plan(task: TaskContract, steps: tuple[StepPlan, ...]) -> ExecutionPlan:
    selection = select_workflow(task)
    workflow = WorkflowPlan(
        workflow_id=selection.workflow_id,
        route=selection.route,
        profile=selection.profile,
        authority_id=selection.authority_id,
        steps=steps,
        plan_id=f"{task.task_id}:plan",
    )
    return ExecutionPlan(
        workflow=workflow,
        transfer_backend=selection.transfer_backend,
        blender_call_surface=selection.blender_call_surface,
        modification_method=selection.modification_method,
        host_app=selection.host_app,
        host_call_surface=selection.host_call_surface,
    )


def actor_operation_plan(task: TaskContract) -> ExecutionPlan:
    read_operation = str(task.metadata.get("read_operation", "read_actor_transform"))
    apply_operation = str(task.metadata.get("operation", "set_actor_transform"))
    publish_operation = task.metadata.get("publish_operation")
    read_call = selected_call(
        "ue5.editor",
        "ue5",
        read_operation,
        "read-1",
        usage=ToolCallUsage.OBSERVE,
    )
    apply_call = selected_call(
        "ue5.editor",
        "ue5",
        apply_operation,
        "apply-1",
        depends_on=(read_call.call_id,),
        usage=ToolCallUsage.EXECUTE,
    )
    steps = [
        StepPlan(
            "read-state",
            "Read the target Actor state before mutation.",
            (checked_stage("stage.read_state", "Read the Actor state.", read_operation, (read_call,), stage_kind=StageKind.INVESTIGATION),),
        ),
        StepPlan(
            "apply-change",
            "Apply the requested Actor mutation.",
            (checked_stage("stage.apply_change", "Apply the Actor transform.", apply_operation, (apply_call,)),),
            depends_on=("read-state",),
        ),
    ]
    previous_step = "apply-change"
    previous_call = apply_call.call_id
    if publish_operation:
        publish_call = selected_call(
            "ue5.editor",
            "ue5",
            str(publish_operation),
            "publish-1",
            depends_on=(previous_call,),
            usage=ToolCallUsage.EXECUTE,
        )
        steps.append(
            StepPlan(
                "publish-result",
                "Persist the approved Actor change.",
                (checked_stage("stage.publish_result", "Save the Level.", str(publish_operation), (publish_call,)),),
                depends_on=(previous_step,),
            )
        )
        previous_step = "publish-result"
        previous_call = publish_call.call_id
    validate_call = selected_call(
        "ue5.editor",
        "ue5",
        read_operation,
        "validate-1",
        depends_on=(previous_call,),
        usage=ToolCallUsage.VERIFY,
    )
    steps.append(
        StepPlan(
            "validate-result",
            "Read back the Actor and verify the declared result.",
            (
                checked_stage(
                    "stage.validate_result",
                    "Verify the Actor transform.",
                    read_operation,
                    (validate_call,),
                    stage_kind=StageKind.INVESTIGATION,
                    acceptance_operator=CheckOperator.WITHIN_TOLERANCE,
                    actual_path=("location",),
                    expected=task.metadata.get("expected_location", task.metadata.get("location")),
                ),
            ),
            depends_on=(previous_step,),
        )
    )
    return agent_plan(task, tuple(steps))


def level_template_plan(task: TaskContract) -> ExecutionPlan:
    create_call = selected_call(
        "ue5.editor",
        "ue5",
        "create_level_from_template",
        "create-1",
        {key: task.metadata[key] for key in ("template", "target", "expected_default_objects") if key in task.metadata},
        usage=ToolCallUsage.EXECUTE,
    )
    inspect_call = selected_call(
        "ue5.editor",
        "ue5",
        "inspect_level",
        "inspect-1",
        depends_on=(create_call.call_id,),
        usage=ToolCallUsage.VERIFY,
    )
    return agent_plan(
        task,
        (
            StepPlan(
                "create-level",
                "Create and open the target Level from the selected template.",
                (checked_stage("stage.create_level_from_template", "Create the Level.", "create_level_from_template", (create_call,)),),
            ),
            StepPlan(
                "validate-result",
                "Read the Level back and verify the template result.",
                (
                    checked_stage(
                        "stage.validate_result",
                        "Verify the Level.",
                        "inspect_level",
                        (inspect_call,),
                        stage_kind=StageKind.INVESTIGATION,
                        acceptance_operator=CheckOperator.TRUTHY,
                        actual_path=("default_objects_valid",),
                        expected=True,
                    ),
                ),
                depends_on=("create-level",),
            ),
        ),
    )


def asset_roundtrip_plan(task: TaskContract, backend_id: str) -> ExecutionPlan:
    transfer_call = selected_call(
        f"transfer.{backend_id}",
        backend_id,
        "transfer_to_edit_host",
        "transfer-1",
        usage=ToolCallUsage.EXECUTE,
    )
    modify_arguments = {
        key: task.metadata[key]
        for key in ("blender_edit_file", "modified_blend_file", "delta", "location", "scale", "rotation")
        if key in task.metadata
    }
    if task.metadata.get("blender_edit_file"):
        modify_arguments["blend_file"] = task.metadata["blender_edit_file"]
    if task.metadata.get("modified_blend_file"):
        modify_arguments["save_after"] = task.metadata["modified_blend_file"]
    modify_call = selected_call(
        "blender.editor",
        "blender",
        str(task.metadata.get("blender_operation", "translate-active")),
        "modify-1",
        modify_arguments,
        depends_on=(transfer_call.call_id,),
        usage=ToolCallUsage.EXECUTE,
    )
    return_call = selected_call(
        f"transfer.{backend_id}",
        backend_id,
        "return_to_target",
        "return-1",
        depends_on=(modify_call.call_id,),
        usage=ToolCallUsage.EXECUTE,
    )
    validate_call = selected_call(
        "validation.workflow",
        "validator",
        "validate",
        "validate-1",
        depends_on=(return_call.call_id,),
        usage=ToolCallUsage.VERIFY,
    )
    return agent_plan(
        task,
        (
            StepPlan(
                "transfer-to-edit-host",
                "Make the asset available in Blender.",
                (checked_stage("stage.transfer_to_edit_host", "Transfer to Blender.", "transfer_to_edit_host", (transfer_call,)),),
            ),
            StepPlan(
                "modify-asset",
                "Apply the requested Blender edit.",
                (checked_stage("stage.modify_asset", "Modify the asset.", "modify", (modify_call,)),),
                depends_on=("transfer-to-edit-host",),
            ),
            StepPlan(
                "return-to-target",
                "Return the edited representation to the target host.",
                (checked_stage("stage.return_to_target", "Return the asset.", "return_to_target", (return_call,)),),
                depends_on=("modify-asset",),
            ),
            StepPlan(
                "validate",
                "Validate the declared result and preserved relations.",
                (
                    checked_stage(
                        "stage.validate_asset",
                        "Validate the transfer.",
                        "validate",
                        (validate_call,),
                        stage_kind=StageKind.INVESTIGATION,
                    ),
                ),
                depends_on=("return-to-target",),
            ),
        ),
    )


def execute_agent_plan(task: TaskContract, plan: ExecutionPlan, runtime, manifest=None):
    """Simulate the Agent loop: execute each project ToolCall and submit it.

    The stand-in uses the same product CLI execution module an Agent would call,
    then submits the resulting ExecutionResult to WorkflowSession validation.
    """

    from ainative.cli.execute import (
        ToolExecutionContext,
        execute_resolved,
        to_execution_result,
    )

    session = WorkflowGuide().start(task, plan, runtime, manifest=manifest)
    for stage in plan.workflow.stage_requests:
        for call in stage.calls:
            try:
                session.check_call_ready(call.call_id)
                resolved = runtime.resolve_tool(call)
                ctx = ToolExecutionContext(
                    task=task,
                    stage=stage,
                    manifest=manifest,
                    plan_route=plan.route.value,
                    plan_host_app=plan.host_app,
                    plan_host_call_surface=plan.host_call_surface,
                    plan_blender_call_surface=plan.blender_call_surface.value if plan.blender_call_surface else None,
                    plan_transfer_backend=plan.transfer_backend.value if plan.transfer_backend else None,
                    task_metadata=dict(task.metadata),
                )
                task_result = execute_resolved(runtime, call, resolved, ctx)
            except Exception as exc:  # noqa: BLE001 - fixture must keep running on failure
                from ainative.orchestration.contracts import ExecutionResult
                task_result = None
                result = ExecutionResult(call_id=call.call_id, kind="tool", toolset_id=call.toolset_id, tool_id=call.tool_id, status=TaskStatus.BLOCKED, errors=(str(exc),))
                session.record_execution_result(result)
                break
            result = to_execution_result(call, task_result)
            session.record_execution_result(result)
            if result.status not in {TaskStatus.SUCCEEDED, TaskStatus.DEGRADED}:
                break
        stage_result = session.complete_stage(stage.stage_id)
        if stage_result.status not in {TaskStatus.SUCCEEDED, TaskStatus.DEGRADED}:
            break
    return session.finish()
