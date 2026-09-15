from ainative.model import (
    TaskContract,
    TaskRoute,
    TaskStatus,
    Workflow,
    WorkflowStatus,
    WorkflowStep,
)
from ainative.reading import (
    WorkflowIntegrityError,
    replan_workflow,
    supersede_workflow,
    validate_workflow_structure,
)
from ainative.session_api import AcceptanceGuide
from tests.support.workflow_factory import (
    call,
    stage_spec,
    submit_call_result,
    workflow_for,
)


def test_agent_authored_plan_starts_as_an_immutable_draft_revision():
    task = TaskContract(
        task_id="plan-lifecycle",
        objective="Inspect a Blender object",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "blender"},
    )
    workflow = workflow_for(
        task,
        (WorkflowStep("inspect", "Inspect the object", (stage_spec("stage.inspect", "Inspect", "inspect-active"),)),),
    )

    assert workflow.workflow_id == "plan-lifecycle:workflow"
    assert workflow.revision == 1
    assert workflow.revision_id == "plan-lifecycle:workflow:r1"
    assert workflow.status is WorkflowStatus.DRAFT


def test_replan_attaches_a_new_agent_authored_revision_without_mutating_old_plan():
    task = TaskContract(
        task_id="replan-task",
        objective="Move an Actor in a UE5 level",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "ue5"},
    )
    previous = workflow_for(
        task,
        (WorkflowStep("old", "Old workflow", (stage_spec("stage.old", "Old", "read_actor_transform"),)),),
    )
    replacement = workflow_for(
        task,
        (WorkflowStep("new", "New workflow", (stage_spec("stage.new", "New", "read_actor_transform"),)),),
    )

    superseded = supersede_workflow(previous, "the first workflow selected the wrong target")
    revised = replan_workflow(previous, replacement, "the first workflow selected the wrong target")

    assert previous.status is WorkflowStatus.DRAFT
    assert superseded.status is WorkflowStatus.SUPERSEDED
    assert superseded.revision_id == previous.revision_id
    assert revised.workflow_id == previous.workflow_id
    assert revised.revision == previous.revision + 1
    assert revised.supersedes_workflow_id == previous.revision_id
    assert revised.replacement_reason == "the first workflow selected the wrong target"
    assert revised.status is WorkflowStatus.DRAFT
    assert revised.stages == ("stage.new",)


def test_agent_execution_records_plan_revision_after_selected_calls_finish():
    task = TaskContract(
        task_id="completed-workflow",
        objective="Inspect an object on the edit host",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "blender"},
    )
    selected_call = call("blender", "inspect_active", "inspect-1")
    workflow = workflow_for(
        task,
        (WorkflowStep("inspect", "Inspect", (stage_spec("stage.inspect", "Inspect", "inspect-active", (selected_call,)),)),),
    )

    session = AcceptanceGuide().start(task, workflow)
    submit_call_result(session, selected_call, TaskStatus.SUCCEEDED)
    session.complete_stage("stage.inspect")
    result = session.finish()

    assert result.status is TaskStatus.SUCCEEDED
    assert result.workflow_id == "completed-workflow:workflow"
    assert result.workflow_revision == 1
    assert result.workflow_revision_id == "completed-workflow:workflow:r1"
    assert result.workflow_status == WorkflowStatus.COMPLETED.value


def test_invalid_stage_dependency_is_rejected_before_execution():
    workflow = Workflow(
        guidance="host-operation",
        route=TaskRoute.HOST_OPERATION,
        steps=(
            WorkflowStep("one", "One", (stage_spec("stage.one", "One", "inspect"),)),
            WorkflowStep(
                "two",
                "Two",
                (stage_spec("stage.two", "Two", "inspect", depends_on=("stage.missing",)),),
                depends_on=("one",),
            ),
        ),
    )

    try:
        validate_workflow_structure(workflow)
    except WorkflowIntegrityError as exc:
        assert exc.issues[0].location == "stage:stage.two.depends_on"
    else:
        raise AssertionError("invalid workflow dependency was accepted")


def test_a_failed_call_suspends_the_plan_revision():
    task = TaskContract(
        task_id="suspended-workflow",
        objective="Inspect an Actor in a UE5 level",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "ue5"},
    )
    selected_call = call("ue5", "read_actor_transform", "read-1")
    workflow = workflow_for(
        task,
        (WorkflowStep("read", "Read", (stage_spec("stage.read", "Read", "read_actor_transform", (selected_call,)),)),),
    )

    session = AcceptanceGuide().start(task, workflow)
    call_result = submit_call_result(
        session, selected_call, TaskStatus.FAILED, errors=("temporary UE5 failure",)
    )
    stage_result = session.complete_stage("stage.read")
    result = session.finish()

    assert call_result.status is TaskStatus.FAILED
    assert stage_result.status is TaskStatus.FAILED
    assert result.status is TaskStatus.FAILED
    assert result.workflow_status == WorkflowStatus.SUSPENDED.value
    assert result.workflow_revision_id == "suspended-workflow:workflow:r1"

