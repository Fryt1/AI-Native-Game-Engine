"""Stage acceptance: what the Agent reports is what gets judged."""

from __future__ import annotations

from dataclasses import replace

import pytest

from ainative.model import (
    AcceptanceCheck,
    CheckOperator,
    CheckResult,
    CheckStatus,
    ExecutionChecklistItem,
    ExecutionItemResult,
    StageKind,
    StageRequest,
    TaskContract,
    TaskRoute,
    TaskStatus,
    WorkflowStep,
)
from ainative.reading import WorkflowIntegrityError, validate_workflow_structure
from ainative.session_api import AcceptanceGuide, WorkflowError
from tests.support.workflow_factory import call, submit_call_result, workflow_for


def _task(task_id: str) -> TaskContract:
    return TaskContract(
        task_id=task_id,
        objective="Move and verify an Actor through UE5 MCP",
        route=TaskRoute.HOST_OPERATION,
    )


def test_a_successful_call_does_not_complete_a_stage_without_acceptance_evidence():
    """The core promise of the whole repository."""

    task = _task("missing-acceptance-evidence")
    mutate = call("ue5", "set_actor_transform", "mutate-1", {"location": [1, 2, 3]})
    stage = StageRequest(
        stage_id="stage.change",
        purpose="Move the Actor",
        operation="set_actor_transform",
        calls=(mutate,),
        stage_kind=StageKind.CHANGE,
        execution_checklist=(
            ExecutionChecklistItem("mutation_called", "The mutation ran", call_ids=(mutate.call_id,)),
        ),
        acceptance_checklist=(
            AcceptanceCheck(
                "location_verified",
                "The final location matches the requested location",
                operator=CheckOperator.MANUAL,
            ),
        ),
    )
    workflow = workflow_for(task, (WorkflowStep("change", "Change", (stage,)),))
    session = AcceptanceGuide().start(task, workflow)

    mutate_result = submit_call_result(session, mutate, TaskStatus.SUCCEEDED)
    assert mutate_result.status is TaskStatus.SUCCEEDED
    result = session.complete_stage("stage.change")

    assert result.status is TaskStatus.BLOCKED
    assert result.execution_item_results[0].status is CheckStatus.PASS
    assert result.check_results[0].status is CheckStatus.UNKNOWN
    assert "stage.change" not in session.completed_stage_ids


def test_a_readback_call_deterministically_completes_the_stage():
    task = _task("readback-acceptance")
    mutate = call("ue5", "set_actor_transform", "mutate-1", {"location": [1, 2, 3]})
    readback = call("ue5", "read_actor_transform", "verify-1", depends_on=(mutate.call_id,))
    stage = StageRequest(
        stage_id="stage.change",
        purpose="Move and verify the Actor",
        operation="actor_transform",
        calls=(mutate, readback),
        stage_kind=StageKind.CHANGE,
        execution_checklist=(
            ExecutionChecklistItem("mutation_called", "The mutation ran", call_ids=(mutate.call_id,)),
        ),
        acceptance_checklist=(
            AcceptanceCheck(
                "location_matches",
                "Read-back location equals the requested location",
                source_call_id=readback.call_id,
                actual_path=("location",),
                operator=CheckOperator.EQUALS,
                expected=[1, 2, 3],
            ),
        ),
    )
    workflow = workflow_for(task, (WorkflowStep("change", "Change", (stage,)),))
    session = AcceptanceGuide().start(task, workflow)

    submit_call_result(session, mutate, TaskStatus.SUCCEEDED)
    submit_call_result(session, readback, TaskStatus.SUCCEEDED, outputs={"location": [1, 2, 3]})
    result = session.complete_stage("stage.change")

    assert result.status is TaskStatus.SUCCEEDED
    assert result.check_results[0].status is CheckStatus.PASS
    assert result.acceptance_summary.passed == 1
    assert session.finish().status is TaskStatus.SUCCEEDED


