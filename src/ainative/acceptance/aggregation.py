"""Deterministic aggregation: node results in, one Task verdict out.

Pure functions. They read no session state and mutate nothing, so the decision
ladder can be read and tested on its own instead of being buried in the session's
`finish()`.

Nodes are named by **path**, not by a bare id: a ``node_id`` is unique only among
siblings, so the path is what identifies one subtree's ``mass`` from another's.
"""

from __future__ import annotations

from ainative.model.results import TaskStatus
from ainative.model.tree import WorkflowStatus

# Priority order for node outcomes. The first status present wins, so a single
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
    node_statuses: frozenset[TaskStatus],
    required_paths: frozenset[str],
    completed_paths: frozenset[str],
) -> tuple[TaskStatus, WorkflowStatus]:
    """Decide the Task and Workflow status from the closed nodes.

    @param gate_ready: whether the entry gate let the run start.
    @param node_statuses: the outcome of every node closed so far.
    @param required_paths: paths of the nodes the Workflow marked required.
    @param completed_paths: paths that reached succeeded or degraded.
    @returns the Task status and the matching Workflow status.
    """

    if not gate_ready:
        return TaskStatus.BLOCKED, WorkflowStatus.SUSPENDED

    for status in _STATUS_PRIORITY:
        if status in node_statuses:
            return status, WorkflowStatus.SUSPENDED

    if required_paths - completed_paths:
        return TaskStatus.BLOCKED, WorkflowStatus.RUNNING

    if TaskStatus.DEGRADED in node_statuses:
        return TaskStatus.DEGRADED, WorkflowStatus.COMPLETED

    return TaskStatus.SUCCEEDED, WorkflowStatus.COMPLETED


def outstanding_nodes(
    *,
    required_paths: frozenset[str],
    completed_paths: frozenset[str],
) -> tuple[str, ...]:
    """Return the required node paths that have not been closed, in sorted order.

    A blocked Task tells the Agent that something is missing. Naming the paths is
    what lets it act without re-reading the Workflow it authored.

    @param required_paths: paths the Workflow marked required.
    @param completed_paths: paths that reached succeeded or degraded.
    @returns the paths still outstanding.
    """

    return tuple(sorted(required_paths - completed_paths))


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
