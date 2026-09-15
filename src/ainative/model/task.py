from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .coercion import coerce_enum


class TaskRoute(StrEnum):
    """Stable lifecycle domains used as routing guardrails.

    A Route narrows the applicable safety and validation rules. It does not
    identify a tool, Backend, or file format.
    """

    HOST_OPERATION = "host_operation"
    ASSET_TRANSFER = "asset_transfer"
    ARTIFACT_PIPELINE = "artifact_pipeline"


@dataclass(frozen=True, slots=True)
class TaskContract:
    """Normalized input to one task.


    This contract carries what the task *is*: its goal, direction, and which
    relations must survive. It carries no call-surface, host, backend, or
    modification-method field, because hosts are reached through their own MCP
    servers and those choices belong to the Agent's calls.
    """

    task_id: str
    objective: str
    route: TaskRoute
    asset_type: str = "unknown"
    direction: str = "none"
    preserve_relations: frozenset[str] = field(default_factory=frozenset)
    guidance: str | None = None
    source_context: dict[str, Any] = field(default_factory=dict)
    target_context: dict[str, Any] = field(default_factory=dict)
    confirmation_required: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        coerce_enum(self, "route", TaskRoute)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "objective": self.objective,
            "route": self.route.value,
            "asset_type": self.asset_type,
            "direction": self.direction,
            "preserve_relations": sorted(self.preserve_relations),
            "guidance": self.guidance,
            "source_context": self.source_context,
            "target_context": self.target_context,
            "confirmation_required": self.confirmation_required,
            "metadata": self.metadata,
        }
