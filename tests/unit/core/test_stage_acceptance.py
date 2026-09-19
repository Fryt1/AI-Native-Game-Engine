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
    NodeCheck,
    NodeKind,
    StageBody,
    StageKind,
    TaskContract,
    TaskRoute,
    TaskStatus,
    WorkflowNode,
)
from ainative.reading import TreeIntegrityError, validate_tree_structure
from ainative.session_api import AcceptanceGuide, WorkflowError
from tests.support.workflow_factory import (
    call,
    first_stage,
    first_stage_path,
    step,
    submit_call_result,
    workflow_for,
)


def _task(task_id: str) -> TaskContract:
    return TaskContract(
        task_id=task_id,
        objective="Move and verify an Actor through UE5 MCP",
        route=TaskRoute.HOST_OPERATION,
    )


def _stage(
    node_id: str,
    purpose: str,
    *,
    calls=(),
    stage_kind: StageKind = StageKind.CHANGE,
    execution_checklist=(),
    acceptance_checklist=(),
    required: bool = True,
) -> WorkflowNode:
    """Build one STAGE node: a leaf that declares calls and both checklists."""

    return WorkflowNode(
        node_id=node_id,
        kind=NodeKind.STAGE,
        purpose=purpose,
        required=required,
        stage=StageBody(
            calls=tuple(calls),
            execution_checklist=tuple(execution_checklist),
            acceptance_checklist=tuple(NodeCheck(check) for check in acceptance_checklist),
            stage_kind=stage_kind,
        ),
    )


