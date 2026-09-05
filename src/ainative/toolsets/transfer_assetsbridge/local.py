from pathlib import Path

from ainative.orchestration.contracts.artifacts import ArtifactKind, ArtifactRef
from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.orchestration.contracts.results import TaskResult, TaskStatus
from ainative.orchestration.contracts.task import BlenderCallSurface, TaskRoute
from ainative.toolsets.blender_editor.execution import (
    BlenderExecutor,
    BlenderOperationRequest,
)

from .protocol import AssetsBridgeJsonProtocol


class JsonUE5BridgeConnector:
    """Protocol endpoint for UE5-side JSON exchange and evidence checks."""

    connector_id = "ue5-json-protocol"

    def __init__(self, protocol: AssetsBridgeJsonProtocol) -> None:
        self.protocol = protocol

    def is_ready(self) -> bool:
        return self.protocol.is_ready()

    def export_asset(self, manifest: TransferManifest) -> TaskResult:
        path = self.protocol.write("from_unreal", self.protocol.document_for_manifest(manifest, "UnrealExport"))
        artifact = ArtifactRef(artifact_id=f"{manifest.transfer_id}:from-unreal", kind=ArtifactKind.BUNDLE, uri=str(path), provider_id="assetsbridge")
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value, backend="assetsbridge", artifacts=(artifact,))

    def import_asset(self, manifest: TransferManifest) -> TaskResult:
        path = self.protocol.from_blender
        if not path.is_file():
            return TaskResult(status=TaskStatus.FAILED, route=TaskRoute.ASSET_TRANSFER.value, backend="assetsbridge", errors=(f"Bridge result file does not exist: {path}",), resume_pointer="stage.return_to_target")
        document = self.protocol.read("from_blender")
        objects = document.get("objects", [])
        identifiers = {manifest.asset_id, str(manifest.metadata.get("ue5_asset_path", "")), str(manifest.metadata.get("model", ""))}
        if not any(str(item.get("objectId", "")) in identifiers or str(item.get("model", "")) in identifiers for item in objects):
            return TaskResult(status=TaskStatus.FAILED, route=TaskRoute.ASSET_TRANSFER.value, backend="assetsbridge", errors=(f"Bridge result does not contain asset identity: {manifest.asset_id}",), resume_pointer="stage.return_to_target")
        artifact = ArtifactRef(artifact_id=f"{manifest.transfer_id}:from-blender", kind=ArtifactKind.BUNDLE, uri=str(path), provider_id="assetsbridge")
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value, backend="assetsbridge", artifacts=(artifact,))


class LocalBlenderBridgeConnector:
    """AssetsBridge Blender connector backed by the local Blender Executor."""

    connector_id = "blender-local-bridge"

    def __init__(self, executor: BlenderExecutor, bridge_dir: Path, call_surface: BlenderCallSurface = BlenderCallSurface.CLI_PYTHON) -> None:
        self.executor = executor
        self.bridge_dir = bridge_dir
        self.call_surface = call_surface

    def is_ready(self) -> bool:
        return self.bridge_dir.is_dir() and self.executor.can_use(self.call_surface)

    def import_asset(self, manifest: TransferManifest) -> TaskResult:
        params = dict(manifest.metadata)
        params["bridge_dir"] = str(self.bridge_dir)
        if manifest.metadata.get("blender_edit_file"):
            params["save_after"] = manifest.metadata["blender_edit_file"]
        result_dir = Path(str(manifest.metadata.get("result_dir", Path.cwd() / "artifacts" / "scratch" / manifest.transfer_id)))
        params.setdefault("result_file", str(result_dir / "blender-import.json"))
        return self.executor.execute(BlenderOperationRequest(task_id=f"{manifest.transfer_id}-stage-transfer-to-edit-host", operation="import-bridge-json", call_surface=self.call_surface, parameters=params))

    def export_asset(self, manifest: TransferManifest) -> TaskResult:
        params = dict(manifest.metadata)
        params.update({"bridge_dir": str(self.bridge_dir), "export_file": manifest.export_file})
        if manifest.metadata.get("modified_blend_file"):
            params["blend_file"] = manifest.metadata["modified_blend_file"]
        result_dir = Path(str(manifest.metadata.get("result_dir", Path.cwd() / "artifacts" / "scratch" / manifest.transfer_id)))
        params.setdefault("result_file", str(result_dir / "blender-export.json"))
        return self.executor.execute(BlenderOperationRequest(task_id=f"{manifest.transfer_id}-stage-return-to-target", operation="export-bridge-json", call_surface=self.call_surface, parameters=params))

