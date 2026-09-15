"""The session's own invariants: evidence recording, dependencies, and closure."""

import pytest

from ainative.model import (
    CheckResult,
    CheckStatus,
    ExecutionItemResult,
    ExecutionResult,
    StageKind,
    TaskContract,
    TaskRoute,
    TaskStatus,
    WorkflowStep,
)
from ainative.session_api import AcceptanceGuide, WorkflowError
from tests.support.workflow_factory import (
    call,
    one_stage_workflow,
    stage_spec,
    submit_call_result,
    workflow_for,
)


def host_task(task_id: str = "ue5-actor-stage") -> TaskContract:
    return TaskContract(
        task_id=task_id,
        objective="Move an Actor in a UE5 level",
        route=TaskRoute.HOST_OPERATION,
    )


def actor_plan(task: TaskContract, *, include_read=True, include_set=True):
    """A workflow declaring two UE5 MCP calls the Agent will make itself."""

    calls = []
    previous = None
    if include_read:
        read = call("ue5", "get_actor_transform", "read-1")
        calls.append(read)
        previous = read.call_id
    if include_set:
        calls.append(
            call(
                "ue5",
                "set_actor_transform",
                "set-1",
                {"expected_location": [100, 200, 300]},
                depends_on=(previous,) if previous else (),
            )
        )
    return workflow_for(
        task,
        (WorkflowStep("change", "Read and apply the Actor change", (stage_spec("stage.change", "Read and apply", "actor_transform", tuple(calls)),)),),
    )


def test_a_host_mcp_call_is_accepted_in_the_plan():
    """Host calls are the main work, so they must be declarable."""

    task = host_task()
    workflow = actor_plan(task)
    session = AcceptanceGuide().start(task, workflow)

    assert session.ready
    assert [c.target.name for c in workflow.calls] == ["get_actor_transform", "set_actor_transform"]


def test_opening_a_plan_executes_nothing():
    seen = []
    task = host_task()
    session = AcceptanceGuide().start(task, actor_plan(task))

    assert session.ready
    assert seen == []
    assert session.completed_call_ids == ()


def test_agent_reports_each_mcp_call_and_the_stage_closes():
    task = host_task()
    workflow = actor_plan(task)
    session = AcceptanceGuide().start(task, workflow)
    stage = workflow.stage_requests[0]

    for declared in stage.calls:
        result = submit_call_result(session, declared, TaskStatus.SUCCEEDED, outputs={"actor": "Cube"})
        assert result.status is TaskStatus.SUCCEEDED

    assert session.completed_call_ids == ("read-1", "set-1")
    assert session.complete_stage("stage.change").status is TaskStatus.SUCCEEDED
    assert session.finish().status is TaskStatus.SUCCEEDED


def test_a_call_cannot_be_recorded_before_its_declared_dependency():
    task = host_task("dependency-order")
    workflow = actor_plan(task)
    session = AcceptanceGuide().start(task, workflow)
    set_call = workflow.stage_requests[0].calls[1]

    with pytest.raises(WorkflowError, match="incomplete dependencies"):
        submit_call_result(session, set_call)


def test_a_result_for_a_call_the_plan_never_declared_is_rejected():
    task = host_task("undeclared")
    session = AcceptanceGuide().start(task, actor_plan(task))
    undeclared = call("ue5", "delete_everything", "not-declared")

    with pytest.raises(WorkflowError, match="undeclared call"):
        session.record_execution_result(
            ExecutionResult(
                call_id=undeclared.call_id,
                status=TaskStatus.SUCCEEDED,
                        target=undeclared.target,
            )
        )



def test_a_result_whose_target_contradicts_the_declaration_is_rejected():
    task = host_task("target-mismatch")
    workflow = actor_plan(task, include_set=False)
    session = AcceptanceGuide().start(task, workflow)
    declared = workflow.stage_requests[0].calls[0]

    from ainative.model import CallTarget, ExecutionResult

    mismatch = ExecutionResult(
        call_id=declared.call_id,
        status=TaskStatus.SUCCEEDED,
        target=CallTarget(owner="ue5", name="some_other_tool"),
    )
    with pytest.raises(WorkflowError, match="target mismatch"):
        session.record_execution_result(mismatch)


def test_the_same_call_cannot_be_recorded_twice():
    task = host_task("no-overwrite")
    workflow = actor_plan(task, include_set=False)
    session = AcceptanceGuide().start(task, workflow)
    declared = workflow.stage_requests[0].calls[0]
    submit_call_result(session, declared)

    with pytest.raises(WorkflowError, match="already been recorded"):
        submit_call_result(session, declared)


