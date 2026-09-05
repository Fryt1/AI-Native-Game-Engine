from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from ainative.orchestration.contracts.artifacts import ArtifactKind, ArtifactRef
from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.orchestration.contracts.results import TaskResult, TaskStatus
from ainative.orchestration.contracts.task import TaskRoute
from ainative.orchestration.contracts.tools import ToolExecutionKind, ToolsetDefinition
from ainative.registry import toolset_from_operations
from ainative.toolsets.ports.host_executor import HostOperationRequest

UE5_OPERATIONS = (
    "list_actors",
    "create_actor",
    "create-actor",
    "create_level_from_template",
    "create-level-from-template",
    "inspect_level",
    "inspect-level",
    "resolve_actor",
    "resolve-actor",
    "read_actor_transform",
    "read-actor-transform",
    "set_actor_transform",
    "set-actor-transform",
    "save_level",
    "save-level",
)


class UnrealEditorPythonExecutor:
    """UE5 Python execution seam for commandlet or visible Editor launches.

    ``-ExecutePythonScript`` is available on both UE5 launch surfaces, but the
    process flags change the contract materially. A commandlet-style launch is
    appropriate for headless inspection. Operations that touch editor
    subsystems should use ``launch_mode="editor"`` so the ordinary
    ``UnrealEditor.exe`` application and Slate context are started.
    """

    executor_id = "ue5-python"
    host_id = "ue5"

    def __init__(
        self,
        executable: str | Path,
        project_file: str | Path,
        script: str | Path,
        bridge_dir: str | Path | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        timeout: int = 180,
        launch_mode: Literal["commandlet", "editor"] = "commandlet",
        extra_args: tuple[str, ...] = (),
    ) -> None:
        self.executable = str(executable)
        self.project_file = Path(project_file)
        self.script = str(script)
        self.bridge_dir = Path(bridge_dir) if bridge_dir else None
        self._runner = runner or subprocess.run
        self.timeout = timeout
        self.launch_mode = launch_mode
        self.extra_args = tuple(extra_args)

    def is_ready(self) -> bool:
        path = Path(self.executable)
        return (path.exists() or shutil.which(self.executable) is not None) and self.project_file.is_file() and Path(self.script).is_file()

    def toolsets(self) -> tuple[ToolsetDefinition, ...]:
        return (
            toolset_from_operations(
                toolset_id="ue5.editor",
                provider_id=self.host_id,
                execution_kind=ToolExecutionKind.HOST,
                operations=UE5_OPERATIONS,
                title="UE5 Editor Python",
                description="UE5 actor, Level, asset, and project operations through Python.",
                metadata={"executor_id": self.executor_id, "launch_mode": self.launch_mode},
            ),
        )

    def execute(self, request: HostOperationRequest) -> TaskResult:
        manifest = request.parameters.get("manifest")
        return self._run(
            request.operation,
            manifest if isinstance(manifest, TransferManifest) else None,
            parameters=request.parameters,
            route=TaskRoute.HOST_OPERATION.value,
        )

    def export_asset(self, manifest: TransferManifest) -> TaskResult:
        return self._run("export_asset", manifest, route=TaskRoute.ASSET_TRANSFER.value)

    def import_asset(self, manifest: TransferManifest) -> TaskResult:
        return self._run("import_asset", manifest, route=TaskRoute.ASSET_TRANSFER.value)

    def inspect(self) -> TaskResult:
        return self._run("inspect", None, route=TaskRoute.HOST_OPERATION.value)

    def create_level_from_template(self, parameters: dict[str, Any] | None = None) -> TaskResult:
        return self._run("create_level_from_template", None, parameters=parameters, route=TaskRoute.HOST_OPERATION.value)

    def inspect_level(self, parameters: dict[str, Any] | None = None) -> TaskResult:
        return self._run("inspect_level", None, parameters=parameters, route=TaskRoute.HOST_OPERATION.value)

    def inspect_actor(self, parameters: dict[str, Any] | None = None) -> TaskResult:
        return self._run("resolve_actor", None, parameters=parameters, route=TaskRoute.HOST_OPERATION.value)

    def read_actor_transform(self, parameters: dict[str, Any] | None = None) -> TaskResult:
        return self._run("read_actor_transform", None, parameters=parameters, route=TaskRoute.HOST_OPERATION.value)

    def set_actor_transform(self, parameters: dict[str, Any] | None = None) -> TaskResult:
        return self._run("set_actor_transform", None, parameters=parameters, route=TaskRoute.HOST_OPERATION.value)

    def save_level(self, parameters: dict[str, Any] | None = None) -> TaskResult:
        return self._run("save_level", None, parameters=parameters, route=TaskRoute.HOST_OPERATION.value)

    def _run(
        self,
        operation: str,
        manifest: TransferManifest | None,
        *,
        parameters: dict[str, Any] | None = None,
        route: str,
    ) -> TaskResult:
        base = {"status": TaskStatus.FAILED, "route": route, "call_surface": "ue5-python"}
        if not self.is_ready():
            return TaskResult(**base, errors=("UE5 executable, project, or Python script is not ready",), next_action="configure the UE5 Python Executor")
        supplied = dict(parameters or {})
        supplied.pop("manifest", None)
        result_root = Path(str((manifest.metadata if manifest else supplied).get("result_dir"))) if (manifest and manifest.metadata.get("result_dir") or supplied.get("result_dir")) else Path.cwd() / "artifacts" / "scratch"
        run_dir = result_root / "ue5" / operation
        run_dir.mkdir(parents=True, exist_ok=True)
        result_file = Path(str(supplied.get("result_file", run_dir / "result.json")))
        result_file.parent.mkdir(parents=True, exist_ok=True)
        request_file = run_dir / "request.json"
        request_payload = {"operation": operation, "parameters": supplied}
        request_file.write_text(json.dumps(request_payload, ensure_ascii=False, indent=2, default=self._json_default), encoding="utf-8")
        env = os.environ.copy()
        env["AINATIVE_UE5_OPERATION"] = operation
        env["AINATIVE_UE5_RESULT_FILE"] = str(result_file)
        env["AINATIVE_UE5_REQUEST_FILE"] = str(request_file)
        env["AINATIVE_UE5_EXIT_AFTER_OPERATION"] = "1"
        if self.bridge_dir:
            env["AINATIVE_UE5_BRIDGE_DIR"] = str(self.bridge_dir)
        if manifest is not None:
            manifest_file = run_dir / "manifest.json"
            manifest_file.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, default=self._json_default), encoding="utf-8")
            env["AINATIVE_UE5_MANIFEST_FILE"] = str(manifest_file)
        if self.launch_mode == "editor":
            args = [self.executable, str(self.project_file), "-nop4", *self.extra_args, f"-ExecutePythonScript={self.script}"]
        else:
            args = [self.executable, str(self.project_file), "-unattended", "-nop4", "-nosplash", "-nullrhi", *self.extra_args, f"-ExecutePythonScript={self.script}"]
        try:
            completed = self._runner(args, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, timeout=self.timeout, env=env)
        except subprocess.TimeoutExpired:
            return TaskResult(**base, errors=(f"UE5 Python command timed out after {self.timeout}s",), resume_pointer="stage.apply_change")
        if not result_file.is_file() and completed.returncode != 0 and "Preparing to exit" in (completed.stdout or ""):
            retry = self._runner(args, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, timeout=self.timeout, env=env)
            completed = retry
        (run_dir / "process.stdout.log").write_text(completed.stdout or "", encoding="utf-8")
        (run_dir / "process.stderr.log").write_text(completed.stderr or "", encoding="utf-8")
        if not result_file.is_file():
            message = completed.stderr or completed.stdout or "UE5 Python command produced no result file"
            return TaskResult(**base, errors=(f"{message} (returncode={completed.returncode})",), resume_pointer="stage.apply_change")
        try:
            payload = json.loads(result_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return TaskResult(**base, errors=(f"invalid UE5 result file: {exc}",), resume_pointer="stage.apply_change")
        status = TaskStatus(payload.get("status", "failed"))
        artifact = ArtifactRef(artifact_id=f"ue5:{operation}", kind=ArtifactKind.BUNDLE, uri=str(result_file), provider_id="ue5-python")
        details = {key: value for key, value in payload.items() if key not in {"status", "warnings", "errors", "error"}}
        errors = tuple(payload.get("errors", ())) + ((str(payload["error"]),) if payload.get("error") else ())
        return TaskResult(status=status, **{k: v for k, v in base.items() if k != "status"}, artifacts=(artifact,), details=details, warnings=tuple(payload.get("warnings", ())), errors=errors, next_action=None if status is TaskStatus.SUCCEEDED else "inspect the UE5 log and resume the selected Workflow", resume_pointer=None if status is TaskStatus.SUCCEEDED else "stage.apply_change")

    @staticmethod
    def _json_default(value: Any):
        if isinstance(value, TransferManifest):
            return value.to_dict()
        if hasattr(value, "to_dict"):
            return value.to_dict()
        return str(value)



