import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.orchestration.contracts.results import TaskResult, TaskStatus
from ainative.orchestration.contracts.task import TaskRoute
from ainative.orchestration.contracts.tools import ToolExecutionKind, ToolsetDefinition
from ainative.registry import toolset_from_operations
from ainative.toolsets.ports.host_executor import HostOperationRequest

COMMAND_OPERATIONS = ("inspect", "list_actors", "create_actor", "create-actor", "create_level_from_template", "create-level-from-template", "inspect_level", "inspect-level", "resolve_actor", "resolve-actor", "read_actor_transform", "read-actor-transform", "set_actor_transform", "set-actor-transform", "save_level", "save-level", "export_asset", "import_asset")


class UnrealEditorCommandExecutor:
    """UE5 command seam with an injected command builder.

    UE5 project/editor commands vary by installed plugins and project. The
    executor therefore owns process execution while the project-specific command
    builder stays injected instead of being guessed in the core.
    """

    executor_id = "ue5-command"
    host_id = "ue5"

    def __init__(
        self,
        executable: str | Path,
        project_file: str | Path,
        command_builder: Callable[[str, TransferManifest], list[str]] | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        timeout: int = 300,
    ) -> None:
        self.executable = str(executable)
        self.project_file = Path(project_file)
        self._command_builder = command_builder
        self._runner = runner or subprocess.run
        self.timeout = timeout

    def is_ready(self) -> bool:
        path = Path(self.executable)
        return (path.exists() or shutil.which(self.executable) is not None) and self.project_file.is_file()

    def toolsets(self) -> tuple[ToolsetDefinition, ...]:
        return (
            toolset_from_operations(
                toolset_id="ue5.editor",
                provider_id=self.host_id,
                execution_kind=ToolExecutionKind.HOST,
                operations=COMMAND_OPERATIONS,
                title="UE5 Command Surface",
                description="Project-specific UE5 command execution tools.",
                metadata={"executor_id": self.executor_id, "surface": "ue5-command"},
                input_schemas={
                    "create_actor": {"type": "object", "properties": {"level_path": {"type": "string"}, "label": {"type": "string"}, "mesh_path": {"type": "string"}}},
                    "create_level_from_template": {"type": "object", "properties": {"target_level": {"type": "string"}, "template_level": {"type": "string"}}},
                    "inspect_level": {"type": "object", "properties": {"level_path": {"type": "string"}, "target_level": {"type": "string"}}},
                    "set_actor_transform": {"type": "object", "properties": {"actor_path": {"type": "string"}, "actor_name": {"type": "string"}, "label": {"type": "string"}, "location": {"type": "array", "minItems": 3, "maxItems": 3}, "delta": {"type": "array", "minItems": 3, "maxItems": 3}, "rotation": {"type": "array", "minItems": 3, "maxItems": 3}, "scale": {"type": "array", "minItems": 3, "maxItems": 3}}},
                    "save_level": {"type": "object", "properties": {"level_path": {"type": "string"}}},
                },
            ),
        )

    def execute(self, request: HostOperationRequest) -> TaskResult:
        manifest = request.parameters.get("manifest")
        return self._run(request.operation, manifest if isinstance(manifest, TransferManifest) else None, request.parameters, TaskRoute.HOST_OPERATION.value)

    def export_asset(self, manifest: TransferManifest) -> TaskResult:
        return self._run("export_asset", manifest, {}, TaskRoute.ASSET_TRANSFER.value)

    def import_asset(self, manifest: TransferManifest) -> TaskResult:
        return self._run("import_asset", manifest, {}, TaskRoute.ASSET_TRANSFER.value)

    def _run(self, operation: str, manifest: TransferManifest | None, parameters: dict[str, Any], route: str) -> TaskResult:
        if not self.is_ready():
            return TaskResult(status=TaskStatus.BLOCKED, route=route, call_surface="ue5-command", errors=("UE5 executable or project file is not ready",), next_action="configure the UE5 Executor")
        if self._command_builder is None:
            return TaskResult(status=TaskStatus.BLOCKED, route=route, call_surface="ue5-command", errors=("UE5 command_builder is required",), next_action="inject the project-specific UE5 command builder")
        if operation in {"export_asset", "import_asset"} and manifest is None:
            return TaskResult(status=TaskStatus.BLOCKED, route=route, call_surface="ue5-command", errors=("TransferManifest is required for asset transfer",), next_action="provide a TransferManifest")
        args = self._command_builder(operation, manifest)  # type: ignore[arg-type]
        try:
            completed = self._runner(args, capture_output=True, text=True, check=False, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return TaskResult(
                status=TaskStatus.FAILED,
                route=route,
                call_surface="ue5-command",
                errors=(f"UE5 command timed out after {self.timeout}s",),
                resume_pointer="stage.apply_change",
            )
        except OSError as exc:
            return TaskResult(
                status=TaskStatus.FAILED,
                route=route,
                call_surface="ue5-command",
                errors=(f"UE5 command failed to start: {exc}",),
                resume_pointer="stage.apply_change",
            )
        if completed.returncode != 0:
            return TaskResult(status=TaskStatus.FAILED, route=route, call_surface="ue5-command", errors=(completed.stderr or completed.stdout or "UE5 command failed",), resume_pointer="stage.apply_change")
        return TaskResult(status=TaskStatus.SUCCEEDED, route=route, call_surface="ue5-command", details={"operation": operation})



