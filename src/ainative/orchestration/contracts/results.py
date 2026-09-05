from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .artifacts import ArtifactRef
from .checklists import ChecklistSummary, CheckResult, ExecutionItemResult


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
    """Structured result for one ToolCall or McpCall inside a Stage."""

    call_id: str
    kind: str
    status: TaskStatus
    toolset_id: str | None = None
    tool_id: str | None = None
    server_id: str | None = None
    tool_name: str | None = None
    outputs: dict[str, Any] = field(default_factory=dict)
    artifacts: tuple[ArtifactRef, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    resume_pointer: str | None = None
    preserved_relations: frozenset[str] = field(default_factory=frozenset)
    lost_relations: frozenset[str] = field(default_factory=frozenset)

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "kind": self.kind,
            "toolset_id": self.toolset_id,
            "tool_id": self.tool_id,
            "server_id": self.server_id,
            "tool_name": self.tool_name,
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
    workflow_id: str | None = None
    profile: str = "default"
    authority_id: str | None = None
    plan_id: str | None = None
    plan_revision: int | None = None
    plan_revision_id: str | None = None
    plan_status: str | None = None
    supersedes_plan_id: str | None = None
    backend: str | None = None
    provider_id: str | None = None
    call_surface: str | None = None
    modification_method: str | None = None
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
            "workflow_id": self.workflow_id,
            "profile": self.profile,
            "authority_id": self.authority_id,
            "plan_id": self.plan_id,
            "plan_revision": self.plan_revision,
            "plan_revision_id": self.plan_revision_id,
            "plan_status": self.plan_status,
            "supersedes_plan_id": self.supersedes_plan_id,
            "backend": self.backend,
            "provider_id": self.provider_id,
            "call_surface": self.call_surface,
            "modification_method": self.modification_method,
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
