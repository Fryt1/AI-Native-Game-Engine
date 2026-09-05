from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TaskRoute(StrEnum):
    """Stable lifecycle domains used as routing guardrails.

    A Route narrows the applicable safety and validation rules. It does not
    identify a tool, Backend, file format, or one fixed Workflow.
    """

    HOST_OPERATION = "host_operation"
    ASSET_TRANSFER = "asset_transfer"
    ARTIFACT_PIPELINE = "artifact_pipeline"


class ProfileName(StrEnum):
    DEFAULT = "default"
    INTERACTIVE = "interactive"
    HEADLESS_BATCH = "headless_batch"


class BlenderCallSurface(StrEnum):
    CLI_PYTHON = "blender_cli_python"
    ADDON = "blender_addon"


class TransferBackendKind(StrEnum):
    ASSETSBRIDGE = "assetsbridge"
    DIRECT = "direct"


@dataclass(frozen=True, slots=True)
class TaskContract:
    """Normalized input to one Route Family and optional Workflow choice."""

    task_id: str
    objective: str
    route: TaskRoute
    profile: str = ProfileName.DEFAULT.value
    asset_type: str = "unknown"
    direction: str = "none"
    preserve_relations: frozenset[str] = field(default_factory=frozenset)
    acceptable_loss: frozenset[str] = field(default_factory=frozenset)
    destructive: bool = False
    preferred_backend: TransferBackendKind | None = None
    preferred_call_surface: BlenderCallSurface | None = None
    preferred_provider_id: str | None = None
    preferred_workflow_id: str | None = None
    source_context: dict[str, Any] = field(default_factory=dict)
    target_context: dict[str, Any] = field(default_factory=dict)
    confirmation_required: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "objective": self.objective,
            "route": self.route.value,
            "profile": self.profile,
            "asset_type": self.asset_type,
            "direction": self.direction,
            "preserve_relations": sorted(self.preserve_relations),
            "acceptable_loss": sorted(self.acceptable_loss),
            "destructive": self.destructive,
            "preferred_backend": self.preferred_backend.value if self.preferred_backend else None,
            "preferred_call_surface": self.preferred_call_surface.value if self.preferred_call_surface else None,
            "preferred_provider_id": self.preferred_provider_id,
            "preferred_workflow_id": self.preferred_workflow_id,
            "source_context": self.source_context,
            "target_context": self.target_context,
            "confirmation_required": self.confirmation_required,
            "metadata": self.metadata,
        }
