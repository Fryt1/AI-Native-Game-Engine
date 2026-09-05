from dataclasses import dataclass, field
from typing import Any, Protocol

from ainative.orchestration.contracts.results import TaskResult
from ainative.orchestration.contracts.tools import ToolsetDefinition


@dataclass(frozen=True, slots=True)
class HostOperationRequest:
    task_id: str
    operation: str
    parameters: dict[str, Any] = field(default_factory=dict)
    call_surface: str | None = None


class HostExecutor(Protocol):
    """Small seam for a host such as Blender or UE5."""

    executor_id: str
    host_id: str

    def is_ready(self) -> bool: ...

    def toolsets(self) -> tuple[ToolsetDefinition, ...]: ...

    def execute(self, request: HostOperationRequest) -> TaskResult: ...
