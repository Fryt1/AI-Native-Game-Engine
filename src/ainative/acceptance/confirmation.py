"""The entry gate: one precondition, and it is the task's own.

A task may declare that it needs confirmation before work starts. That is the only
thing this gate observes, and it is independent of everything else the task carries.

The module used to model a `route` as a second precondition. A route was never a
behavioral branch -- every route contributed the same context, and three
byte-identical authority objects existed to express that sameness. They are gone,
along with the route itself: the entry gate compared `workflow.route` against
`task.route` and nothing else read either value, so a field whose only purpose was
to equal another field was removed rather than kept as a label.
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
