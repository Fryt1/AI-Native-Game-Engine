import shutil
from pathlib import Path

from ainative.orchestration.contracts.artifacts import ArtifactKind, ArtifactRef
from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.orchestration.contracts.results import TaskResult, TaskStatus
from ainative.orchestration.contracts.task import TaskRoute


class FileTransferIO:
    """Concrete exchange-file implementation for Direct Transfer."""

    def is_ready(self) -> bool:
        return True

    def export_source(self, manifest: TransferManifest) -> TaskResult:
        if not manifest.source_asset_path or not manifest.export_file:
            return TaskResult(status=TaskStatus.BLOCKED, route=TaskRoute.ASSET_TRANSFER.value, backend="direct", errors=("source_asset_path and export_file are required",), next_action="provide explicit exchange paths")
        source = Path(manifest.source_asset_path)
        target = Path(manifest.export_file)
        if not source.is_file():
            return TaskResult(status=TaskStatus.FAILED, route=TaskRoute.ASSET_TRANSFER.value, backend="direct", errors=(f"source asset does not exist: {source}",), resume_pointer="stage.transfer_to_edit_host")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        artifact = ArtifactRef(artifact_id=f"{manifest.transfer_id}:export", kind=ArtifactKind.BUNDLE, uri=str(target), provider_id="direct")
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value, backend="direct", artifacts=(artifact,))

    def import_for_edit(self, manifest: TransferManifest) -> TaskResult:
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value, backend="direct")

    def export_modified(self, manifest: TransferManifest) -> TaskResult:
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value, backend="direct")

    def import_target(self, manifest: TransferManifest) -> TaskResult:
        if not manifest.export_file or not manifest.target_asset_path:
            return TaskResult(status=TaskStatus.BLOCKED, route=TaskRoute.ASSET_TRANSFER.value, backend="direct", errors=("export_file and target_asset_path are required",), next_action="provide explicit target paths")
        source = Path(manifest.export_file)
        target = Path(manifest.target_asset_path)
        if not source.is_file():
            return TaskResult(status=TaskStatus.FAILED, route=TaskRoute.ASSET_TRANSFER.value, backend="direct", errors=(f"exchange artifact does not exist: {source}",), resume_pointer="stage.return_to_target")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        artifact = ArtifactRef(artifact_id=f"{manifest.transfer_id}:target", kind=ArtifactKind.BUNDLE, uri=str(target), provider_id="direct")
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value, backend="direct", artifacts=(artifact,))

