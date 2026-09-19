from dataclasses import dataclass, field
from typing import Any


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
    asset_type: str = "unknown"
    direction: str = "none"
    preserve_relations: frozenset[str] = field(default_factory=frozenset)
    guidance: str | None = None
    source_context: dict[str, Any] = field(default_factory=dict)
    target_context: dict[str, Any] = field(default_factory=dict)
    confirmation_required: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "objective": self.objective,
            "asset_type": self.asset_type,
            "direction": self.direction,
            "preserve_relations": sorted(self.preserve_relations),
            "guidance": self.guidance,
            "source_context": self.source_context,
            "target_context": self.target_context,
            "confirmation_required": self.confirmation_required,
            "metadata": self.metadata,
        }
