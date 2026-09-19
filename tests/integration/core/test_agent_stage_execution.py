"""The acceptance loop end to end: the Agent reports host MCP calls, Python judges."""

from dataclasses import replace

from ainative.model import (
    AcceptanceCheck,
    CallTarget,
    CheckOperator,
    ExecutionChecklistItem,
    NodeCheck,
    StageBody,
    StageKind,
    TaskContract,
    TaskRoute,
    TaskStatus,
)
from ainative.session_api import AcceptanceGuide
from tests.support.workflow_factory import (
    call,
    first_stage,
    first_stage_path,
    stage_spec,
    step,
    submit_call_result,
    workflow_for,
)


def host_task(task_id: str) -> TaskContract:
    return TaskContract(
        task_id=task_id,
        objective="Move an Actor in a UE5 level",
        route=TaskRoute.HOST_OPERATION,
    )


def read_plan(task: TaskContract):
    read = call("ue5", "get_actor_transform", "read-1")
    stage = stage_spec("stage.read", "Read the Actor transform", "read_actor_transform", (read,))
    return workflow_for(task, (step("read", "Read current state", (stage,)),))


def relation_stage(call_id: str = "export-1"):
    """A Stage whose acceptance depends on a relation being proven."""

    transfer = call("blender", "export_selected", call_id)
    base = stage_spec("stage.transfer", "Export the asset", "export", (transfer,))
    stage = replace(
        base,
        stage=StageBody(
            calls=base.stage.calls,
            execution_checklist=(
                ExecutionChecklistItem(
                    item_id="ran-export",
                    description="run the export",
                    call_ids=(call_id,),
                ),
            ),
            acceptance_checklist=(
                NodeCheck(AcceptanceCheck(
                    check_id="identity-proven",
                    description="asset identity survived",
                    operator=CheckOperator.TRUTHY,
                    source_call_id=call_id,
                    actual_path=("preserved_relations",),
                )),
            ),
            stage_kind=StageKind.CHANGE,
        ),
    )
    return transfer, stage


def test_the_agent_reports_its_own_mcp_call_and_the_stage_closes():
    task = host_task("mcp-roundtrip")
    workflow = read_plan(task)
    session = AcceptanceGuide().start(task, workflow)
    stage = first_stage(workflow)

    assert session.ready
    submit_call_result(session, stage.declared_calls[0], TaskStatus.SUCCEEDED, outputs={"actor": "Cube"})

    result = session.complete_node(first_stage_path(workflow))
    assert result.status is TaskStatus.SUCCEEDED
    assert result.execution_results[0].target == CallTarget(owner="ue5", name="get_actor_transform")
    assert session.finish().status is TaskStatus.SUCCEEDED


def test_a_failed_host_call_fails_the_stage():
    task = host_task("mcp-failure")
    workflow = read_plan(task)
    session = AcceptanceGuide().start(task, workflow)
    stage = first_stage(workflow)

    submit_call_result(session, stage.declared_calls[0], TaskStatus.FAILED, errors=("ue5 MCP call failed",))
    result = session.complete_node(first_stage_path(workflow))

    assert result.status is TaskStatus.FAILED
    assert session.finish().status is TaskStatus.FAILED


def test_tool_success_alone_does_not_prove_a_preserved_relation():
    """The core promise: a succeeded call is not a completed Stage."""

    task = TaskContract(
        task_id="relation-not-proven",
        objective="Round-trip a mesh and keep its identity",
        route=TaskRoute.ASSET_TRANSFER,
        preserve_relations=frozenset({"asset_identity"}),
    )
    transfer, stage = relation_stage()
    workflow = workflow_for(task, (step("transfer", "Transfer", (stage,)),))
    session = AcceptanceGuide().start(task, workflow)

    # The call itself succeeded, but nothing proved the relation.
    submit_call_result(session, transfer, TaskStatus.SUCCEEDED, preserved_relations=())
    result = session.complete_node(first_stage_path(workflow))

    assert result.execution_results[0].status is TaskStatus.SUCCEEDED
    assert result.check_results[0].status.value == "fail"
    assert result.status is TaskStatus.FAILED


def test_proven_relations_pass_the_same_check():
    task = TaskContract(
        task_id="relation-proven",
        objective="Round-trip a mesh and keep its identity",
        route=TaskRoute.ASSET_TRANSFER,
        preserve_relations=frozenset({"asset_identity"}),
    )
    transfer, stage = relation_stage()
    workflow = workflow_for(task, (step("transfer", "Transfer", (stage,)),))
    session = AcceptanceGuide().start(task, workflow)

    submit_call_result(session, transfer, TaskStatus.SUCCEEDED, preserved_relations=("asset_identity",))
    result = session.complete_node(first_stage_path(workflow))

    assert result.check_results[0].status.value == "pass"
    assert result.status is TaskStatus.SUCCEEDED
