from dataclasses import replace
from pathlib import Path

from ainative.orchestration.contracts import (
    TaskContract,
    TaskRoute,
    TransferBackendKind,
)
from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.toolsets.transfer_direct import FileTransferIO


def test_file_transfer_io_copies_source_to_exchange_and_target(tmp_path: Path):
    source = tmp_path / "source.glb"
    exchange = tmp_path / "exchange" / "asset.glb"
    target = tmp_path / "target" / "asset.glb"
    source.write_bytes(b"mesh-data")
    task = TaskContract(
        task_id="direct-file-1",
        objective="copy a mesh file",
        route=TaskRoute.ASSET_TRANSFER,
        preferred_backend=TransferBackendKind.DIRECT,
    )
    manifest = replace(
        TransferManifest.from_task(task),
        source_asset_path=str(source),
        export_file=str(exchange),
        target_asset_path=str(target),
    )

    io = FileTransferIO()
    exported = io.export_source(manifest)
    imported = io.import_target(manifest)

    assert exported.status.value == "succeeded"
    assert imported.status.value == "succeeded"
    assert exchange.read_bytes() == b"mesh-data"
    assert target.read_bytes() == b"mesh-data"
