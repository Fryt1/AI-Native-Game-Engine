from pathlib import Path

from ainative.orchestration.contracts import TaskContract, TaskRoute
from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.toolsets.transfer_assetsbridge import (
    AssetsBridgeJsonProtocol,
    JsonUE5BridgeConnector,
)


def test_json_ue5_connector_accepts_model_path_when_object_id_is_empty(tmp_path: Path):
    protocol = AssetsBridgeJsonProtocol(tmp_path)
    task = TaskContract(task_id="model-id", objective="import", route=TaskRoute.ASSET_TRANSFER, source_context={"app": "ue5", "asset_id": "/Engine/BasicShapes/Cube.Cube"}, target_context={"app": "ue5"}, metadata={"ue5_asset_path": "/Engine/BasicShapes/Cube.Cube"})
    manifest = TransferManifest.from_task(task)
    protocol.write("from_blender", {"operation": "BlenderExport", "objects": [{"objectId": "", "model": "/Engine/BasicShapes/Cube.Cube"}]})

    result = JsonUE5BridgeConnector(protocol).import_asset(manifest)

    assert result.status.value == "succeeded"
