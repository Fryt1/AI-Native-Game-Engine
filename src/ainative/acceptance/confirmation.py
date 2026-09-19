"""A route is a label, plus a confirmation precondition.

A route names the primary lifecycle of a task. That is all it is: a label the
Workflow carries so the record shows which lifecycle it followed. It is *not* a
behavioral branch — every route contributes the same context, and this module
used to model that sameness with three byte-identical authority objects. They
are gone.

The one precondition this module does observe is the task's own confirmation
requirement, which is independent of the route.
"""

from __future__ import annotations

from ainative.model.task import TaskContract
from ainative.model.tree import GateResult


def confirmation_gate(task: TaskContract) -> GateResult:
    """Return the gate result for the task's confirmation requirement.

    @param task: the task being planned.
    @returns a passing gate, or a blocking one that names the missing decision.
    """

    if not task.confirmation_required:
        return GateResult(True)
    reason = str(task.metadata.get("clarification_reason", "task intent requires confirmation"))
    return GateResult(
        False,
        (f"Task intent requires confirmation: {reason}",),
        next_action="clarify the target host, direction, or requested lifecycle and create a revised TaskContract",
    )
