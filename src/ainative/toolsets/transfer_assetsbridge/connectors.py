from typing import Protocol

from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.orchestration.contracts.results import TaskResult


class UE5BridgeConnector(Protocol):
    connector_id: str

    def is_ready(self) -> bool: ...

    def export_asset(self, manifest: TransferManifest) -> TaskResult: ...

    def import_asset(self, manifest: TransferManifest) -> TaskResult: ...


class BlenderBridgeConnector(Protocol):
    connector_id: str

    def is_ready(self) -> bool: ...

    def import_asset(self, manifest: TransferManifest) -> TaskResult: ...

    def export_asset(self, manifest: TransferManifest) -> TaskResult: ...
