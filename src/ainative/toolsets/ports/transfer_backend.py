from typing import Protocol

from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.orchestration.contracts.results import TaskResult
from ainative.orchestration.contracts.tools import ToolsetDefinition


class AssetTransferBackend(Protocol):
    """Seam for one cross-host transfer implementation."""

    backend_id: str

    def is_ready(self) -> bool: ...

    def toolsets(self) -> tuple[ToolsetDefinition, ...]: ...

    def export_source(self, manifest: TransferManifest) -> TaskResult: ...

    def import_for_edit(self, manifest: TransferManifest) -> TaskResult: ...

    def export_modified(self, manifest: TransferManifest) -> TaskResult: ...

    def import_target(self, manifest: TransferManifest) -> TaskResult: ...
