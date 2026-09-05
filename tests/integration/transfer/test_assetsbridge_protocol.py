from pathlib import Path

from ainative.orchestration.contracts import TaskContract, TaskRoute
from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.toolsets.transfer_assetsbridge import AssetsBridgeJsonProtocol


def test_assetsbridge_json_protocol_uses_bidirectional_file_names(tmp_path: Path):
    task = TaskContract(
        task_id="bridge-json-1",
        objective="roundtrip a static mesh",
        route=TaskRoute.ASSET_TRANSFER,
        source_context={"app": "ue5", "asset_id": "SM_Test"},
        target_context={"app": "blender"},
    )
    manifest = TransferManifest.from_task(task)
    protocol = AssetsBridgeJsonProtocol(tmp_path)

    unreal_path = protocol.write("from_unreal", protocol.document_for_manifest(manifest, "UnrealExport"))
    blender_path = protocol.write("from_blender", protocol.document_for_manifest(manifest, "BlenderExport"))

    assert unreal_path.name == "from-unreal.json"
    assert blender_path.name == "from-blender.json"
    assert protocol.read("from_unreal")["operation"] == "UnrealExport"
    assert protocol.read("from_blender")["objects"][0]["objectId"] == "SM_Test"
