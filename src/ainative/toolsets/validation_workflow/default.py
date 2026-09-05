from pathlib import Path

from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.orchestration.contracts.results import TaskResult, TaskStatus
from ainative.orchestration.contracts.task import TaskContract, TaskRoute
from ainative.orchestration.contracts.tools import ToolExecutionKind, ToolsetDefinition
from ainative.registry import toolset_from_operations


class ManifestValidator:
    """Conservative validator that reports only observable file/manifest facts."""

    validator_id = "manifest-validator"

    def toolsets(self) -> tuple[ToolsetDefinition, ...]:
        return (
            toolset_from_operations(
                toolset_id="validation.workflow",
                provider_id=self.validator_id,
                execution_kind=ToolExecutionKind.VALIDATOR,
                operations=("validate",),
                title="Manifest Validation",
                description="Validate observable file, manifest, and loss facts.",
                metadata={"observes": ["files", "manifest", "loss"]},
            ),
        )

    def validate(self, task: TaskContract, manifest: TransferManifest) -> TaskResult:
        errors: list[str] = []
        warnings: list[str] = []
        if manifest.export_file and not Path(manifest.export_file).is_file():
            errors.append(f"export artifact does not exist: {manifest.export_file}")
        if manifest.target_asset_path and not Path(manifest.target_asset_path).is_file():
            errors.append(f"target artifact does not exist: {manifest.target_asset_path}")
        observed = frozenset(manifest.metadata.get("observed_preserved_relations", ()))
        preserved = observed & task.preserve_relations
        lost = task.preserve_relations - preserved
        if lost:
            warnings.append("requested relations lack independent validation evidence: " + ", ".join(sorted(lost)))
        status = TaskStatus.SUCCEEDED if not errors and not lost else (TaskStatus.DEGRADED if not errors else TaskStatus.FAILED)
        return TaskResult(status=status, route=TaskRoute.ASSET_TRANSFER.value, preserved_relations=preserved, lost_relations=lost, warnings=tuple(warnings), errors=tuple(errors), next_action=None if status is TaskStatus.SUCCEEDED else "inspect the manifest evidence and resume validation", resume_pointer=None if status is TaskStatus.SUCCEEDED else "stage.validate_asset")
