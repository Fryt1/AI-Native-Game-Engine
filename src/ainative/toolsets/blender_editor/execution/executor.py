from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from ainative.orchestration.contracts.results import TaskResult, TaskStatus
from ainative.orchestration.contracts.task import BlenderCallSurface, TaskRoute
from ainative.orchestration.contracts.tools import ToolExecutionKind, ToolsetDefinition
from ainative.registry import toolset_from_operations
from ainative.toolsets.ports.host_executor import HostOperationRequest

BLENDER_OPERATIONS = (
    "inspect-active",
    "configure-scene-unreal",
    "import-bridge-json",
    "export-bridge-json",
    "create-cube",
    "import-glb",
    "translate-active",
    "set-location",
    "set-scale",
    "rename-active",
    "save-mainfile",
    "export-glb",
    "apply-artifact",
    "modify",
    "run-script",
)


@dataclass(frozen=True, slots=True)
class BlenderOperationRequest(HostOperationRequest):
    call_surface: BlenderCallSurface = BlenderCallSurface.CLI_PYTHON
    parameters: dict[str, Any] = field(default_factory=dict)


class BlenderSurfaceExecutor(Protocol):
    call_surface: BlenderCallSurface

    def is_ready(self) -> bool: ...

    def execute(self, request: BlenderOperationRequest) -> TaskResult: ...


class BlenderExecutor:
    """Deep Blender seam that normalizes CLI and Add-on call surfaces."""

    executor_id = "blender"
    host_id = "blender"

    def __init__(self, surfaces: Mapping[BlenderCallSurface, BlenderSurfaceExecutor] | None = None) -> None:
        self._surfaces = dict(surfaces or {})

    def is_ready(self) -> bool:
        return any(surface.is_ready() for surface in self._surfaces.values())

    def can_use(self, call_surface: BlenderCallSurface | None) -> bool:
        if call_surface is None:
            return False
        surface = self._surfaces.get(call_surface)
        return surface is not None and surface.is_ready()

    def toolsets(self) -> tuple[ToolsetDefinition, ...]:
        return (
            toolset_from_operations(
                toolset_id="blender.editor",
                provider_id=self.executor_id,
                execution_kind=ToolExecutionKind.HOST,
                operations=BLENDER_OPERATIONS,
                title="Blender Editor",
                description="Blender scene, object, asset, and file operations.",
                metadata={"call_surfaces": [surface.value for surface in self._surfaces]},
            ),
        )

    def execute(self, request: HostOperationRequest) -> TaskResult:
        selected_surface = request.call_surface
        if isinstance(selected_surface, str):
            try:
                selected_surface = BlenderCallSurface(selected_surface)
            except ValueError:
                selected_surface = None
        surface = self._surfaces.get(selected_surface)
        if surface is None or not surface.is_ready():
            surface_name = selected_surface.value if isinstance(selected_surface, BlenderCallSurface) else str(request.call_surface)
            return TaskResult(
                status=TaskStatus.BLOCKED,
                route=TaskRoute.HOST_OPERATION.value,
                call_surface=surface_name,
                errors=(f"Blender call surface is not ready: {surface_name}",),
                next_action="make the selected Blender call surface ready",
            )
        blender_request = request if isinstance(request, BlenderOperationRequest) else BlenderOperationRequest(
            task_id=request.task_id,
            operation=request.operation,
            parameters=dict(request.parameters),
            call_surface=selected_surface,
        )
        return surface.execute(blender_request)
