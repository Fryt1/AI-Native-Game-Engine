"""Open an Agent-authored Workflow: verify the Skill, then admit the Workflow.

This is the entry point of the acceptance loop. It checks everything that can be
checked before a single call runs, so a Stage never starts against a Workflow
that cannot be judged:

    the Skill package is intact and the named guidance resolves
    the Workflow revision is still executable
    the Workflow is structurally valid
    the entry gate passes
"""

from __future__ import annotations

from ainative.acceptance.confirmation import confirmation_gate
from ainative.model.task import TaskContract
from ainative.model.tree import WorkflowStatus, WorkflowTree
from ainative.reading import TreeIntegrityError, validate_tree_structure

from .errors import WorkflowError
from .session import AcceptanceSession
from .skill import AINativeSkill, SkillSession

# A revision in one of these states is finished; opening it again would mean
# judging a Workflow whose outcome is already decided.
_TERMINAL_WORKFLOW_STATUSES = frozenset({
    WorkflowStatus.COMPLETED,
    WorkflowStatus.FAILED,
    WorkflowStatus.INVALID,
    WorkflowStatus.SUPERSEDED,
})


def _reject_unexecutable_revision(workflow: WorkflowTree) -> None:
    """Refuse to open a Workflow revision that is no longer executable.

    @param workflow: the Agent-authored Workflow.
    @throws WorkflowError when the revision already reached a terminal state.
    """

    if workflow.status in _TERMINAL_WORKFLOW_STATUSES:
        raise WorkflowError(
            f"Workflow revision {workflow.revision_id} is not executable "
            f"in status {workflow.status.value}"
        )


class AcceptanceGuide:
    """Loads Skill guidance and opens a validation-only AcceptanceSession."""

    def __init__(self, skill: AINativeSkill | None = None) -> None:
        self.skill = skill or AINativeSkill()

    def load_skill(self, task: TaskContract) -> SkillSession:
        return self.skill.load(task)

    def start(self, task: TaskContract, workflow: WorkflowTree) -> AcceptanceSession:
        """Open an Agent-authored Workflow for structured validation and recording.

        @param task: the Agent-authored task contract.
        @param workflow: the Agent-authored Workflow, already deserialized.
        @returns a session ready to record evidence and evaluate nodes.
        @throws WorkflowError when the Workflow cannot be opened.
        """

        skill_session = self.load_skill(task)
        _reject_unexecutable_revision(workflow)
        try:
            validate_tree_structure(workflow)
        except TreeIntegrityError as exc:
            raise WorkflowError(str(exc)) from exc
        return AcceptanceSession(
            skill=skill_session,
            task=task,
            workflow=workflow,
            gate=confirmation_gate(task),
        )
