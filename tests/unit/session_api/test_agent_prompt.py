import pytest

from ainative.model import (
    TaskContract,
    TaskStatus,
    WorkflowStatus,
)
from ainative.session_api import AcceptanceGuide, WorkflowError
from tests.support.workflow_factory import (
    call,
    first_stage_path,
    stage_spec,
    step,
    submit_call_result,
    workflow_for,
)


def blender_task(task_id: str = "agent-task") -> TaskContract:
    return TaskContract(
        task_id=task_id,
        objective="在当前 Scene 里交互修改模型",
        target_context={"app": "blender"},
    )


def test_loading_a_skill_executes_nothing():
    """Loading verifies the package; it never runs a call.

    The property that survived the guidance removal, and the one worth keeping: the
    engine reads files and checks a list, and touches nothing else.
    """

    task = blender_task("prompt-1")

    session = AcceptanceGuide().load_skill(task)

    assert session.skill_id == "ai-native-game-engine"
    assert session.package_root.is_dir()


def test_choosing_a_lifecycle_is_not_a_task_field():
    """Which lifecycle applies is the Agent's judgement, recorded nowhere here.

    The task and the Workflow no longer carry a guidance name: the skill catalog is
    what tells a model which lifecycles exist, and a second inventory inside the
    engine could only disagree with it.
    """

    task = TaskContract(
        task_id="prompt-2",
        objective="在当前 Scene 里交互修改模型",
        target_context={"app": "blender"},
    )

    assert not hasattr(task, "guidance")
    assert "guidance" not in task.to_dict()


def test_the_agent_declares_a_blender_mcp_call_and_reports_its_result():
    task = blender_task("agent-mcp-call")
    declared = call("blender", "modify_object", "modify-1")
    stage = stage_spec("stage.change", "Change the scene", "modify", (declared,))
    workflow = workflow_for(task, (step("change", "Apply the requested change", (stage,)),))

    session = AcceptanceGuide().start(task, workflow)

    assert session.ready
    assert session.completed_call_ids == ()

    result = submit_call_result(session, declared, TaskStatus.SUCCEEDED)
    assert result.status is TaskStatus.SUCCEEDED
    assert session.completed_call_ids == ("modify-1",)
    assert session.complete_node(first_stage_path(workflow)).status is TaskStatus.SUCCEEDED
    assert session.finish().status is TaskStatus.SUCCEEDED


def test_a_plan_selecting_a_tool_that_is_not_declared_anywhere_is_still_openable():
    """Nothing binds calls any more, so opening is about structure, not providers."""

    task = blender_task("agent-unbound-call")
    declared = call("edit.host", "not_registered", "missing-1")
    stage = stage_spec("stage.change", "Apply", "not_registered", (declared,))
    workflow = workflow_for(task, (step("change", "Apply", (stage,)),))

    session = AcceptanceGuide().start(task, workflow)

    assert session.ready


def test_the_framework_does_not_police_host_or_call_surface_choices():
    """Hosts are reached through MCP, so these are the Agent's calls, not workflow fields."""

    task = TaskContract(
        task_id="no-host-dimensions",
        objective="Inspect the UE5 level",
    )
    inspect = call("ue5", "inspect_active", "inspect-1")
    workflow = workflow_for(
        task, (step("step", "Inspect", (stage_spec("stage", "Inspect", "inspect", (inspect,)),)),)
    )

    for field in ("host_app", "host_call_surface", "blender_call_surface", "modification_method"):
        assert not hasattr(workflow, field), f"{field} must not be a Workflow dimension"
    AcceptanceGuide().start(task, workflow)


def test_agent_rejects_superseded_plan_revision():
    from dataclasses import replace

    task = TaskContract(
        task_id="superseded-workflow",
        objective="Inspect the UE5 level",
    )
    workflow = workflow_for(task, (step("step", "Inspect", (stage_spec("stage", "Inspect"),)),))
    superseded = replace(workflow, status=WorkflowStatus.SUPERSEDED)

    with pytest.raises(WorkflowError, match="not executable"):
        AcceptanceGuide().start(task, superseded)


