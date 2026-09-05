from collections.abc import Callable

from ainative.orchestration.contracts.results import TaskResult, TaskStatus
from ainative.orchestration.contracts.task import BlenderCallSurface, TaskRoute

from .executor import BlenderOperationRequest


class BlenderAddonSurface:
    """Interactive Blender Add-on surface with an injected transport."""

    call_surface = BlenderCallSurface.ADDON

    def __init__(self, executor: Callable[[BlenderOperationRequest], TaskResult] | None = None) -> None:
        self._executor = executor

    def is_ready(self) -> bool:
        return self._executor is not None

    def execute(self, request: BlenderOperationRequest) -> TaskResult:
        if self._executor is None:
            return TaskResult(status=TaskStatus.BLOCKED, route=TaskRoute.HOST_OPERATION.value, call_surface=self.call_surface.value, errors=("Blender Add-on executor is not configured",))
        return self._executor(request)
