from dataclasses import replace

from ainative.model import (
    NodeKind,
    TaskContract,
    TaskStatus,
    WorkflowNode,
    WorkflowStatus,
    WorkflowTree,
)
from ainative.reading import (
    TreeIntegrityError,
    validate_tree_structure,
)
from ainative.session_api import AcceptanceGuide
from tests.support.workflow_factory import (
    call,
    first_stage_path,
    stage_spec,
    step,
    submit_call_result,
    workflow_for,
)


def test_agent_authored_plan_starts_as_an_immutable_draft_revision():
    task = TaskContract(
        task_id="plan-lifecycle",
        objective="Inspect a Blender object",
        target_context={"app": "blender"},
    )
    workflow = workflow_for(
        task,
        (step("inspect", "Inspect the object", (stage_spec("stage.inspect", "Inspect", "inspect-active"),)),),
    )

    assert workflow.workflow_id == "plan-lifecycle:workflow"
    assert workflow.revision == 1
    assert workflow.revision_id == "plan-lifecycle:workflow:r1"
    assert workflow.status is WorkflowStatus.DRAFT


def test_replan_attaches_a_new_agent_authored_revision_without_mutating_old_plan():
    task = TaskContract(
        task_id="replan-task",
        objective="Move an Actor in a UE5 level",
        target_context={"app": "ue5"},
    )
    previous = workflow_for(
        task,
        (step("old", "Old workflow", (stage_spec("stage.old", "Old", "read_actor_transform", (call("ue5", "read_actor_transform", "old-1"),)),)),),
    )
    replacement = workflow_for(
        task,
        (step("new", "New workflow", (stage_spec("stage.new", "New", "read_actor_transform", (call("ue5", "read_actor_transform", "new-1"),)),)),),
    )

    # The reading module's `supersede_workflow` / `replan_workflow` helpers are gone;
    # both were `dataclasses.replace` over the revision fields, so the same transition
    # is expressed here directly against the model.
    superseded = replace(
        previous,
        status=WorkflowStatus.SUPERSEDED,
    )
    revised = replace(
        replacement,
        workflow_id=previous.workflow_id,
        revision=previous.revision + 1,
        status=WorkflowStatus.DRAFT,
        supersedes_workflow_id=previous.revision_id,
    )
    validate_tree_structure(revised)

    assert previous.status is WorkflowStatus.DRAFT
    assert superseded.status is WorkflowStatus.SUPERSEDED
    assert superseded.revision_id == previous.revision_id
    assert revised.workflow_id == previous.workflow_id
    assert revised.revision == previous.revision + 1
    assert revised.supersedes_workflow_id == previous.revision_id
    assert revised.status is WorkflowStatus.DRAFT
    assert revised.stage_paths == (first_stage_path(replacement),)


def test_agent_execution_records_plan_revision_after_selected_calls_finish():
    task = TaskContract(
        task_id="completed-workflow",
        objective="Inspect an object on the edit host",
        target_context={"app": "blender"},
    )
    selected_call = call("blender", "inspect_active", "inspect-1")
    workflow = workflow_for(
        task,
        (step("inspect", "Inspect", (stage_spec("stage.inspect", "Inspect", "inspect-active", (selected_call,)),)),),
    )

    session = AcceptanceGuide().start(task, workflow)
    submit_call_result(session, selected_call, TaskStatus.SUCCEEDED)
    session.complete_node(first_stage_path(workflow))
    result = session.finish()

    assert result.status is TaskStatus.SUCCEEDED
    assert result.workflow_id == "completed-workflow:workflow"
    assert result.workflow_revision == 1
    assert result.workflow_revision_id == "completed-workflow:workflow:r1"
    assert result.workflow_status == WorkflowStatus.COMPLETED.value


def test_invalid_stage_dependency_is_rejected_before_execution():
    workflow = WorkflowTree(
        workflow_id="invalid-dependency:workflow",
        guidance="host-operation",
        root=WorkflowNode(
            node_id="workflow",
            kind=NodeKind.WORKFLOW,
            purpose="the Workflow",
            children=(
                step("one", "One", (stage_spec("stage.one", "One", "inspect", (call("ue5", "inspect", "one-1"),)),)),
                step(
                    "two",
                    "Two",
                    (
                        stage_spec(
                            "stage.two",
                            "Two",
                            "inspect",
                            (call("ue5", "inspect", "two-1"),),
                            depends_on=("../stage.missing",),
                        ),
                    ),
                    depends_on=("../one",),
                ),
            ),
        ),
    )
    offending = next(path for path, node in workflow.stages if node.node_id == "stage.two")

    try:
        validate_tree_structure(workflow)
    except TreeIntegrityError as exc:
        assert exc.issues[0].location == offending
        assert "stage.missing" in exc.issues[0].message
    else:
        raise AssertionError("invalid workflow dependency was accepted")


def test_a_failed_call_suspends_the_plan_revision():
    task = TaskContract(
        task_id="suspended-workflow",
        objective="Inspect an Actor in a UE5 level",
        target_context={"app": "ue5"},
    )
    selected_call = call("ue5", "read_actor_transform", "read-1")
    workflow = workflow_for(
        task,
        (step("read", "Read", (stage_spec("stage.read", "Read", "read_actor_transform", (selected_call,)),)),),
    )

    session = AcceptanceGuide().start(task, workflow)
    call_result = submit_call_result(
        session, selected_call, TaskStatus.FAILED, errors=("temporary UE5 failure",)
    )
    stage_result = session.complete_node(first_stage_path(workflow))
    result = session.finish()

    assert call_result.status is TaskStatus.FAILED
    assert stage_result.status is TaskStatus.FAILED
    assert result.status is TaskStatus.FAILED
    assert result.workflow_status == WorkflowStatus.SUSPENDED.value
    assert result.workflow_revision_id == "suspended-workflow:workflow:r1"
