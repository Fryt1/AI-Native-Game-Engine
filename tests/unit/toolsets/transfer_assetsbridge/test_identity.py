from pathlib import Path

from ainative.orchestration.contracts import TaskContract, TaskRoute, TaskStatus
from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.toolsets.transfer_assetsbridge import (
    AssetsBridgeJsonProtocol,
    JsonUE5BridgeConnector,
)
from ainative.toolsets.validation_workflow import AssetsBridgeValidator


def test_json_ue5_connector_accepts_model_path_when_object_id_is_empty(tmp_path: Path):
    protocol = AssetsBridgeJsonProtocol(tmp_path)
    task = TaskContract(task_id="model-id", objective="import", route=TaskRoute.ASSET_TRANSFER, source_context={"app": "ue5", "asset_id": "/Engine/BasicShapes/Cube.Cube"}, target_context={"app": "ue5"}, metadata={"ue5_asset_path": "/Engine/BasicShapes/Cube.Cube"})
    manifest = TransferManifest.from_task(task)
    protocol.write("from_blender", {"operation": "BlenderExport", "transfer_id": manifest.transfer_id, "objects": [{"objectId": "", "model": "/Engine/BasicShapes/Cube.Cube"}]})

    result = JsonUE5BridgeConnector(protocol).import_asset(manifest)

    assert result.status.value == "succeeded"


def test_assetsbridge_validator_requires_source_snapshot_for_materials_and_transform(tmp_path: Path):
    protocol = AssetsBridgeJsonProtocol(tmp_path)
    task = TaskContract(
        task_id="validator-1",
        objective="validate",
        route=TaskRoute.ASSET_TRANSFER,
        preserve_relations=frozenset({"asset_identity", "material_slots", "transform"}),
        source_context={"app": "ue5", "asset_id": "asset-1"},
        target_context={"app": "ue5"},
        metadata={"delta": [1, 0, 0]},
    )
    manifest = TransferManifest.from_task(task)
    protocol.write("from_unreal", protocol.document_for_manifest(manifest, "UnrealExport"))
    protocol.write(
        "from_blender",
        {
            "operation": "BlenderExport",
            "transfer_id": manifest.transfer_id,
            "objects": [
                {
                    "objectId": "asset-1",
                    "objectMaterials": ["wrong-material"],
                    "worldData": {
                        "location": {"x": 999, "y": 0, "z": 0},
                        "rotation": {"x": 0, "y": 0, "z": 0},
                        "scale": {"x": 1, "y": 1, "z": 1},
                    },
                }
            ],
        },
    )

    result = AssetsBridgeValidator(protocol).validate(task, manifest)

    assert result.status is TaskStatus.DEGRADED
    assert result.preserved_relations == frozenset({"asset_identity"})
    assert result.lost_relations == frozenset({"material_slots", "transform"})



def test_assetsbridge_validator_ignores_original_index_bookkeeping_for_material_slots(tmp_path: Path):
    protocol = AssetsBridgeJsonProtocol(tmp_path)
    task = TaskContract(
        task_id="material-bookkeeping",
        objective="validate",
        route=TaskRoute.ASSET_TRANSFER,
        preserve_relations=frozenset({"asset_identity", "material_slots", "transform"}),
        source_context={"app": "ue5", "asset_id": "asset-1"},
        target_context={"app": "ue5"},
        metadata={"delta": [1, 0, 0], "objectMaterials": [{"name": "OriginalMaterial", "idx": 0, "internalPath": "/Game/M", "originalIdx": -1}]},
    )
    manifest = TransferManifest.from_task(task)
    protocol.write("from_unreal", protocol.document_for_manifest(manifest, "UnrealExport"))
    protocol.write(
        "from_blender",
        {
            "operation": "BlenderExport",
            "transfer_id": manifest.transfer_id,
            "objects": [
                {
                    "objectId": "asset-1",
                    "objectMaterials": [{"name": "Material.001", "idx": 0, "internalPath": "/Game/M", "originalIdx": 0}],
                    "worldData": {
                        "location": {"x": 1, "y": 0, "z": 0},
                        "rotation": {"x": 0, "y": 0, "z": 0},
                        "scale": {"x": 1, "y": 1, "z": 1},
                    },
                }
            ],
        },
    )

    result = AssetsBridgeValidator(protocol).validate(task, manifest)

    assert result.status is TaskStatus.SUCCEEDED
    assert result.preserved_relations == task.preserve_relations
