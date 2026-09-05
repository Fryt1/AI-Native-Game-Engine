import json
from pathlib import Path
from subprocess import CompletedProcess

from ainative.orchestration.contracts import TaskContract, TaskRoute, TaskStatus
from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.toolsets.transfer_assetsbridge import ExternalBlenderAssetsBridgeConnector


def _connector(tmp_path: Path, runner):
    executable = tmp_path / "blender.exe"
    executable.write_text("binary", encoding="utf-8")
    addon = tmp_path / "addon"
    addon.mkdir()
    (addon / "__init__.py").write_text("# addon", encoding="utf-8")
    bridge = tmp_path / "bridge"
    bridge.mkdir()
    return ExternalBlenderAssetsBridgeConnector(executable, addon, bridge, tmp_path / "work", runner=runner), bridge


def _manifest(transfer_id: str = "current-transfer") -> TransferManifest:
    return TransferManifest.from_task(
        TaskContract(
            task_id=transfer_id,
            objective="roundtrip",
            route=TaskRoute.ASSET_TRANSFER,
            source_context={"app": "ue5", "asset_id": "asset-1"},
            target_context={"app": "ue5"},
        )
    )


def test_external_export_cannot_reuse_stale_from_blender_file(tmp_path: Path):
    def runner(args, **kwargs):
        result_file = Path(kwargs["env"]["AINATIVE_BLENDER_RESULT_FILE"])
        result_file.parent.mkdir(parents=True, exist_ok=True)
        result_file.write_text(
            json.dumps({"status": "succeeded", "transfer_id": "current-transfer"}),
            encoding="utf-8",
        )
        return CompletedProcess(args, 0, stdout="ok", stderr="")

    connector, bridge = _connector(tmp_path, runner)
    (bridge / "from-blender.json").write_text(
        json.dumps({"transfer_id": "old-transfer", "objects": [{"objectId": "asset-1"}]}),
        encoding="utf-8",
    )

    result = connector.export_asset(_manifest())

    assert result.status is TaskStatus.FAILED
    assert "from-blender.json" in result.errors[0]
    assert "does not exist" in result.errors[0]


def test_external_import_rejects_mismatched_source_before_starting_blender(tmp_path: Path):
    called = False

    def runner(args, **kwargs):
        nonlocal called
        called = True
        return CompletedProcess(args, 0, stdout="ok", stderr="")

    connector, bridge = _connector(tmp_path, runner)
    (bridge / "from-unreal.json").write_text(
        json.dumps({"transfer_id": "old-transfer", "objects": [{"objectId": "asset-1"}]}),
        encoding="utf-8",
    )

    result = connector.import_asset(_manifest())

    assert result.status is TaskStatus.FAILED
    assert "old-transfer" in result.errors[0]
    assert not called
