"""The aggregation ladder, tested on its own.

These functions decide the Task and Workflow status from the closed Stages. They
were previously buried in `AcceptanceSession.finish()`, testable only by driving
a whole session. Now the ladder is a pure function, so the priority order can be
pinned directly -- including the cases a session test would find awkward, such as
needs_approval outranking failed.
"""

import pytest

from ainative.acceptance import aggregate_task_status, next_action_for
from ainative.model.results import TaskStatus
from ainative.model.tree import WorkflowStatus

REQUIRED = frozenset({"/workflow/work/stage.a/"})
DONE = frozenset({"/workflow/work/stage.a/"})


def decide(statuses, *, gate_ready=True, required=REQUIRED, completed=DONE):
    return aggregate_task_status(
        gate_ready=gate_ready,
        node_statuses=frozenset(statuses),
        required_paths=required,
        completed_paths=completed,
    )


def test_all_required_stages_closed_succeeds():
    assert decide({TaskStatus.SUCCEEDED}) == (TaskStatus.SUCCEEDED, WorkflowStatus.COMPLETED)


def test_a_warning_only_outcome_degrades_rather_than_fails():
    assert decide({TaskStatus.SUCCEEDED, TaskStatus.DEGRADED}) == (
        TaskStatus.DEGRADED,
        WorkflowStatus.COMPLETED,
    )


def test_an_unclosed_required_stage_blocks_and_keeps_the_workflow_running():
    assert decide({TaskStatus.SUCCEEDED}, completed=frozenset()) == (
        TaskStatus.BLOCKED,
        WorkflowStatus.RUNNING,
    )


def test_a_failed_stage_suspends_the_workflow():
    assert decide({TaskStatus.FAILED}) == (TaskStatus.FAILED, WorkflowStatus.SUSPENDED)


def test_needs_approval_outranks_a_failure():
    """A pending human decision is not a retryable failure, so it wins."""

    assert decide({TaskStatus.FAILED, TaskStatus.NEEDS_APPROVAL}) == (
        TaskStatus.NEEDS_APPROVAL,
        WorkflowStatus.SUSPENDED,
    )


def test_needs_approval_outranks_blocked_too():
    assert decide({TaskStatus.BLOCKED, TaskStatus.NEEDS_APPROVAL}) == (
        TaskStatus.NEEDS_APPROVAL,
        WorkflowStatus.SUSPENDED,
    )


def test_failed_outranks_blocked():
    assert decide({TaskStatus.BLOCKED, TaskStatus.FAILED}) == (
        TaskStatus.FAILED,
        WorkflowStatus.SUSPENDED,
    )


def test_an_unready_gate_blocks_before_any_stage_is_considered():
    """The gate is checked first: a closed, passing Stage cannot override it."""

    assert decide({TaskStatus.SUCCEEDED}, gate_ready=False) == (
        TaskStatus.BLOCKED,
        WorkflowStatus.SUSPENDED,
    )


def test_no_stages_closed_but_none_required_succeeds():
    assert decide(set(), required=frozenset(), completed=frozenset()) == (
        TaskStatus.SUCCEEDED,
        WorkflowStatus.COMPLETED,
    )


@pytest.mark.parametrize(
    ("status", "gate_ready", "expected"),
    [
        (TaskStatus.BLOCKED, False, "repair the Workflow or entry gate"),
        (TaskStatus.BLOCKED, True, "collect missing checklist evidence"),
        (TaskStatus.NEEDS_APPROVAL, True, "obtain the required human decision"),
        (TaskStatus.FAILED, True, "retry the selected call"),
        (TaskStatus.SUCCEEDED, True, None),
        (TaskStatus.DEGRADED, True, None),
    ],
)
def test_next_action_matches_the_status(status, gate_ready, expected):
    action = next_action_for(status, gate_ready=gate_ready)

    if expected is None:
        assert action is None
    else:
        assert action is not None
        assert expected in action
