from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from collections.abc import Callable
from pathlib import Path

from ainative.orchestration.contracts.artifacts import ArtifactKind, ArtifactRef
from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.orchestration.contracts.results import TaskResult, TaskStatus
from ainative.orchestration.contracts.task import TaskRoute


def _stamp_bridge_transfer(path: Path, transfer_id: str) -> None:
    if not path.is_file():
        return
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(document, dict):
        return
    document["transfer_id"] = transfer_id
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.ainative.tmp")
    temp.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _bridge_transfer_error(path: Path, transfer_id: str) -> str | None:
    if not path.is_file():
        return f"Bridge protocol file does not exist: {path}"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"invalid Bridge protocol file {path}: {exc}"
    if not isinstance(document, dict):
        return f"Bridge protocol file must contain an object: {path}"
    document_transfer_id = document.get("transfer_id") or document.get("transferId")
    if document_transfer_id is None:
        return f"Bridge protocol file is missing transfer_id: {path}"
    if str(document_transfer_id) != transfer_id:
        return f"Bridge protocol file belongs to transfer {document_transfer_id}, expected {transfer_id}"
    return None


def _safe_transfer_token(value: str) -> str:
    return "".join(character if character.isalnum() or character in "-_." else "_" for character in value) or "transfer"


class ExternalBlenderAssetsBridgeConnector:
    """Process executor for the upstream AssetsBridge Blender Add-on."""

    connector_id = "blender-external-assetsbridge"

    def __init__(
        self,
        blender_executable: str | Path,
        addon_root: str | Path,
        bridge_dir: str | Path,
        work_dir: str | Path,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        timeout: int = 120,
    ) -> None:
        self.blender_executable = Path(blender_executable)
        self.addon_root = Path(addon_root)
        self.bridge_dir = Path(bridge_dir)
        self.work_dir = Path(work_dir)
        self.user_scripts = self.work_dir / "blender-user-scripts"
        self.installed_addon = self.user_scripts / "addons" / "AssetsBridge"
        self._runner = runner or subprocess.run
        self.timeout = timeout
        if self.addon_root.is_dir():
            shutil.copytree(
                self.addon_root,
                self.installed_addon,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )

    def is_ready(self) -> bool:
        return self.blender_executable.is_file() and (self.installed_addon / "__init__.py").is_file() and self.bridge_dir.is_dir()

    def import_asset(self, manifest: TransferManifest) -> TaskResult:
        return self._run("import", manifest)

    def export_asset(self, manifest: TransferManifest) -> TaskResult:
        return self._run("export", manifest)

    def _run(self, operation: str, manifest: TransferManifest) -> TaskResult:
        result_file = self.work_dir / f"blender-{operation}-{_safe_transfer_token(manifest.transfer_id)}.json"
        result_file.parent.mkdir(parents=True, exist_ok=True)
        if result_file.exists():
            result_file.unlink()
        active_bridge_dir = Path(str(manifest.metadata.get("bridge_dir", self.bridge_dir)))
        active_bridge_dir.mkdir(parents=True, exist_ok=True)
        bridge_result = active_bridge_dir / "from-blender.json"
        if operation == "export" and bridge_result.exists():
            bridge_result.unlink()
        if operation == "import":
            source_error = _bridge_transfer_error(active_bridge_dir / "from-unreal.json", manifest.transfer_id)
            if source_error:
                return TaskResult(
                    status=TaskStatus.FAILED,
                    route=TaskRoute.ASSET_TRANSFER.value,
                    backend="assetsbridge",
                    errors=(source_error,),
                    resume_pointer="stage.transfer_to_edit_host",
                )
        env = os.environ.copy()
        env.update(
            {
                "BLENDER_USER_SCRIPTS": str(self.user_scripts),
                "AINATIVE_BRIDGE_DIR": str(active_bridge_dir),
                "AINATIVE_BLENDER_OPERATION": operation,
                "AINATIVE_BLENDER_RESULT_FILE": str(result_file),
                "AINATIVE_TRANSFER_ID": manifest.transfer_id,
            }
        )
        if manifest.metadata.get("blender_edit_file"):
            env["AINATIVE_BLENDER_EDIT_FILE"] = str(manifest.metadata["blender_edit_file"])
        if manifest.metadata.get("modified_blend_file"):
            env["AINATIVE_BLENDER_MODIFIED_FILE"] = str(manifest.metadata["modified_blend_file"])
        if manifest.export_file:
            env["AINATIVE_BLENDER_EXPORT_FILE"] = str(manifest.export_file)
        script = Path(__file__).parent / "execution" / "blender_endpoint.py"
        args = [str(self.blender_executable), "--background"]
        if operation == "export" and manifest.metadata.get("modified_blend_file"):
            args.append(str(manifest.metadata["modified_blend_file"]))
        else:
            args.append("--factory-startup")
        args.extend(["--python", str(script)])
        try:
            completed = self._runner(
                args,
                env=env,
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
                route=TaskRoute.ASSET_TRANSFER.value,
                backend="assetsbridge",
                errors=(f"Blender AssetsBridge process timed out after {self.timeout}s",),
                resume_pointer="stage.transfer_to_edit_host" if operation == "import" else "stage.return_to_target",
            )
        except OSError as exc:
            return TaskResult(
                status=TaskStatus.FAILED,
                route=TaskRoute.ASSET_TRANSFER.value,
                backend="assetsbridge",
                errors=(f"Blender AssetsBridge process failed to start: {exc}",),
                resume_pointer="stage.transfer_to_edit_host" if operation == "import" else "stage.return_to_target",
            )
        if completed.returncode != 0:
            return TaskResult(
                status=TaskStatus.FAILED,
                route=TaskRoute.ASSET_TRANSFER.value,
                backend="assetsbridge",
                errors=(completed.stderr or completed.stdout or "Blender AssetsBridge process failed",),
                resume_pointer="stage.transfer_to_edit_host" if operation == "import" else "stage.return_to_target",
            )
        if not result_file.is_file():
            return TaskResult(
                status=TaskStatus.FAILED,
                route=TaskRoute.ASSET_TRANSFER.value,
                backend="assetsbridge",
                errors=(completed.stderr or completed.stdout or "Blender AssetsBridge process produced no result file",),
                resume_pointer="stage.transfer_to_edit_host" if operation == "import" else "stage.return_to_target",
            )
        try:
            payload = json.loads(result_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return TaskResult(
                status=TaskStatus.FAILED,
                route=TaskRoute.ASSET_TRANSFER.value,
                backend="assetsbridge",
                errors=(f"invalid Blender AssetsBridge result: {exc}",),
                resume_pointer="stage.transfer_to_edit_host" if operation == "import" else "stage.return_to_target",
            )
        if not isinstance(payload, dict):
            return TaskResult(
                status=TaskStatus.FAILED,
                route=TaskRoute.ASSET_TRANSFER.value,
                backend="assetsbridge",
                errors=("Blender AssetsBridge result must be a JSON object",),
                resume_pointer="stage.transfer_to_edit_host" if operation == "import" else "stage.return_to_target",
            )
        payload_transfer_id = payload.get("transfer_id") or payload.get("transferId")
        if payload_transfer_id is None:
            return TaskResult(
                status=TaskStatus.FAILED,
                route=TaskRoute.ASSET_TRANSFER.value,
                backend="assetsbridge",
                errors=("Blender result is missing transfer_id",),
                resume_pointer="stage.transfer_to_edit_host" if operation == "import" else "stage.return_to_target",
            )
        if str(payload_transfer_id) != manifest.transfer_id:
            return TaskResult(
                status=TaskStatus.FAILED,
                route=TaskRoute.ASSET_TRANSFER.value,
                backend="assetsbridge",
                errors=(f"Blender result belongs to transfer {payload_transfer_id}, expected {manifest.transfer_id}",),
                resume_pointer="stage.transfer_to_edit_host" if operation == "import" else "stage.return_to_target",
            )
        try:
            status = TaskStatus(payload.get("status", "failed"))
        except ValueError as exc:
            return TaskResult(
                status=TaskStatus.FAILED,
                route=TaskRoute.ASSET_TRANSFER.value,
                backend="assetsbridge",
                errors=(f"invalid Blender AssetsBridge result status: {exc}",),
                resume_pointer="stage.transfer_to_edit_host" if operation == "import" else "stage.return_to_target",
            )
        if status is TaskStatus.SUCCEEDED and operation == "export":
            _stamp_bridge_transfer(bridge_result, manifest.transfer_id)
            bridge_error = _bridge_transfer_error(bridge_result, manifest.transfer_id)
            if bridge_error:
                return TaskResult(
                    status=TaskStatus.FAILED,
                    route=TaskRoute.ASSET_TRANSFER.value,
                    backend="assetsbridge",
                    errors=(bridge_error,),
                    resume_pointer="stage.return_to_target",
                )
        artifact = ArtifactRef(
            artifact_id=f"{manifest.transfer_id}:blender-{operation}",
            kind=ArtifactKind.BUNDLE,
            uri=str(result_file),
            provider_id="assetsbridge",
        )
        return TaskResult(
            status=status,
            route=TaskRoute.ASSET_TRANSFER.value,
            backend="assetsbridge",
            artifacts=(artifact,),
            warnings=tuple(payload.get("warnings", ())),
            errors=tuple(payload.get("errors", ())) + ((str(payload["error"]),) if payload.get("error") else ()),
            resume_pointer=None if status is TaskStatus.SUCCEEDED else ("stage.transfer_to_edit_host" if operation == "import" else "stage.return_to_target"),
        )
