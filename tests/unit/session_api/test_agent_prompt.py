import pytest

from ainative.model import (
    TaskContract,
    TaskRoute,
    TaskStatus,
    Workflow,
    WorkflowStatus,
    WorkflowStep,
)
from ainative.session_api import AcceptanceGuide, WorkflowError
from tests.support.workflow_factory import (
    call,
    stage_spec,
    submit_call_result,
    workflow_for,
)


def blender_task(task_id: str = "agent-task") -> TaskContract:
    return TaskContract(
        task_id=task_id,
        objective="在当前 Scene 里交互修改模型",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "blender"},
    )


def test_loading_a_skill_selects_guidance_without_executing_anything():
    task = blender_task("prompt-1")

    session = AcceptanceGuide().load_skill(task)

    assert session.guidance is None


def test_the_agent_may_request_the_native_blender_variant_explicitly():
    """The framework does not infer this from host_context; the Agent asks for it."""

    task = TaskContract(
        task_id="prompt-2",
        objective="在当前 Scene 里交互修改模型",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "blender"},
        guidance="native-blender-operation",
    )

    assert AcceptanceGuide().load_skill(task).guidance == "native-blender-operation"


def test_the_agent_declares_a_blender_mcp_call_and_reports_its_result():
    task = blender_task("agent-mcp-call")
    declared = call("blender", "modify_object", "modify-1")
    stage = stage_spec("stage.change", "Change the scene", "modify", (declared,))
    workflow = workflow_for(task, (WorkflowStep("change", "Apply the requested change", (stage,)),))

    session = AcceptanceGuide().start(task, workflow)

    assert session.ready
    assert session.completed_call_ids == ()

    result = submit_call_result(session, declared, TaskStatus.SUCCEEDED)
    assert result.status is TaskStatus.SUCCEEDED
    assert session.completed_call_ids == ("modify-1",)
    assert session.complete_stage("stage.change").status is TaskStatus.SUCCEEDED
    assert session.finish().status is TaskStatus.SUCCEEDED


def test_a_plan_selecting_a_tool_that_is_not_declared_anywhere_is_still_openable():
    """Nothing binds calls any more, so opening is about structure, not providers."""

    task = blender_task("agent-unbound-call")
    declared = call("edit.host", "not_registered", "missing-1")
    stage = stage_spec("stage.change", "Apply", "not_registered", (declared,))
    workflow = workflow_for(task, (WorkflowStep("change", "Apply", (stage,)),))

    session = AcceptanceGuide().start(task, workflow)

    assert session.ready


def test_agent_rejects_a_plan_whose_route_contradicts_the_task():
    task = blender_task("wrong-route")
    workflow = Workflow(
        guidance="asset-roundtrip",
        route=TaskRoute.ASSET_TRANSFER,
        steps=(),
        workflow_id="wrong-route:workflow",
    )

    with pytest.raises(WorkflowError, match="does not match task route"):
        AcceptanceGuide().start(task, workflow)


def test_the_framework_does_not_police_host_or_call_surface_choices():
    """Hosts are reached through MCP, so these are the Agent's calls, not workflow fields."""

    task = TaskContract(
        task_id="no-host-dimensions",
        objective="Inspect the UE5 level",
        route=TaskRoute.HOST_OPERATION,
    )
    workflow = workflow_for(task, (WorkflowStep("step", "Inspect", (stage_spec("stage", "Inspect"),)),))

    for field in ("host_app", "host_call_surface", "blender_call_surface", "modification_method"):
        assert not hasattr(workflow, field), f"{field} must not be a Workflow dimension"
    AcceptanceGuide().start(task, workflow)


def test_agent_rejects_superseded_plan_revision():
    from dataclasses import replace

    task = TaskContract(
        task_id="superseded-workflow",
        objective="Inspect the UE5 level",
        route=TaskRoute.HOST_OPERATION,
    )
    workflow = workflow_for(task, (WorkflowStep("step", "Inspect", (stage_spec("stage", "Inspect"),)),))
    superseded = replace(workflow, status=WorkflowStatus.SUPERSEDED)

    with pytest.raises(WorkflowError, match="not executable"):
        AcceptanceGuide().start(task, superseded)


