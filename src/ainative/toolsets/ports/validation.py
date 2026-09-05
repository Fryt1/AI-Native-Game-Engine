from typing import Protocol

from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.orchestration.contracts.results import TaskResult
from ainative.orchestration.contracts.task import TaskContract
from ainative.orchestration.contracts.tools import ToolsetDefinition


class WorkflowValidator(Protocol):
    """Seam for post-stage validation and loss reporting."""

    validator_id: str

    def toolsets(self) -> tuple[ToolsetDefinition, ...]: ...

    def validate(self, task: TaskContract, manifest: TransferManifest) -> TaskResult: ...
