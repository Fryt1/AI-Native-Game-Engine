from dataclasses import replace

import pytest

from ainative.agent import WorkflowGuide, WorkflowPlanError
from ainative.orchestration import RuntimeContext
from ainative.orchestration.contracts import (
    BlenderCallSurface,
    ExecutionPlan,
    StepPlan,
    TaskContract,
    TaskRoute,
    TaskStatus,
    ToolCall,
    WorkflowPlan,
    WorkflowPlanStatus,
)
from ainative.toolsets.blender_editor.execution import (
    BlenderAddonSurface,
    BlenderExecutor,
)
from tests.support.plan_factory import (
    execute_local_tool_and_submit,
    plan_for,
    stage_plan,
)


def test_agent_does_not_execute_when_only_skill_is_loaded():
    seen = []

    def execute(request):
        seen.append(request.operation)
        raise AssertionError("loading Skill must not execute a Tool")

    task = TaskContract(
        task_id="prompt-1",
        objective="在当前 Scene 里交互修改 Blender 模型",
        route=TaskRoute.HOST_OPERATION,
        profile="interactive",
        target_context={"app": "blender"},
        preferred_call_surface=BlenderCallSurface.ADDON,
    )

    session = WorkflowGuide().load_skill(task)

    assert session.workflow_id == "native-blender-operation"
    assert seen == []


def test_agent_executes_one_explicit_tool_call_at_a_time():
    seen = []

    def execute(request):
        seen.append(request.operation)
        return __import__("ainative.orchestration.contracts", fromlist=["TaskResult"]).TaskResult(
            status=TaskStatus.SUCCEEDED,
            route=TaskRoute.HOST_OPERATION.value,
            details={"ok": True},
        )

    task = TaskContract(
        task_id="agent-tool-call",
        objective="在当前 Scene 里交互修改 Blender 模型",
        route=TaskRoute.HOST_OPERATION,
        profile="interactive",
        target_context={"app": "blender"},
        preferred_call_surface=BlenderCallSurface.ADDON,
    )
    call = ToolCall(
        call_id="modify-1",
        toolset_id="blender.editor",
        tool_id="blender.editor.modify",
    )
    plan = ExecutionPlan(
        workflow=WorkflowPlan(
            workflow_id="native-blender-operation",
            route=TaskRoute.HOST_OPERATION,
            profile="interactive",
            authority_id="host-operation",
            steps=(StepPlan("change", "Apply the requested change", (stage_plan("stage.change", "Change the scene", "modify", (call,)),)),),
            plan_id="agent-tool-call:plan",
        ),
        transfer_backend=None,
        blender_call_surface=BlenderCallSurface.ADDON,
        modification_method="native_host_operation",
        host_app="blender",
        host_call_surface=BlenderCallSurface.ADDON.value,
    )
    runtime = RuntimeContext(blender=BlenderExecutor({BlenderCallSurface.ADDON: BlenderAddonSurface(execute)}))

    agent_session = WorkflowGuide().start(task, plan, runtime)

    assert agent_session.ready
    assert seen == []
    stage = plan.workflow.steps[0].stages[0]
    result = execute_local_tool_and_submit(agent_session, stage, stage.calls[0])
    assert result.status is TaskStatus.SUCCEEDED
    assert seen == ["modify"]
    stage = agent_session.complete_stage("stage.change")
    assert stage.status is TaskStatus.SUCCEEDED
    assert agent_session.finish().status is TaskStatus.SUCCEEDED


def test_agent_plan_with_missing_tool_is_blocked_before_any_tool_call():
    seen = []

    def execute(request):
        seen.append(request.operation)

    task = TaskContract(
        task_id="agent-missing-tool",
        objective="在当前 Scene 里交互修改 Blender 模型",
        route=TaskRoute.HOST_OPERATION,
        profile="interactive",
        target_context={"app": "blender"},
        preferred_call_surface=BlenderCallSurface.ADDON,
    )
    call = ToolCall(call_id="missing-1", toolset_id="blender.editor", tool_id="blender.editor.not_registered")
    plan = ExecutionPlan(
        workflow=WorkflowPlan(
            "native-blender-operation",
            TaskRoute.HOST_OPERATION,
            "interactive",
            "host-operation",
            (StepPlan("change", "Apply", (stage_plan("stage.change", "Apply", "not_registered", (call,)),)),),
            plan_id="agent-missing-tool:plan",
        ),
        transfer_backend=None,
        blender_call_surface=BlenderCallSurface.ADDON,
        modification_method="native_host_operation",
        host_app="blender",
        host_call_surface=BlenderCallSurface.ADDON.value,
    )
    runtime = RuntimeContext(blender=BlenderExecutor({BlenderCallSurface.ADDON: BlenderAddonSurface(execute)}))

    agent_session = WorkflowGuide().start(task, plan, runtime)

    assert not agent_session.ready
    stage = plan.workflow.steps[0].stages[0]
    result = execute_local_tool_and_submit(agent_session, stage, stage.calls[0])
    assert result.status is TaskStatus.BLOCKED
    assert seen == []


def test_agent_rejects_plan_for_a_different_workflow():
    task = TaskContract(
        task_id="wrong-workflow",
        objective="Modify a Blender model",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "blender"},
    )
    plan = ExecutionPlan(
        workflow=WorkflowPlan(
            "host-operation",
            TaskRoute.HOST_OPERATION,
            "default",
            "host-operation",
            (),
            plan_id="wrong-workflow:plan",
        ),
        transfer_backend=None,
        blender_call_surface=BlenderCallSurface.CLI_PYTHON,
        modification_method="native_host_operation",
        host_app="blender",
        host_call_surface=BlenderCallSurface.CLI_PYTHON.value,
    )

    try:
        WorkflowGuide().start(task, plan, RuntimeContext())
    except WorkflowPlanError as exc:
        assert "does not match selected Workflow" in str(exc)
    else:
        raise AssertionError("a plan for another Workflow was accepted")


def test_agent_rejects_plan_that_changes_selected_host_dimensions():
    task = TaskContract(
        task_id="selection-mismatch",
        objective="Inspect the UE5 level",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "ue5"},
    )
    plan = plan_for(task, (StepPlan("step", "Inspect", (stage_plan("stage", "Inspect"),)),))
    wrong = replace(plan, host_app="blender", host_call_surface="blender_cli_python")

    with pytest.raises(WorkflowPlanError, match="host app"):
        WorkflowGuide().start(task, wrong, RuntimeContext())


def test_agent_rejects_superseded_plan_revision():
    task = TaskContract(
        task_id="superseded-plan",
        objective="Inspect the UE5 level",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "ue5"},
    )
    plan = plan_for(task, (StepPlan("step", "Inspect", (stage_plan("stage", "Inspect"),)),))
    superseded = replace(plan, workflow=replace(plan.workflow, status=WorkflowPlanStatus.SUPERSEDED))

    with pytest.raises(WorkflowPlanError, match="not executable"):
        WorkflowGuide().start(task, superseded, RuntimeContext())



def test_prompt_entry_requires_an_explicit_agent_owned_interpreter():
    guide = WorkflowGuide()

    with pytest.raises(WorkflowPlanError, match="No Agent-owned IntentInterpreter"):
        guide.task_from_prompt("处理一下这个模型", "ambiguous-task")
