from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .artifacts import ArtifactRef
from .checklists import ChecklistSummary, CheckResult, ExecutionItemResult
from .coercion import coerce_enum
from .tools import CallTarget


class TaskStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    NEEDS_APPROVAL = "needs_approval"
    DEGRADED = "degraded"


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """What one declared call returned, as the Agent reports it."""

    call_id: str
    status: TaskStatus
    target: CallTarget | None = None
    outputs: dict[str, Any] = field(default_factory=dict)
    artifacts: tuple[ArtifactRef, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    resume_pointer: str | None = None
    preserved_relations: frozenset[str] = field(default_factory=frozenset)
    lost_relations: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        coerce_enum(self, "status", TaskStatus)

    def evidence_view(self) -> dict[str, Any]:
        """Return the fields an acceptance check may address by path.

        A check reads evidence, and the evidence of a call is not only its
        free-form ``outputs``: the relation and status fields below are
        first-class proof. Exposing them here keeps ``actual_path`` meaningful for
        the evidence that matters most, instead of forcing it into ``outputs``.

        @returns a mapping of addressable evidence paths to their values.
        """

        return {
            "status": self.status.value,
            "target": self.target.to_dict() if self.target else None,
            "preserved_relations": sorted(self.preserved_relations),
            "lost_relations": sorted(self.lost_relations),
            "artifact_count": len(self.artifacts),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            **self.outputs,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "target": self.target.to_dict() if self.target else None,
            "status": self.status.value,
            "outputs": self.outputs,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "resume_pointer": self.resume_pointer,
            "preserved_relations": sorted(self.preserved_relations),
            "lost_relations": sorted(self.lost_relations),
        }


@dataclass(frozen=True, slots=True)
class StageResult:
    """Durable result for one Stage and all Tool Calls it attempted."""

    stage_id: str
    step_id: str
    status: TaskStatus
    execution_results: tuple[ExecutionResult, ...] = ()
    execution_item_results: tuple[ExecutionItemResult, ...] = ()
    check_results: tuple[CheckResult, ...] = ()
    execution_summary: ChecklistSummary = field(default_factory=ChecklistSummary)
    acceptance_summary: ChecklistSummary = field(default_factory=ChecklistSummary)
    outputs: dict[str, Any] = field(default_factory=dict)
    artifacts: tuple[ArtifactRef, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    resume_pointer: str | None = None

    def __post_init__(self) -> None:
        coerce_enum(self, "status", TaskStatus)

    @property
    def call_ids(self) -> tuple[str, ...]:
        return tuple(result.call_id for result in self.execution_results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "step_id": self.step_id,
            "status": self.status.value,
            "call_ids": list(self.call_ids),
            "execution_results": [result.to_dict() for result in self.execution_results],
            "execution_item_results": [result.to_dict() for result in self.execution_item_results],
            "check_results": [result.to_dict() for result in self.check_results],
            "execution_summary": self.execution_summary.to_dict(),
            "acceptance_summary": self.acceptance_summary.to_dict(),
            "outputs": self.outputs,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "resume_pointer": self.resume_pointer,
        }


@dataclass(frozen=True, slots=True)
class TaskResult:
    status: TaskStatus
    route: str
    guidance: str | None = None
    workflow_id: str | None = None
    workflow_revision: int | None = None
    workflow_revision_id: str | None = None
    workflow_status: str | None = None
    supersedes_workflow_id: str | None = None
    provider_id: str | None = None
    stages_completed: tuple[str, ...] = ()
    steps_completed: tuple[str, ...] = ()
    stage_results: tuple[StageResult, ...] = ()
    preserved_relations: frozenset[str] = field(default_factory=frozenset)
    lost_relations: frozenset[str] = field(default_factory=frozenset)
    artifacts: tuple[ArtifactRef, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    next_action: str | None = None
    resume_pointer: str | None = None

    def __post_init__(self) -> None:
        coerce_enum(self, "status", TaskStatus)

    @property
    def terminal(self) -> bool:
        return self.status in {
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.BLOCKED,
            TaskStatus.NEEDS_APPROVAL,
            TaskStatus.DEGRADED,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "route": self.route,
            "guidance": self.guidance,
            "workflow_id": self.workflow_id,
            "workflow_revision": self.workflow_revision,
            "workflow_revision_id": self.workflow_revision_id,
            "workflow_status": self.workflow_status,
            "supersedes_workflow_id": self.supersedes_workflow_id,
            "provider_id": self.provider_id,
            "stages_completed": list(self.stages_completed),
            "steps_completed": list(self.steps_completed),
            "stage_results": [stage.to_dict() for stage in self.stage_results],
            "preserved_relations": sorted(self.preserved_relations),
            "lost_relations": sorted(self.lost_relations),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "details": self.details,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "next_action": self.next_action,
            "resume_pointer": self.resume_pointer,
        }