def test_a_mismatched_readback_fails_the_stage():
    task = _task("readback-mismatch")
    mutate = call("ue5", "set_actor_transform", "mutate-1", {"location": [1, 2, 3]})
    readback = call("ue5", "read_actor_transform", "verify-1", depends_on=(mutate.call_id,))
    stage = StageRequest(
        stage_id="stage.change",
        purpose="Move and verify",
        calls=(mutate, readback),
        execution_checklist=(
            ExecutionChecklistItem("mutation_called", "The mutation ran", call_ids=(mutate.call_id,)),
        ),
        acceptance_checklist=(
            AcceptanceCheck(
                "location_matches",
                "Read-back location equals the requested location",
                source_call_id=readback.call_id,
                actual_path=("location",),
                operator=CheckOperator.EQUALS,
                expected=[1, 2, 3],
            ),
        ),
    )
    workflow = workflow_for(task, (WorkflowStep("change", "Change", (stage,)),))
    session = AcceptanceGuide().start(task, workflow)

    submit_call_result(session, mutate, TaskStatus.SUCCEEDED)
    submit_call_result(session, readback, TaskStatus.SUCCEEDED, outputs={"location": [9, 9, 9]})
    result = session.complete_stage("stage.change")

    assert result.check_results[0].status is CheckStatus.FAIL
    assert result.status is TaskStatus.FAILED


def test_a_degraded_call_marks_the_required_check_as_warning():
    task = _task("warn-acceptance")
    observe = call("ue5", "read_actor_transform", "observe-1")
    stage = StageRequest(
        stage_id="stage.inspect",
        purpose="Inspect the Actor",
        operation="read_actor_transform",
        calls=(observe,),
        stage_kind=StageKind.INVESTIGATION,
        execution_checklist=(
            ExecutionChecklistItem("state_read", "The state was read", call_ids=(observe.call_id,)),
        ),
        acceptance_checklist=(
            AcceptanceCheck(
                "read_completed",
                "The read call completed",
                source_call_id=observe.call_id,
                operator=CheckOperator.TOOL_SUCCEEDED,
            ),
        ),
    )
    workflow = workflow_for(task, (WorkflowStep("inspect", "Inspect", (stage,)),))
    session = AcceptanceGuide().start(task, workflow)

    submit_call_result(session, observe, TaskStatus.DEGRADED, warnings=("non-blocking warning",))
    stage_result = session.complete_stage("stage.inspect")

    assert stage_result.status is TaskStatus.DEGRADED
    assert stage_result.check_results[0].status is CheckStatus.WARN
    assert session.finish().status is TaskStatus.DEGRADED


def test_a_required_stage_must_freeze_both_checklists():
    task = _task("missing-checklists")
    selected = call("ue5", "read_actor_transform", "read-1")
    workflow = workflow_for(
        task,
        (WorkflowStep("inspect", "Inspect", (StageRequest("stage.inspect", "Inspect", "read", (selected,)),)),),
    )

    with pytest.raises(WorkflowIntegrityError) as caught:
        validate_workflow_structure(workflow)

    locations = {issue.location for issue in caught.value.issues}
    assert "stage:stage.inspect.execution_checklist" in locations
    assert "stage:stage.inspect.acceptance_checklist" in locations


def test_the_agent_cannot_override_a_deterministic_acceptance_check():
    task = _task("no-check-override")
    observe = call("ue5", "read_actor_transform", "verify-1")
    stage = StageRequest(
        stage_id="stage.verify",
        purpose="Verify the Actor",
        calls=(observe,),
        stage_kind=StageKind.INVESTIGATION,
        execution_checklist=(
            ExecutionChecklistItem("read", "Read the Actor", call_ids=(observe.call_id,)),
        ),
        acceptance_checklist=(
            AcceptanceCheck(
                "location",
                "Location matches",
                source_call_id=observe.call_id,
                operator=CheckOperator.EQUALS,
                actual_path=("location",),
                expected=[0, 0, 0],
            ),
        ),
    )
    session = AcceptanceGuide().start(task, workflow_for(task, (WorkflowStep("verify", "Verify", (stage,)),)))

    with pytest.raises(WorkflowError, match="cannot be overridden"):
        session.record_check_result(
            "stage.verify",
            CheckResult("location", CheckStatus.PASS, evidence_refs=("invented",)),
        )


