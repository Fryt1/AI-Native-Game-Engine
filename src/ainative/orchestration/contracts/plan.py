from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .checklists import AcceptanceCheck, ExecutionChecklistItem, StageKind
from .task import BlenderCallSurface, TaskRoute, TransferBackendKind
from .tools import ExecutionCall


class WorkflowPlanStatus(StrEnum):
    """Lifecycle state of one immutable Workflow Plan revision."""

    DRAFT = "draft"
    FEASIBLE = "feasible"
    RUNNING = "running"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"
    INVALID = "invalid"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class WorkflowSelection:
    """Route/workflow context selected before the Agent writes a plan.

    This is deliberately not a plan and contains no Step, Stage, or Tool Call.
    It tells the Agent which Workflow guidance to read and which coarse runtime
    constraints apply. The Agent still creates the concrete WorkflowPlan.
    """

    workflow_id: str
    route: TaskRoute
    profile: str
    authority_id: str
    transfer_backend: TransferBackendKind | None = None
    blender_call_surface: BlenderCallSurface | None = None
    modification_method: str = ""
    host_app: str = "blender"
    host_call_surface: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "route": self.route.value,
            "profile": self.profile,
            "authority_id": self.authority_id,
            "transfer_backend": self.transfer_backend.value if self.transfer_backend else None,
            "blender_call_surface": self.blender_call_surface.value if self.blender_call_surface else None,
            "modification_method": self.modification_method,
            "host_app": self.host_app,
            "host_call_surface": self.host_call_surface,
        }


@dataclass(frozen=True, slots=True)
class StageRequest:
    """One Agent-defined local goal with frozen execution and acceptance.

    ``operation`` is a human-readable label. The checklists define required work
    and proof; only explicit ``calls`` execute external operations.
    """

    stage_id: str
    purpose: str
    operation: str = ""
    calls: tuple[ExecutionCall, ...] = ()
    stage_kind: StageKind = StageKind.CHANGE
    execution_checklist: tuple[ExecutionChecklistItem, ...] = ()
    acceptance_checklist: tuple[AcceptanceCheck, ...] = ()
    depends_on: tuple[str, ...] = ()
    input_keys: tuple[str, ...] = ()
    output_keys: tuple[str, ...] = ()
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
            "input_keys": list(self.input_keys),
            "output_keys": list(self.output_keys),
            "required": self.required,
            "recovery": self.recovery,
        }


@dataclass(frozen=True, slots=True)
class StepPlan:
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
class WorkflowPlan:
    """One immutable, Agent-authored macro-lifecycle plan revision."""

    workflow_id: str
    route: TaskRoute
    profile: str
    authority_id: str
    steps: tuple[StepPlan, ...]
    plan_id: str = ""
    revision: int = 1
    status: WorkflowPlanStatus = WorkflowPlanStatus.DRAFT
    supersedes_plan_id: str | None = None
    replan_reason: str | None = None
    validation_items: tuple[str, ...] = ()
    recovery_pointer: str | None = None
    warnings: tuple[str, ...] = ()

    @property
    def revision_id(self) -> str:
        base = self.plan_id or self.workflow_id
        return f"{base}:r{self.revision}"

    @property
    def stage_requests(self) -> tuple[StageRequest, ...]:
        return tuple(stage for step in self.steps for stage in step.stages)

    @property
    def calls(self) -> tuple[ExecutionCall, ...]:
        return tuple(call for stage in self.stage_requests for call in stage.calls)

    @property
    def stages(self) -> tuple[str, ...]:
        return tuple(stage.stage_id for stage in self.stage_requests)

    @property
    def step_ids(self) -> tuple[str, ...]:
        return tuple(step.step_id for step in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "route": self.route.value,
            "profile": self.profile,
            "authority_id": self.authority_id,
            "plan_id": self.plan_id,
            "revision": self.revision,
            "revision_id": self.revision_id,
            "status": self.status.value,
            "supersedes_plan_id": self.supersedes_plan_id,
            "replan_reason": self.replan_reason,
            "steps": [step.to_dict() for step in self.steps],
            "validation_items": list(self.validation_items),
            "recovery_pointer": self.recovery_pointer,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Agent-authored WorkflowPlan plus concrete runtime dimensions.

    This object is supplied by the Agent to the execution seam. It is not
    synthesized by Python and it does not contain an implicit Tool binding
    pass. Every executable Tool Call must already be present in the nested
    WorkflowPlan.
    """

    workflow: WorkflowPlan
    transfer_backend: TransferBackendKind | None
    blender_call_surface: BlenderCallSurface | None
    modification_method: str
    host_app: str = "blender"
    host_call_surface: str | None = None

    @property
    def route(self) -> TaskRoute:
        return self.workflow.route

    @property
    def profile(self) -> str:
        return self.workflow.profile

    @property
    def authority_id(self) -> str:
        return self.workflow.authority_id

    @property
    def workflow_id(self) -> str:
        return self.workflow.workflow_id

    @property
    def plan_id(self) -> str:
        return self.workflow.plan_id

    @property
    def revision(self) -> int:
        return self.workflow.revision

    @property
    def revision_id(self) -> str:
        return self.workflow.revision_id

    @property
    def plan_status(self) -> WorkflowPlanStatus:
        return self.workflow.status

    @property
    def supersedes_plan_id(self) -> str | None:
        return self.workflow.supersedes_plan_id

    @property
    def replan_reason(self) -> str | None:
        return self.workflow.replan_reason

    @property
    def stages(self) -> tuple[str, ...]:
        return self.workflow.stages

    @property
    def stage_requests(self) -> tuple[StageRequest, ...]:
        return self.workflow.stage_requests

    @property
    def calls(self) -> tuple[ExecutionCall, ...]:
        return self.workflow.calls

    @property
    def validation_items(self) -> tuple[str, ...]:
        return self.workflow.validation_items

    @property
    def recovery_pointer(self) -> str | None:
        return self.workflow.recovery_pointer

    @property
    def warnings(self) -> tuple[str, ...]:
        return self.workflow.warnings

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow": self.workflow.to_dict(),
            "transfer_backend": self.transfer_backend.value if self.transfer_backend else None,
            "blender_call_surface": self.blender_call_surface.value if self.blender_call_surface else None,
            "modification_method": self.modification_method,
            "host_app": self.host_app,
            "host_call_surface": self.host_call_surface,
        }


@dataclass(frozen=True, slots=True)
class GateResult:
    """Local precondition / entry gate result."""

    ready: bool
    blocked_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    next_action: str | None = None
