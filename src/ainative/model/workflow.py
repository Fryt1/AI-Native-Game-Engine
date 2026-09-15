from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .checklists import AcceptanceCheck, ExecutionChecklistItem, StageKind
from .coercion import coerce_enum
from .task import TaskRoute
from .tools import ToolCall


class WorkflowStatus(StrEnum):
    """Lifecycle state of one immutable Workflow revision."""

    DRAFT = "draft"
    FEASIBLE = "feasible"
    RUNNING = "running"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"
    INVALID = "invalid"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class StageRequest:
    """One Agent-defined local goal with frozen execution and acceptance.

    ``operation`` is a human-readable label. The checklists define required work
    and proof; only explicit ``calls`` execute external operations.
    """

    stage_id: str
    purpose: str
    operation: str = ""
    calls: tuple[ToolCall, ...] = ()
    stage_kind: StageKind = StageKind.CHANGE
    execution_checklist: tuple[ExecutionChecklistItem, ...] = ()
    acceptance_checklist: tuple[AcceptanceCheck, ...] = ()
    depends_on: tuple[str, ...] = ()
    required: bool = True
    recovery: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "purpose": self.purpose,
            "operation": self.operation,
            "stage_kind": self.stage_kind.value,
            "execution_checklist": [item.to_dict() for item in self.execution_checklist],
            "acceptance_checklist": [check.to_dict() for check in self.acceptance_checklist],
            "calls": [call.to_dict() for call in self.calls],
            "depends_on": list(self.depends_on),
            "required": self.required,
            "recovery": self.recovery,
        }

    def __post_init__(self) -> None:
        coerce_enum(self, "stage_kind", StageKind)

@dataclass(frozen=True, slots=True)
class WorkflowStep:
    """Agent-defined phase goal and dependency boundary in a Workflow."""

    step_id: str
    purpose: str
    stages: tuple[StageRequest, ...]
    depends_on: tuple[str, ...] = ()
    optional: bool = False

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return tuple(stage.stage_id for stage in self.stages)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "purpose": self.purpose,
            "stages": [stage.to_dict() for stage in self.stages],
            "depends_on": list(self.depends_on),
            "optional": self.optional,
        }


@dataclass(frozen=True, slots=True)
class Workflow:
    """One immutable, Agent-authored macro-lifecycle Workflow revision."""

    guidance: str
    route: TaskRoute
    steps: tuple[WorkflowStep, ...]
    workflow_id: str = ""
    revision: int = 1
    status: WorkflowStatus = WorkflowStatus.DRAFT
    supersedes_workflow_id: str | None = None
    replacement_reason: str | None = None
    recovery_pointer: str | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # Accept a plain string route and coerce it, so a hand-written plan JSON
        # behaves identically to one built in Python. Frozen dataclasses cannot
        # assign directly, so this goes through object.__setattr__.
        if not isinstance(self.route, TaskRoute):
            object.__setattr__(self, "route", TaskRoute(self.route))

    @property
    def revision_id(self) -> str:
        base = self.workflow_id or self.guidance
        return f"{base}:r{self.revision}"

    @property
    def stage_requests(self) -> tuple[StageRequest, ...]:
        return tuple(stage for step in self.steps for stage in step.stages)

    @property
    def calls(self) -> tuple[ToolCall, ...]:
        return tuple(call for stage in self.stage_requests for call in stage.calls)

    @property
    def stages(self) -> tuple[str, ...]:
        return tuple(stage.stage_id for stage in self.stage_requests)

    @property
    def step_ids(self) -> tuple[str, ...]:
        return tuple(step.step_id for step in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "guidance": self.guidance,
            "route": self.route.value,
            "workflow_id": self.workflow_id,
            "revision": self.revision,
            "revision_id": self.revision_id,
            "status": self.status.value,
            "supersedes_workflow_id": self.supersedes_workflow_id,
            "replacement_reason": self.replacement_reason,
            "steps": [step.to_dict() for step in self.steps],
            "recovery_pointer": self.recovery_pointer,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class GateResult:
    """Local precondition / entry gate result."""

    ready: bool
    blocked_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    next_action: str | None = None
