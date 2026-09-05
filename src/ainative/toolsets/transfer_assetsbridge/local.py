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


def _protocol_for_manifest(protocol: AssetsBridgeJsonProtocol, manifest: TransferManifest) -> AssetsBridgeJsonProtocol:
    bridge_dir = Path(str(manifest.metadata.get("bridge_dir", protocol.bridge_dir)))
    bridge_dir.mkdir(parents=True, exist_ok=True)
    return AssetsBridgeJsonProtocol(bridge_dir)


def _safe_transfer_token(value: str) -> str:
    return "".join(character if character.isalnum() or character in "-_." else "_" for character in value) or "transfer"


class JsonUE5BridgeConnector:
    """Protocol endpoint for UE5-side JSON exchange and evidence checks."""

    connector_id = "ue5-json-protocol"

    def __init__(self, protocol: AssetsBridgeJsonProtocol) -> None:
        self.protocol = protocol

    def is_ready(self) -> bool:
        return self.protocol.is_ready()

    def export_asset(self, manifest: TransferManifest) -> TaskResult:
        protocol = _protocol_for_manifest(self.protocol, manifest)
        path = protocol.write("from_unreal", protocol.document_for_manifest(manifest, "UnrealExport"))
        artifact = ArtifactRef(artifact_id=f"{manifest.transfer_id}:from-unreal", kind=ArtifactKind.BUNDLE, uri=str(path), provider_id="assetsbridge")
        return TaskResult(
            status=TaskStatus.SUCCEEDED,
            route=TaskRoute.ASSET_TRANSFER.value,
            backend="assetsbridge",
            artifacts=(artifact,),
            details={"execution_mode": "protocol_only", "ue5_operation_executed": False},
            warnings=("protocol-only AssetsBridge connector: no UE5 process was executed",),
        )

    def import_asset(self, manifest: TransferManifest) -> TaskResult:
        protocol = _protocol_for_manifest(self.protocol, manifest)
        path = protocol.from_blender
        if not path.is_file():
            return TaskResult(status=TaskStatus.FAILED, route=TaskRoute.ASSET_TRANSFER.value, backend="assetsbridge", errors=(f"Bridge result file does not exist: {path}",), resume_pointer="stage.return_to_target")
        try:
            document = protocol.read("from_blender")
        except (OSError, ValueError, TypeError) as exc:
            return TaskResult(
                status=TaskStatus.FAILED,
                route=TaskRoute.ASSET_TRANSFER.value,
                backend="assetsbridge",
                errors=(f"invalid Bridge result JSON: {exc}",),
                resume_pointer="stage.return_to_target",
            )
        document_transfer_id = document.get("transfer_id") or document.get("transferId")
        if document_transfer_id is None:
            return TaskResult(
                status=TaskStatus.FAILED,
                route=TaskRoute.ASSET_TRANSFER.value,
                backend="assetsbridge",
                errors=("Bridge result is missing transfer_id; refusing a potentially stale result",),
                resume_pointer="stage.return_to_target",
            )
        if str(document_transfer_id) != manifest.transfer_id:
            return TaskResult(
                status=TaskStatus.FAILED,
                route=TaskRoute.ASSET_TRANSFER.value,
                backend="assetsbridge",
                errors=(f"Bridge result belongs to transfer {document_transfer_id}, expected {manifest.transfer_id}",),
                resume_pointer="stage.return_to_target",
            )
        objects = document.get("objects", [])
        identifiers = {
            value
            for value in (
                manifest.asset_id,
                str(manifest.metadata.get("ue5_asset_path", "")),
                str(manifest.metadata.get("model", "")),
            )
            if value
        }
        if not identifiers or not any(
            str(item.get("objectId", "")) in identifiers or str(item.get("model", "")) in identifiers
            for item in objects
        ):
            return TaskResult(status=TaskStatus.FAILED, route=TaskRoute.ASSET_TRANSFER.value, backend="assetsbridge", errors=(f"Bridge result does not contain asset identity: {manifest.asset_id}",), resume_pointer="stage.return_to_target")
        artifact = ArtifactRef(artifact_id=f"{manifest.transfer_id}:from-blender", kind=ArtifactKind.BUNDLE, uri=str(path), provider_id="assetsbridge")
        return TaskResult(
            status=TaskStatus.SUCCEEDED,
            route=TaskRoute.ASSET_TRANSFER.value,
            backend="assetsbridge",
            artifacts=(artifact,),
            details={"execution_mode": "protocol_only", "ue5_operation_executed": False},
            warnings=("protocol-only AssetsBridge connector: no UE5 process was executed",),
        )


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
        params["transfer_id"] = manifest.transfer_id
        params["bridge_dir"] = str(manifest.metadata.get("bridge_dir", self.bridge_dir))
        if manifest.metadata.get("blender_edit_file"):
            params["save_after"] = manifest.metadata["blender_edit_file"]
        result_dir = Path(str(manifest.metadata.get("result_dir", Path.cwd() / "artifacts" / "scratch" / manifest.transfer_id)))
        params.setdefault("result_file", str(result_dir / f"blender-import-{_safe_transfer_token(manifest.transfer_id)}.json"))
        return self.executor.execute(BlenderOperationRequest(task_id=f"{manifest.transfer_id}-stage-transfer-to-edit-host", operation="import-bridge-json", call_surface=self.call_surface, parameters=params))

    def export_asset(self, manifest: TransferManifest) -> TaskResult:
        params = dict(manifest.metadata)
        params["transfer_id"] = manifest.transfer_id
        params.update({"bridge_dir": str(manifest.metadata.get("bridge_dir", self.bridge_dir)), "export_file": manifest.export_file})
        if manifest.metadata.get("modified_blend_file"):
            params["blend_file"] = manifest.metadata["modified_blend_file"]
        result_dir = Path(str(manifest.metadata.get("result_dir", Path.cwd() / "artifacts" / "scratch" / manifest.transfer_id)))
        params.setdefault("result_file", str(result_dir / f"blender-export-{_safe_transfer_token(manifest.transfer_id)}.json"))
        return self.executor.execute(BlenderOperationRequest(task_id=f"{manifest.transfer_id}-stage-return-to-target", operation="export-bridge-json", call_surface=self.call_surface, parameters=params))

