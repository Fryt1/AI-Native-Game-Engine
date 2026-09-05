from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.orchestration.contracts.results import TaskResult, TaskStatus
from ainative.orchestration.contracts.task import TaskRoute
from ainative.orchestration.contracts.tools import ToolExecutionKind, ToolsetDefinition
from ainative.registry import toolset_from_operations

from .connectors import BlenderBridgeConnector, UE5BridgeConnector


class AssetsBridgeBackend:
    """Optional backend composing the UE5 and Blender Bridge connectors."""

    backend_id = "assetsbridge"

    def __init__(self, ue5_connector: UE5BridgeConnector | None = None, blender_connector: BlenderBridgeConnector | None = None) -> None:
        self.ue5_connector = ue5_connector
        self.blender_connector = blender_connector

    def is_ready(self) -> bool:
        return bool(self.ue5_connector and self.blender_connector and self.ue5_connector.is_ready() and self.blender_connector.is_ready())

    def toolsets(self) -> tuple[ToolsetDefinition, ...]:
        return (
            toolset_from_operations(
                toolset_id="transfer.assetsbridge",
                provider_id=self.backend_id,
                execution_kind=ToolExecutionKind.TRANSFER,
                operations=("transfer_to_edit_host", "return_to_target", "export_source", "import_for_edit", "export_modified", "import_target"),
                title="AssetsBridge Transfer",
                description="UE5 and Blender Bridge transfer operations.",
                metadata={"preserves": ["asset_identity", "material_slots", "transform"], "protocol": "from-unreal.json/from-blender.json"},
            ),
        )

    def _blocked(self, message: str) -> TaskResult:
        return TaskResult(status=TaskStatus.BLOCKED, route=TaskRoute.ASSET_TRANSFER.value, backend=self.backend_id, errors=(message,), next_action="repair the AssetsBridge branch or explicitly re-plan with Direct Transfer")

    def export_source(self, manifest: TransferManifest) -> TaskResult:
        if not self.is_ready():
            return self._blocked("AssetsBridge connectors are not ready")
        if manifest.source_app.lower() == "ue5":
            return self.ue5_connector.export_asset(manifest)  # type: ignore[union-attr]
        if manifest.source_app.lower() == "blender":
            return self.blender_connector.export_asset(manifest)  # type: ignore[union-attr]
        return self._blocked(f"unsupported AssetsBridge source app: {manifest.source_app}")

    def import_for_edit(self, manifest: TransferManifest) -> TaskResult:
        if not self.is_ready():
            return self._blocked("AssetsBridge connectors are not ready")
        if manifest.edit_app.lower() == "blender":
            return self.blender_connector.import_asset(manifest)  # type: ignore[union-attr]
        return self._blocked(f"AssetsBridge edit target must be Blender, got: {manifest.edit_app}")

    def export_modified(self, manifest: TransferManifest) -> TaskResult:
        if not self.is_ready():
            return self._blocked("AssetsBridge connectors are not ready")
        if manifest.edit_app.lower() == "blender":
            return self.blender_connector.export_asset(manifest)  # type: ignore[union-attr]
        return self._blocked(f"AssetsBridge edit source must be Blender, got: {manifest.edit_app}")

    def import_target(self, manifest: TransferManifest) -> TaskResult:
        if not self.is_ready():
            return self._blocked("AssetsBridge connectors are not ready")
        if manifest.target_app.lower() == "ue5":
            return self.ue5_connector.import_asset(manifest)  # type: ignore[union-attr]
        if manifest.target_app.lower() == "blender":
            return self.blender_connector.import_asset(manifest)  # type: ignore[union-attr]
        return self._blocked(f"unsupported AssetsBridge target app: {manifest.target_app}")