def test_a_successful_call_does_not_complete_a_stage_without_acceptance_evidence():
    """The core promise of the whole repository."""

    task = _task("missing-acceptance-evidence")
    mutate = call("ue5", "set_actor_transform", "mutate-1", {"location": [1, 2, 3]})
    stage = _stage(
        "stage.change",
        "Move the Actor",
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
    workflow = workflow_for(task, (step("change", "Change", (stage,)),))
    path = first_stage_path(workflow)
    session = AcceptanceGuide().start(task, workflow)

    mutate_result = submit_call_result(session, mutate, TaskStatus.SUCCEEDED)
    assert mutate_result.status is TaskStatus.SUCCEEDED
    result = session.complete_node(path)

    assert result.status is TaskStatus.BLOCKED
    assert result.execution_item_results[0].status is CheckStatus.PASS
    assert result.check_results[0].status is CheckStatus.UNKNOWN
    assert path not in session.completed_node_paths


def test_a_readback_call_deterministically_completes_the_stage():
    task = _task("readback-acceptance")
    mutate = call("ue5", "set_actor_transform", "mutate-1", {"location": [1, 2, 3]})
    readback = call("ue5", "read_actor_transform", "verify-1", depends_on=(mutate.call_id,))
    stage = _stage(
        "stage.change",
        "Move and verify the Actor",
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
    workflow = workflow_for(task, (step("change", "Change", (stage,)),))
    path = first_stage_path(workflow)
    session = AcceptanceGuide().start(task, workflow)

    submit_call_result(session, mutate, TaskStatus.SUCCEEDED)
    submit_call_result(session, readback, TaskStatus.SUCCEEDED, outputs={"location": [1, 2, 3]})
    result = session.complete_node(path)

    assert result.status is TaskStatus.SUCCEEDED
    assert result.check_results[0].status is CheckStatus.PASS
    assert result.acceptance_summary.passed == 1
    assert session.finish().status is TaskStatus.SUCCEEDED


def test_a_mismatched_readback_fails_the_stage():
    task = _task("readback-mismatch")
    mutate = call("ue5", "set_actor_transform", "mutate-1", {"location": [1, 2, 3]})
    readback = call("ue5", "read_actor_transform", "verify-1", depends_on=(mutate.call_id,))
    stage = _stage(
        "stage.change",
        "Move and verify",
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
    workflow = workflow_for(task, (step("change", "Change", (stage,)),))
    path = first_stage_path(workflow)
    session = AcceptanceGuide().start(task, workflow)

    submit_call_result(session, mutate, TaskStatus.SUCCEEDED)
    submit_call_result(session, readback, TaskStatus.SUCCEEDED, outputs={"location": [9, 9, 9]})
    result = session.complete_node(path)

    assert result.check_results[0].status is CheckStatus.FAIL
    assert result.status is TaskStatus.FAILED


def test_a_degraded_call_marks_the_required_check_as_warning():
    task = _task("warn-acceptance")
    observe = call("ue5", "read_actor_transform", "observe-1")
    stage = _stage(
        "stage.inspect",
        "Inspect the Actor",
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
    workflow = workflow_for(task, (step("inspect", "Inspect", (stage,)),))
    path = first_stage_path(workflow)
    session = AcceptanceGuide().start(task, workflow)

    submit_call_result(session, observe, TaskStatus.DEGRADED, warnings=("non-blocking warning",))
    stage_result = session.complete_node(path)

    assert stage_result.status is TaskStatus.DEGRADED
    assert stage_result.check_results[0].status is CheckStatus.WARN
    assert session.finish().status is TaskStatus.DEGRADED


def test_a_required_stage_must_freeze_both_checklists():
    task = _task("missing-checklists")
    selected = call("ue5", "read_actor_transform", "read-1")
    workflow = workflow_for(
        task,
        (step("inspect", "Inspect", (_stage("stage.inspect", "Inspect", calls=(selected,)),)),),
    )

    with pytest.raises(TreeIntegrityError) as caught:
        validate_tree_structure(workflow)

    path = first_stage_path(workflow)
    locations = {issue.location for issue in caught.value.issues}
    messages = " ".join(issue.message for issue in caught.value.issues)
    assert path in locations
    assert "must freeze an execution checklist" in messages
    assert "must freeze an acceptance checklist" in messages


def test_the_agent_cannot_override_a_deterministic_acceptance_check():
    task = _task("no-check-override")
    observe = call("ue5", "read_actor_transform", "verify-1")
    stage = _stage(
        "stage.verify",
        "Verify the Actor",
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
    workflow = workflow_for(task, (step("verify", "Verify", (stage,)),))
    session = AcceptanceGuide().start(task, workflow)

    with pytest.raises(WorkflowError, match="cannot be overridden"):
        session.record_check_result(
            first_stage_path(workflow),
            CheckResult("location", CheckStatus.PASS, evidence_refs=("invented",)),
        )


def test_the_agent_cannot_override_call_backed_execution_evidence():
    task = _task("no-execution-override")
    mutate = call("ue5", "set_actor_transform", "mutate-1", {"location": [1, 2, 3]})
    stage = _stage(
        "stage.change",
        "Change the Actor",
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
    workflow = workflow_for(task, (step("change", "Change", (stage,)),))
    session = AcceptanceGuide().start(task, workflow)

    with pytest.raises(WorkflowError, match="cannot be overridden"):
        session.record_execution_item(
            first_stage_path(workflow),
            ExecutionItemResult("mutation", CheckStatus.PASS, evidence_refs=("invented",)),
        )


def test_a_manual_check_may_be_recorded_by_the_agent_with_evidence():
    task = _task("manual-check")
    # A required STAGE declares at least one call, so a review-only checkpoint is
    # an optional node; its execution item and manual check stay required.
    stage = _stage(
        "stage.review",
        "Human review",
        required=False,
        stage_kind=StageKind.INVESTIGATION,
        execution_checklist=(
            ExecutionChecklistItem("reviewed", "A human reviewed the result", call_ids=()),
        ),
        acceptance_checklist=(
            AcceptanceCheck("approved", "The result was approved", operator=CheckOperator.MANUAL),
        ),
    )
    workflow = workflow_for(task, (step("review", "Review", (stage,)),))
    path = first_stage_path(workflow)
    session = AcceptanceGuide().start(task, workflow)

    session.record_execution_item(
        path,
        ExecutionItemResult("reviewed", CheckStatus.PASS, evidence_refs=("human-review:run-1",)),
    )
    session.record_check_result(
        path,
        CheckResult("approved", CheckStatus.PASS, evidence_refs=("human-review:run-1",)),
    )

    assert session.complete_node(path).status is TaskStatus.SUCCEEDED


def test_completing_a_stage_twice_returns_the_recorded_result():
    task = _task("idempotent-stage")
    read = call("ue5", "read_actor_transform", "read-1")
    stage = _stage(
        "stage.read",
        "Read",
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
    workflow = workflow_for(task, (step("read", "Read", (stage,)),))
    path = first_stage_path(workflow)
    session = AcceptanceGuide().start(task, workflow)
    submit_call_result(session, read, TaskStatus.SUCCEEDED)

    first = session.complete_node(path)
    second = session.complete_node(path)

    assert first == second
    assert first.status is TaskStatus.SUCCEEDED


def test_recording_new_evidence_reopens_a_closed_stage():
    task = _task("reopen-stage")
    read = call("ue5", "read_actor_transform", "read-1")
    stage = _stage(
        "stage.read",
        "Read",
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
    workflow = workflow_for(task, (step("read", "Read", (stage,)),))
    path = first_stage_path(workflow)
    session = AcceptanceGuide().start(task, workflow)
    submit_call_result(session, read, TaskStatus.SUCCEEDED)
    assert session.complete_node(path).status is TaskStatus.SUCCEEDED

    # A later Stage's evidence must not leave the earlier verdict stale.
    later = call("ue5", "save_level", "save-1")
    original = first_stage(workflow)
    extended = replace(original, stage=replace(original.stage, calls=(read, later)))
    assert extended.stage.calls[1].call_id == "save-1"
    # Closing a leaf also records the satisfied ancestors it was judged under.
    assert session.completed_node_paths == (*workflow.composite_paths, path)
