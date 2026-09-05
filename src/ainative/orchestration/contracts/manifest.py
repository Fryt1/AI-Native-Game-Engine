from dataclasses import dataclass, field, replace
from typing import Any

from .task import TaskContract


@dataclass(frozen=True, slots=True)
class TransferManifest:
    """Cross-host identity and mapping facts owned by a transfer Workflow."""

    transfer_id: str
    asset_id: str
    source_app: str
    target_app: str
    edit_app: str = "blender"
    source_asset_path: str | None = None
    source_object_path: str | None = None
    target_asset_path: str | None = None
    export_file: str | None = None
    file_format: str | None = None
    source_revision: str | None = None
    selected_route: str | None = None
    selected_workflow: str | None = None
    selected_profile: str | None = None
    selected_backend: str | None = None
    selected_modification_method: str | None = None
    call_surfaces: tuple[str, ...] = ()
    object_mapping: dict[str, str] = field(default_factory=dict)
    material_mapping: dict[str, str] = field(default_factory=dict)
    skeleton_mapping: dict[str, str] = field(default_factory=dict)
    morph_mapping: dict[str, str] = field(default_factory=dict)
    transform_mapping: dict[str, Any] = field(default_factory=dict)
    preserved_relations: frozenset[str] = field(default_factory=frozenset)
    lost_relations: frozenset[str] = field(default_factory=frozenset)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_task(cls, task: TaskContract) -> "TransferManifest":
        return cls(
            transfer_id=task.task_id,
            asset_id=str(task.source_context.get("asset_id", task.task_id)),
            source_app=str(task.source_context.get("app", "ue5")),
            target_app=str(task.target_context.get("app", "ue5")),
            edit_app=str(task.metadata.get("edit_app", "blender")),
            source_asset_path=task.source_context.get("asset_path"),
            source_object_path=task.source_context.get("object_path"),
            target_asset_path=task.target_context.get("asset_path"),
            export_file=task.metadata.get("export_file"),
            file_format=task.metadata.get("file_format"),
            source_revision=task.source_context.get("revision"),
            selected_route=task.route.value,
            selected_workflow=task.preferred_workflow_id,
            selected_profile=task.profile,
            preserved_relations=task.preserve_relations,
            metadata={**task.metadata, "asset_type": task.asset_type, "direction": task.direction},
        )

    def with_execution_selection(self, *, backend: str | None, modification_method: str | None, call_surface: str | None, workflow_id: str | None = None) -> "TransferManifest":
        return replace(
            self,
            selected_workflow=workflow_id or self.selected_workflow,
            selected_backend=backend,
            selected_modification_method=modification_method,
            call_surfaces=(call_surface,) if call_surface else self.call_surfaces,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "transfer_id": self.transfer_id,
            "asset_id": self.asset_id,
            "source_app": self.source_app,
            "target_app": self.target_app,
            "edit_app": self.edit_app,
            "source_asset_path": self.source_asset_path,
            "source_object_path": self.source_object_path,
            "target_asset_path": self.target_asset_path,
            "export_file": self.export_file,
            "file_format": self.file_format,
            "source_revision": self.source_revision,
            "selected_route": self.selected_route,
            "selected_workflow": self.selected_workflow,
            "selected_profile": self.selected_profile,
            "selected_backend": self.selected_backend,
            "selected_modification_method": self.selected_modification_method,
            "call_surfaces": list(self.call_surfaces),
            "object_mapping": self.object_mapping,
            "material_mapping": self.material_mapping,
            "skeleton_mapping": self.skeleton_mapping,
            "morph_mapping": self.morph_mapping,
            "transform_mapping": self.transform_mapping,
            "preserved_relations": sorted(self.preserved_relations),
            "lost_relations": sorted(self.lost_relations),
            "metadata": self.metadata,
        }