def test_the_agent_cannot_override_call_backed_execution_evidence():
    task = _task("no-execution-override")
    mutate = call("ue5", "set_actor_transform", "mutate-1", {"location": [1, 2, 3]})
    stage = StageRequest(
        stage_id="stage.change",
        purpose="Change the Actor",
        calls=(mutate,),
        execution_checklist=(
            ExecutionChecklistItem("mutation", "Mutation ran", call_ids=(mutate.call_id,)),
        ),
        acceptance_checklist=(
            AcceptanceCheck(
                "mutation_call",
                "Mutation call completed",
                source_call_id=mutate.call_id,
                operator=CheckOperator.TOOL_SUCCEEDED,
            ),
        ),
    )
    session = AcceptanceGuide().start(task, workflow_for(task, (WorkflowStep("change", "Change", (stage,)),)))

    with pytest.raises(WorkflowError, match="cannot be overridden"):
        session.record_execution_item(
            "stage.change",
            ExecutionItemResult("mutation", CheckStatus.PASS, evidence_refs=("invented",)),
        )


def test_a_manual_check_may_be_recorded_by_the_agent_with_evidence():
    task = _task("manual-check")
    stage = StageRequest(
        stage_id="stage.review",
        purpose="Human review",
        stage_kind=StageKind.INVESTIGATION,
        calls=(),
        execution_checklist=(
            ExecutionChecklistItem("reviewed", "A human reviewed the result", call_ids=(), evidence_required=False),
        ),
        acceptance_checklist=(
            AcceptanceCheck("approved", "The result was approved", operator=CheckOperator.MANUAL),
        ),
    )
    session = AcceptanceGuide().start(task, workflow_for(task, (WorkflowStep("review", "Review", (stage,)),)))

    session.record_execution_item(
        "stage.review",
        ExecutionItemResult("reviewed", CheckStatus.PASS, evidence_refs=("human-review:run-1",)),
    )
    session.record_check_result(
        "stage.review",
        CheckResult("approved", CheckStatus.PASS, evidence_refs=("human-review:run-1",)),
    )

    assert session.complete_stage("stage.review").status is TaskStatus.SUCCEEDED


def test_completing_a_stage_twice_returns_the_recorded_result():
    task = _task("idempotent-stage")
    read = call("ue5", "read_actor_transform", "read-1")
    stage = StageRequest(
        stage_id="stage.read",
        purpose="Read",
        calls=(read,),
        execution_checklist=(ExecutionChecklistItem("read", "Read", call_ids=(read.call_id,)),),
        acceptance_checklist=(
            AcceptanceCheck(
                "read_ok",
                "Read completed",
                source_call_id=read.call_id,
                operator=CheckOperator.TOOL_SUCCEEDED,
            ),
        ),
    )
    session = AcceptanceGuide().start(task, workflow_for(task, (WorkflowStep("read", "Read", (stage,)),)))
    submit_call_result(session, read, TaskStatus.SUCCEEDED)

    first = session.complete_stage("stage.read")
    second = session.complete_stage("stage.read")

    assert first == second
    assert first.status is TaskStatus.SUCCEEDED


def test_recording_new_evidence_reopens_a_closed_stage():
    task = _task("reopen-stage")
    read = call("ue5", "read_actor_transform", "read-1")
    stage = StageRequest(
        stage_id="stage.read",
        purpose="Read",
        calls=(read,),
        execution_checklist=(ExecutionChecklistItem("read", "Read", call_ids=(read.call_id,)),),
        acceptance_checklist=(
            AcceptanceCheck(
                "read_ok",
                "Read completed",
                source_call_id=read.call_id,
                operator=CheckOperator.TOOL_SUCCEEDED,
            ),
        ),
    )
    workflow = workflow_for(task, (WorkflowStep("read", "Read", (stage,)),))
    session = AcceptanceGuide().start(task, workflow)
    submit_call_result(session, read, TaskStatus.SUCCEEDED)
    assert session.complete_stage("stage.read").status is TaskStatus.SUCCEEDED

    # A later Stage's evidence must not leave the earlier verdict stale.
    later = call("ue5", "save_level", "save-1")
    extended = replace(
        workflow.steps[0].stages[0],
        calls=(read, later),
    )
    assert extended.calls[1].call_id == "save-1"
    assert session.completed_stage_ids == ("stage.read",)
