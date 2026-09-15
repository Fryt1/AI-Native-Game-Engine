"""Deterministic aggregation: Stage results in, one Task verdict out.

Pure functions. They read no session state and mutate nothing, so the decision
ladder can be read and tested on its own instead of being buried in the session's
`finish()`.
"""

from __future__ import annotations

from ainative.model.results import TaskStatus
from ainative.model.workflow import WorkflowStatus

# Priority order for Stage outcomes. The first status present wins, so a single
# needs_approval outranks any number of failures: a human decision blocks the task
# harder than a retryable failure does.
_STATUS_PRIORITY = (
    TaskStatus.NEEDS_APPROVAL,
    TaskStatus.FAILED,
    TaskStatus.BLOCKED,
)


def aggregate_task_status(
    *,
    gate_ready: bool,
    stage_statuses: frozenset[TaskStatus],
    required_stages: frozenset[str],
    completed_stages: frozenset[str],
) -> tuple[TaskStatus, WorkflowStatus]:
    """Decide the Task and Workflow status from the closed Stages.

    @param gate_ready: whether the entry gate let the run start.
    @param stage_statuses: the outcome of every Stage closed so far.
    @param required_stages: Stage ids the Workflow marked required.
    @param completed_stages: Stage ids that reached succeeded or degraded.
    @returns the Task status and the matching Workflow status.
    """

    if not gate_ready:
        return TaskStatus.BLOCKED, WorkflowStatus.SUSPENDED

    for status in _STATUS_PRIORITY:
        if status in stage_statuses:
            return status, WorkflowStatus.SUSPENDED

    if required_stages - completed_stages:
        return TaskStatus.BLOCKED, WorkflowStatus.RUNNING

    if TaskStatus.DEGRADED in stage_statuses:
        return TaskStatus.DEGRADED, WorkflowStatus.COMPLETED

    return TaskStatus.SUCCEEDED, WorkflowStatus.COMPLETED


def outstanding_stages(
    *,
    required_stages: frozenset[str],
    completed_stages: frozenset[str],
) -> tuple[str, ...]:
    """Return the required Stage ids that have not been closed, in sorted order.

    A blocked Task tells the Agent that something is missing. Naming the Stages is
    what lets it act without re-reading the Workflow it authored.

    @param required_stages: Stage ids the Workflow marked required.
    @param completed_stages: Stage ids that reached succeeded or degraded.
    @returns the ids still outstanding.
    """

    return tuple(sorted(required_stages - completed_stages))


def next_action_for(status: TaskStatus, *, gate_ready: bool) -> str | None:
    """State what the Agent should do next, or None when the task is done.

    @param status: the aggregated Task status.
    @param gate_ready: whether the entry gate let the run start.
    @returns one instruction, or None when nothing remains.
    """

    if status is TaskStatus.BLOCKED:
        if not gate_ready:
            return "Agent should repair the Workflow or entry gate before executing"
        return "Agent should collect missing checklist evidence before continuing"
    if status is TaskStatus.NEEDS_APPROVAL:
        return "Agent should obtain the required human decision"
    if status is TaskStatus.FAILED:
        return "Agent should retry the selected call or author a new Workflow revision"
    return None