def test_a_stage_with_no_calls_closes_once_its_items_are_submitted():
    task = host_task("local-checkpoint")
    stage = stage_spec("stage.checkpoint", "A local checkpoint", stage_kind=StageKind.INVESTIGATION)
    workflow = one_stage_workflow(task, stage)
    session = AcceptanceGuide().start(task, workflow)

    session.record_execution_item(
        stage.stage_id,
        ExecutionItemResult(item_id=f"{stage.stage_id}.executed", status=CheckStatus.PASS, evidence_refs=("note:1",)),
    )
    session.record_check_result(
        stage.stage_id,
        CheckResult(check_id=f"{stage.stage_id}.completed", status=CheckStatus.PASS, evidence_refs=("note:1",)),
    )

    assert session.complete_stage(stage.stage_id).status is TaskStatus.SUCCEEDED


def test_a_manual_check_needs_a_recorded_result():
    task = host_task("manual-evidence")
    stage = stage_spec("stage.manual", "Manual check", stage_kind=StageKind.INVESTIGATION)
    workflow = one_stage_workflow(task, stage)
    session = AcceptanceGuide().start(task, workflow)

    before = session.complete_stage(stage.stage_id)
    assert before.status is TaskStatus.BLOCKED
    assert before.check_results[0].status is CheckStatus.UNKNOWN

    session.record_execution_item(
        stage.stage_id,
        ExecutionItemResult(item_id=f"{stage.stage_id}.executed", status=CheckStatus.PASS, evidence_refs=("note:1",)),
    )
    session.record_check_result(
        stage.stage_id,
        CheckResult(check_id=f"{stage.stage_id}.completed", status=CheckStatus.PASS, evidence_refs=("note:1",)),
    )
    assert session.complete_stage(stage.stage_id).status is TaskStatus.SUCCEEDED


def test_a_deterministic_check_cannot_be_overridden_by_the_agent():
    task = host_task("no-override")
    workflow = actor_plan(task, include_set=False)
    session = AcceptanceGuide().start(task, workflow)
    declared = workflow.stage_requests[0].calls[0]
    stage_id = workflow.stage_requests[0].stage_id

    with pytest.raises(WorkflowError, match="cannot be overridden"):
        session.record_check_result(
            stage_id,
            CheckResult(check_id=f"{stage_id}.completed", status=CheckStatus.PASS),
        )
    assert declared is not None


def test_execution_items_derived_from_calls_cannot_be_overridden():
    task = host_task("no-item-override")
    workflow = actor_plan(task, include_set=False)
    session = AcceptanceGuide().start(task, workflow)
    stage_id = workflow.stage_requests[0].stage_id

    with pytest.raises(WorkflowError, match="cannot be overridden"):
        session.record_execution_item(
            stage_id,
            ExecutionItemResult(item_id=f"{stage_id}.executed", status=CheckStatus.PASS),
        )


def test_a_call_from_a_later_dependent_stage_cannot_run_early():
    task = host_task("stage-order")
    first = stage_spec("stage.first", "First", "read", (call("ue5", "get_actor_transform", "c1"),))
    second = stage_spec(
        "stage.second",
        "Second",
        "write",
        (call("ue5", "set_actor_transform", "c2"),),
        depends_on=("stage.first",),
    )
    workflow = workflow_for(task, (WorkflowStep("work", "Two stages", (first, second)),))
    session = AcceptanceGuide().start(task, workflow)

    with pytest.raises(WorkflowError, match="incomplete dependencies"):
        submit_call_result(session, second.calls[0])


def test_closing_a_stage_out_of_order_is_blocked_not_silently_allowed():
    task = host_task("close-order")
    first = stage_spec("stage.first", "First", "read", (call("ue5", "get_actor_transform", "c1"),))
    second = stage_spec(
        "stage.second",
        "Second",
        "write",
        (call("ue5", "set_actor_transform", "c2"),),
        depends_on=("stage.first",),
    )
    workflow = workflow_for(task, (WorkflowStep("work", "Two stages", (first, second)),))
    session = AcceptanceGuide().start(task, workflow)

    result = session.complete_stage("stage.second")

    assert result.status is TaskStatus.BLOCKED
    assert "depends on incomplete Stages" in result.errors[0]
