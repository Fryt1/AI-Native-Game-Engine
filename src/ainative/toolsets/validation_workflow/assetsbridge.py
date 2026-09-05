from ainative.orchestration.contracts.artifacts import ArtifactKind, ArtifactRef
from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.orchestration.contracts.results import TaskResult, TaskStatus
from ainative.orchestration.contracts.task import TaskContract, TaskRoute
from ainative.orchestration.contracts.tools import ToolExecutionKind, ToolsetDefinition
from ainative.registry import toolset_from_operations
from ainative.toolsets.transfer_assetsbridge import AssetsBridgeJsonProtocol


class AssetsBridgeValidator:
    """Validate relations observable in AssetsBridge's from-blender JSON."""

    validator_id = "assetsbridge-validator"

    def __init__(self, protocol: AssetsBridgeJsonProtocol) -> None:
        self.protocol = protocol

    def toolsets(self) -> tuple[ToolsetDefinition, ...]:
        return (
            toolset_from_operations(
                toolset_id="validation.workflow",
                provider_id=self.validator_id,
                execution_kind=ToolExecutionKind.VALIDATOR,
                operations=("validate",),
                title="AssetsBridge Validation",
                description="Validate relations observable in AssetsBridge output.",
                metadata={"observes": ["from-blender.json", "asset_identity", "material_slots", "transform"]},
            ),
        )

    def validate(self, task: TaskContract, manifest: TransferManifest) -> TaskResult:
        path = self.protocol.from_blender
        if not path.is_file():
            return TaskResult(status=TaskStatus.FAILED, route=TaskRoute.ASSET_TRANSFER.value, backend="assetsbridge", errors=(f"missing AssetsBridge result: {path}",), resume_pointer="stage.validate_asset")
        document = self.protocol.read("from_blender")
        identifiers = {manifest.asset_id, str(manifest.metadata.get("ue5_asset_path", "")), str(manifest.metadata.get("model", ""))}
        item = next((item for item in document.get("objects", []) if str(item.get("objectId", "")) in identifiers or str(item.get("model", "")) in identifiers), None)
        if item is None:
            return TaskResult(status=TaskStatus.FAILED, route=TaskRoute.ASSET_TRANSFER.value, backend="assetsbridge", errors=(f"result has no objectId {manifest.asset_id}",), resume_pointer="stage.validate_asset")
        preserved: set[str] = set()
        identifiers = {manifest.asset_id, str(manifest.metadata.get("ue5_asset_path", "")), str(manifest.metadata.get("model", ""))}
        if str(item.get("objectId", "")) in identifiers or str(item.get("model", "")) in identifiers:
            preserved.add("asset_identity")
        if "objectMaterials" in item:
            preserved.add("material_slots")
        world = item.get("worldData") or {}
        if all(key in world for key in ("location", "rotation", "scale")):
            preserved.add("transform")
        preserved_set = frozenset(preserved & set(task.preserve_relations))
        lost = task.preserve_relations - preserved_set
        status = TaskStatus.SUCCEEDED if not lost else TaskStatus.DEGRADED
        warnings = ("requested relations are not represented in from-blender.json: " + ", ".join(sorted(lost)),) if lost else ()
        artifact = ArtifactRef(artifact_id=f"{manifest.transfer_id}:validated", kind=ArtifactKind.BUNDLE, uri=str(path), provider_id="assetsbridge")
        return TaskResult(status=status, route=TaskRoute.ASSET_TRANSFER.value, backend="assetsbridge", artifacts=(artifact,), preserved_relations=preserved_set, lost_relations=lost, details={"validated_item": item}, warnings=warnings, next_action=None if status is TaskStatus.SUCCEEDED else "inspect the bridge payload and re-run validation", resume_pointer=None if status is TaskStatus.SUCCEEDED else "stage.validate_asset")
