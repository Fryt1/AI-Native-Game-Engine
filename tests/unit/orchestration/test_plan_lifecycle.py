from ainative.agent import WorkflowGuide
from ainative.orchestration import RuntimeContext
from ainative.orchestration.contracts import (
    BlenderCallSurface,
    ExecutionPlan,
    StepPlan,
    TaskContract,
    TaskResult,
    TaskRoute,
    TaskStatus,
    ToolExecutionKind,
    WorkflowPlan,
    WorkflowPlanStatus,
)
from ainative.orchestration.planning import (
    PlanIntegrityError,
    replan_plan,
    supersede_plan,
    validate_plan_structure,
)
from ainative.registry import toolset_from_operations
from ainative.toolsets.blender_editor.execution import (
    BlenderAddonSurface,
    BlenderExecutor,
)
from tests.support.plan_factory import (
    call,
    execute_local_tool_and_submit,
    plan_for,
    stage_plan,
)


def execute_agent_plan(task, plan, runtime):
    session = WorkflowGuide().start(task, plan, runtime)
    for stage in plan.workflow.stage_requests:
        for tool_call in stage.calls:
            result = execute_local_tool_and_submit(session, stage, tool_call)
            if result.status is not TaskStatus.SUCCEEDED:
                break
        session.complete_stage(stage.stage_id)
    return session.finish()



def test_agent_authored_plan_starts_as_an_immutable_draft_revision():
    task = TaskContract(
        task_id="plan-lifecycle",
        objective="Inspect a Blender object",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "blender"},
    )
    plan = plan_for(
        task,
        (StepPlan("inspect", "Inspect the object", (stage_plan("stage.inspect", "Inspect", "inspect-active"),)),),
    )

    assert plan.plan_id == "plan-lifecycle:plan"
    assert plan.revision == 1
    assert plan.revision_id == "plan-lifecycle:plan:r1"
    assert plan.plan_status is WorkflowPlanStatus.DRAFT


def test_replan_attaches_a_new_agent_authored_revision_without_mutating_old_plan():
    task = TaskContract(
        task_id="replan-task",
        objective="Move an Actor in a UE5 level",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "ue5"},
    )
    previous = plan_for(
        task,
        (StepPlan("old", "Old plan", (stage_plan("stage.old", "Old", "read_actor_transform"),)),),
    )
    replacement = plan_for(
        task,
        (StepPlan("new", "New plan", (stage_plan("stage.new", "New", "read_actor_transform"),)),),
    )

    superseded = supersede_plan(previous, "the first plan selected the wrong target")
    revised = replan_plan(previous, replacement, "the first plan selected the wrong target")

    assert previous.plan_status is WorkflowPlanStatus.DRAFT
    assert superseded.plan_status is WorkflowPlanStatus.SUPERSEDED
    assert superseded.revision_id == previous.revision_id
    assert revised.plan_id == previous.plan_id
    assert revised.revision == previous.revision + 1
    assert revised.supersedes_plan_id == previous.revision_id
    assert revised.replan_reason == "the first plan selected the wrong target"
    assert revised.plan_status is WorkflowPlanStatus.DRAFT
    assert revised.stages == ("stage.new",)


def test_agent_execution_records_plan_revision_after_selected_tools_finish():
    seen = []

    def execute(request):
        seen.append(request.operation)
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.HOST_OPERATION.value, details={"ok": True})

    task = TaskContract(
        task_id="completed-plan",
        objective="Inspect a Blender object",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "blender"},
        preferred_call_surface=BlenderCallSurface.ADDON,
    )
    selected_call = call("blender.editor", "blender", "inspect-active", "inspect-1")
    plan = plan_for(
        task,
        (StepPlan("inspect", "Inspect", (stage_plan("stage.inspect", "Inspect", "inspect-active", (selected_call,)),)),),
    )
    runtime = RuntimeContext(blender=BlenderExecutor({BlenderCallSurface.ADDON: BlenderAddonSurface(execute)}))

    result = execute_agent_plan(task, plan, runtime)

    assert result.status is TaskStatus.SUCCEEDED
    assert result.plan_id == "completed-plan:plan"
    assert result.plan_revision == 1
    assert result.plan_revision_id == "completed-plan:plan:r1"
    assert result.plan_status == WorkflowPlanStatus.COMPLETED.value
    assert seen == ["inspect-active"]


def test_invalid_stage_dependency_is_rejected_before_execution():
    plan = ExecutionPlan(
        workflow=WorkflowPlan(
            workflow_id="host-operation",
            route=TaskRoute.HOST_OPERATION,
            profile="default",
            authority_id="host-operation",
            steps=(
                StepPlan("one", "One", (stage_plan("stage.one", "One", "inspect"),)),
                StepPlan(
                    "two",
                    "Two",
                    (stage_plan("stage.two", "Two", "inspect", depends_on=("stage.missing",)),),
                    depends_on=("one",),
                ),
            ),
        ),
        transfer_backend=None,
        blender_call_surface=None,
        modification_method="host_operation",
        host_app="ue5",
        host_call_surface="ue5-python",
    )

    try:
        validate_plan_structure(plan)
    except PlanIntegrityError as exc:
        assert exc.issues[0].location == "stage:stage.two.depends_on"
    else:
        raise AssertionError("invalid plan dependency was accepted")


def test_agent_execution_session_returns_failure_after_selected_tool_fails():
    class FailingUE5:
        host_id = "ue5"

        def is_ready(self):
            return True

        def toolsets(self):
            return (
                toolset_from_operations(
                    toolset_id="ue5.editor",
                    provider_id="ue5",
                    execution_kind=ToolExecutionKind.HOST,
                    operations=("read_actor_transform",),
                ),
            )

        def execute(self, request):
            return TaskResult(
                status=TaskStatus.FAILED,
                route=TaskRoute.HOST_OPERATION.value,
                errors=("temporary UE5 failure",),
                resume_pointer="stage.read",
            )

    task = TaskContract(
        task_id="suspended-plan",
        objective="Inspect an Actor in a UE5 level",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "ue5"},
    )
    selected_call = call("ue5.editor", "ue5", "read_actor_transform", "read-1")
    plan = plan_for(
        task,
        (StepPlan("read", "Read", (stage_plan("stage.read", "Read", "read_actor_transform", (selected_call,)),)),),
    )

    session = WorkflowGuide().start(task, plan, RuntimeContext(ue5=FailingUE5()))
    stage = plan.workflow.steps[0].stages[0]
    tool_result = execute_local_tool_and_submit(session, stage, stage.calls[0])
    stage_result = session.complete_stage("stage.read")
    result = session.finish()

    assert tool_result.status is TaskStatus.FAILED
    assert stage_result.status is TaskStatus.FAILED
    assert result.status is TaskStatus.FAILED
    assert result.plan_status == WorkflowPlanStatus.SUSPENDED.value
    assert result.plan_revision_id == "suspended-plan:plan:r1"
    assert result.resume_pointer == "stage.read"

