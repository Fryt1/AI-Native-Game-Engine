from typing import Protocol

from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.orchestration.contracts.results import TaskResult, TaskStatus
from ainative.orchestration.contracts.task import TaskRoute
from ainative.orchestration.contracts.tools import ToolExecutionKind, ToolsetDefinition
from ainative.registry import toolset_from_operations


class DirectTransferIO(Protocol):
    def is_ready(self) -> bool: ...

    def export_source(self, manifest: TransferManifest) -> TaskResult: ...

    def import_target(self, manifest: TransferManifest) -> TaskResult: ...


class DirectTransferBackend:
    """File-level transfer backend selected when its loss is accepted."""

    backend_id = "direct"

    def __init__(self, io: DirectTransferIO | None = None) -> None:
        self.io = io

    def is_ready(self) -> bool:
        return self.io is not None and self.io.is_ready()

    def toolsets(self) -> tuple[ToolsetDefinition, ...]:
        return (
            toolset_from_operations(
                toolset_id="transfer.direct",
                provider_id=self.backend_id,
                execution_kind=ToolExecutionKind.TRANSFER,
                operations=("transfer_to_edit_host", "return_to_target", "export_source", "import_for_edit", "export_modified", "import_target"),
                title="Direct Transfer",
                description="File-level transfer operations with an explicit loss model.",
                metadata={"loss_model": "file-level copy; identity restoration is not guaranteed"},
            ),
        )

    def _blocked(self) -> TaskResult:
        return TaskResult(status=TaskStatus.BLOCKED, route=TaskRoute.ASSET_TRANSFER.value, backend=self.backend_id, errors=("Direct Transfer I/O is not ready",), next_action="configure the exchange-file surface")

    def export_source(self, manifest: TransferManifest) -> TaskResult:
        return self.io.export_source(manifest) if self.is_ready() else self._blocked()  # type: ignore[union-attr]

    def import_for_edit(self, manifest: TransferManifest) -> TaskResult:
        if not self.is_ready():
            return self._blocked()
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value, backend=self.backend_id)

    def export_modified(self, manifest: TransferManifest) -> TaskResult:
        if not self.is_ready():
            return self._blocked()
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value, backend=self.backend_id)

    def import_target(self, manifest: TransferManifest) -> TaskResult:
        return self.io.import_target(manifest) if self.is_ready() else self._blocked()  # type: ignore[union-attr]
