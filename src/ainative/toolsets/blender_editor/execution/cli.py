import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from ainative.orchestration.contracts.artifacts import ArtifactKind, ArtifactRef
from ainative.orchestration.contracts.results import TaskResult, TaskStatus
from ainative.orchestration.contracts.task import BlenderCallSurface, TaskRoute

from .executor import BlenderOperationRequest


def find_blender_executable() -> str:
    configured = os.environ.get("BLENDER_EXECUTABLE")
    candidates = [
        configured,
        shutil.which("blender"),
        r"E:\blender\blender.exe",
        r"D:\Blender\Blender-5.0.0\blender-5.0.0-windows-x64\blender.exe",
        r"D:\Blender\Blender-4.2.0\blender-4.2.0-windows-x64\blender.exe",
        r"D:\Blender\4.2\blender.exe",
    ]
    for candidate in candidates:
        if candidate and (Path(candidate).is_file() or shutil.which(candidate)):
            return str(Path(candidate)) if Path(candidate).is_file() else str(candidate)
    return "blender"


class BlenderCliSurface:
    """Blender CLI + Python surface; process execution is injected for tests."""

    call_surface = BlenderCallSurface.CLI_PYTHON

    def __init__(
        self,
        executable: str | Path | None = None,
        script: str | Path | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        timeout: int = 300,
    ) -> None:
        self.executable = str(executable) if executable is not None else find_blender_executable()
        default_script = Path(__file__).with_name("cli_entry.py")
        self.script = str(script) if script else (str(default_script) if default_script.is_file() else None)
        self._runner = runner or subprocess.run
        self.timeout = timeout

    def is_ready(self) -> bool:
        path = Path(self.executable)
        return path.exists() or shutil.which(self.executable) is not None

    def execute(self, request: BlenderOperationRequest) -> TaskResult:
        script = str(request.parameters.get("script", self.script or ""))
        if not script:
            return TaskResult(status=TaskStatus.BLOCKED, route=TaskRoute.HOST_OPERATION.value, call_surface=self.call_surface.value, errors=("CLI execution requires a script",), next_action="configure BlenderCliSurface.script")
        result_file = request.parameters.get("result_file")
        if result_file:
            output_file = Path(result_file)
        else:
            output_file = Path.cwd() / "artifacts" / "scratch" / request.task_id / "blender-result.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        if output_file.exists():
            output_file.unlink()
        with tempfile.TemporaryDirectory(prefix="ainative-blender-") as temp_dir:
            request_file = Path(temp_dir) / "request.json"
            request_file.write_text(json.dumps({"operation": request.operation, "parameters": request.parameters}, ensure_ascii=False, default=str), encoding="utf-8")
            args: list[str] = [self.executable, "--background"]
            blend_file = request.parameters.get("blend_file")
            if blend_file:
                args.append(str(blend_file))
            args.extend(["--python", script, "--", "--request-file", str(request_file), "--result-file", str(output_file)])
            try:
                completed = self._runner(
                    args,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                    timeout=self.timeout,
                )
            except subprocess.TimeoutExpired:
                return TaskResult(
                    status=TaskStatus.FAILED,
                    route=TaskRoute.HOST_OPERATION.value,
                    call_surface=self.call_surface.value,
                    errors=(f"Blender CLI timed out after {self.timeout}s",),
                    resume_pointer="stage.apply_change",
                )
            except OSError as exc:
                return TaskResult(
                    status=TaskStatus.FAILED,
                    route=TaskRoute.HOST_OPERATION.value,
                    call_surface=self.call_surface.value,
                    errors=(f"Blender CLI failed to start: {exc}",),
                    resume_pointer="stage.apply_change",
                )
            if completed.returncode != 0:
                return TaskResult(status=TaskStatus.FAILED, route=TaskRoute.HOST_OPERATION.value, call_surface=self.call_surface.value, errors=(completed.stderr or completed.stdout or "Blender CLI failed",), resume_pointer="stage.apply_change")
            if not output_file.is_file():
                return TaskResult(status=TaskStatus.FAILED, route=TaskRoute.HOST_OPERATION.value, call_surface=self.call_surface.value, errors=("Blender CLI completed without a result file",), resume_pointer="stage.apply_change")
            try:
                payload = json.loads(output_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                return TaskResult(status=TaskStatus.FAILED, route=TaskRoute.HOST_OPERATION.value, call_surface=self.call_surface.value, errors=(f"invalid Blender result file: {exc}",), resume_pointer="stage.apply_change")
            try:
                status = TaskStatus(payload.get("status", TaskStatus.SUCCEEDED.value))
            except ValueError as exc:
                return TaskResult(
                    status=TaskStatus.FAILED,
                    route=TaskRoute.HOST_OPERATION.value,
                    call_surface=self.call_surface.value,
                    errors=(f"invalid Blender result status: {exc}",),
                    resume_pointer="stage.apply_change",
                )
            artifact = ArtifactRef(artifact_id=f"{request.task_id}:blender", kind=ArtifactKind.BUNDLE, uri=str(output_file), provider_id="blender-cli")
            details = {key: value for key, value in payload.items() if key not in {"status", "warnings", "errors", "error"}}
            errors = tuple(payload.get("errors", ())) + ((str(payload["error"]),) if payload.get("error") else ())
            return TaskResult(status=status, route=TaskRoute.HOST_OPERATION.value, call_surface=self.call_surface.value, artifacts=(artifact,), details=details, warnings=tuple(payload.get("warnings", ())), errors=errors, resume_pointer=None if status is TaskStatus.SUCCEEDED else "stage.apply_change")
