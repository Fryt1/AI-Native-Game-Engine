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


def test_every_workflow_status_either_has_a_producer_or_a_reader():
    """A status value must be one the engine writes or one it acts on.

    `WorkflowStatus` has two readers asking different questions: `guide.py` refuses
    to reopen a terminal revision, and this module's `aggregate_task_status`
    produces the three that reach `TaskResult.workflow_status`. A value is justified
    by either half:

    * produced -- the engine emits it, as aggregation does for running, suspended,
      and completed;
    * read -- the engine branches on it, as `guide.py` does for completed, failed,
      invalid, and superseded, which an author declares and the engine honours by
      refusing to reopen;
    * or a default, like draft.

    `feasible` had none of the three: no code wrote it, no branch read it. An author
    could declare a revision feasible and the engine would treat it as an unnamed
    draft. It was removed, and this test is derived from the enum so a new value
    forces the question rather than passing by default.
    """

    import re
    from pathlib import Path

    repo = Path(__file__).resolve().parents[3]
    sources = "\n".join(
        path.read_text(encoding="utf-8") for path in (repo / "src").rglob("*.py"))

    unjustified = []
    for member in WorkflowStatus:
        name = member.name
        produced = re.search(rf"status\s*=\s*\w*\.?{name}\b", sources)
        returned = re.search(rf"return\s+[^\n]*WorkflowStatus\.{name}\b", sources)
        default = re.search(rf"=\s*WorkflowStatus\.{name}\b", sources)
        # Read: named inside a frozenset, tuple, or comparison the engine branches on.
        read = re.search(rf"WorkflowStatus\.{name}\b", sources) and not (
            produced or returned)
        if not (produced or returned or default or read):
            unjustified.append(member.value)

    assert not unjustified, (
        f"WorkflowStatus declares {unjustified}, which nothing produces and nothing "
        "reads: an author could choose them and the engine would never emit them")
