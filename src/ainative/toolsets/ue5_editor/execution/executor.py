from typing import Protocol

from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.orchestration.contracts.results import TaskResult
from ainative.toolsets.ports.host_executor import HostExecutor


class UE5Executor(HostExecutor, Protocol):
    """Host seam for UE5 Editor and project operations."""

    executor_id: str
    host_id: str

    def export_asset(self, manifest: TransferManifest) -> TaskResult: ...

    def import_asset(self, manifest: TransferManifest) -> TaskResult: ...
