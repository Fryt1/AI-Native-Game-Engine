from __future__ import annotations

from copy import deepcopy
from math import isclose
from pathlib import Path
from typing import Any

from ainative.orchestration.contracts.artifacts import ArtifactKind, ArtifactRef
from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.orchestration.contracts.results import TaskResult, TaskStatus
from ainative.orchestration.contracts.task import TaskContract, TaskRoute
from ainative.orchestration.contracts.tools import ToolExecutionKind, ToolsetDefinition
from ainative.registry import toolset_from_operations
from ainative.toolsets.transfer_assetsbridge import AssetsBridgeJsonProtocol


class AssetsBridgeValidator:
    """Validate AssetsBridge output against the source snapshot and task facts.

    Presence of a JSON key is not enough to claim that a relation survived. The
    validator requires a source ``from-unreal.json`` snapshot for material and
    transform relations, then compares the result with either an explicit
    expected snapshot or the requested transform delta.
    """

    validator_id = "assetsbridge-validator"

    def __init__(self, protocol: AssetsBridgeJsonProtocol) -> None:
        self.protocol = protocol

    def toolsets(self) -> tuple[ToolsetDefinition, ...]:
        return (
            toolset_from_operations(
                toolset_id="validation.workflow",
                provider_id=self.validator_id,
                execution_kind=ToolExecutionKind.VALIDATOR,
                operations=("validate",),
                title="AssetsBridge Validation",
                description="Validate source/result identity and preserved AssetsBridge relations.",
                metadata={"observes": ["from-unreal.json", "from-blender.json", "asset_identity", "material_slots", "transform"]},
            ),
        )

    def validate(self, task: TaskContract, manifest: TransferManifest) -> TaskResult:
        bridge_dir = Path(str(manifest.metadata.get("bridge_dir", self.protocol.bridge_dir)))
        protocol = AssetsBridgeJsonProtocol(bridge_dir)
        result_path = protocol.from_blender
        if not result_path.is_file():
            return TaskResult(
                status=TaskStatus.FAILED,
                route=TaskRoute.ASSET_TRANSFER.value,
                backend="assetsbridge",
                errors=(f"missing AssetsBridge result: {result_path}",),
                resume_pointer="stage.validate_asset",
            )

        try:
            result_document = protocol.read("from_blender")
        except (OSError, ValueError, TypeError) as exc:
            return TaskResult(
                status=TaskStatus.FAILED,
                route=TaskRoute.ASSET_TRANSFER.value,
                backend="assetsbridge",
                errors=(f"invalid AssetsBridge result JSON: {exc}",),
                resume_pointer="stage.validate_asset",
            )

        source_document: dict[str, Any] = {}
        source_path = protocol.from_unreal
        if source_path.is_file():
            try:
                source_document = protocol.read("from_unreal")
            except (OSError, ValueError, TypeError) as exc:
                return TaskResult(
                    status=TaskStatus.FAILED,
                    route=TaskRoute.ASSET_TRANSFER.value,
                    backend="assetsbridge",
                    errors=(f"invalid AssetsBridge source JSON: {exc}",),
                    resume_pointer="stage.validate_asset",
                )

        expected_transfer_id = manifest.transfer_id
        result_transfer_id = result_document.get("transfer_id") or result_document.get("transferId")
        if result_transfer_id is None:
            return TaskResult(
                status=TaskStatus.FAILED,
                route=TaskRoute.ASSET_TRANSFER.value,
                backend="assetsbridge",
                errors=("result is missing transfer_id; refusing a potentially stale result",),
                resume_pointer="stage.validate_asset",
            )
        if str(result_transfer_id) != expected_transfer_id:
            return TaskResult(
                status=TaskStatus.FAILED,
                route=TaskRoute.ASSET_TRANSFER.value,
                backend="assetsbridge",
                errors=(f"result belongs to transfer {result_transfer_id}, expected {expected_transfer_id}",),
                resume_pointer="stage.validate_asset",
            )

        result_item = self._find_item(result_document, manifest)
        if result_item is None:
            return TaskResult(
                status=TaskStatus.FAILED,
                route=TaskRoute.ASSET_TRANSFER.value,
                backend="assetsbridge",
                errors=(f"result has no object identity for asset {manifest.asset_id}",),
                resume_pointer="stage.validate_asset",
            )
        source_item = self._find_item(source_document, manifest) if source_document else None

        preserved: set[str] = set()
        warnings: list[str] = []
        lost: set[str] = set()

        if self._identity_matches(result_item, manifest, source_item):
            preserved.add("asset_identity")
        elif "asset_identity" in task.preserve_relations:
            lost.add("asset_identity")

        if "material_slots" in task.preserve_relations:
            expected_materials = manifest.metadata.get("expected_materials")
            source_materials = source_item.get("objectMaterials") if source_item is not None else None
            actual_materials = result_item.get("objectMaterials")
            if expected_materials is not None:
                material_ok = self._same_json(
                    self._material_slots(actual_materials),
                    self._material_slots(expected_materials),
                )
            else:
                material_ok = source_materials is not None and self._same_json(
                    self._material_slots(actual_materials),
                    self._material_slots(source_materials),
                )
            if material_ok:
                preserved.add("material_slots")
            else:
                lost.add("material_slots")
                warnings.append("material slots lack an exact source/expected snapshot comparison")

        if "transform" in task.preserve_relations:
            source_world = self._world_data(source_item)
            actual_world = self._world_data(result_item)
            expected_world = self._expected_world_data(manifest, source_world)
            if expected_world is not None and actual_world is not None and self._same_json(actual_world, expected_world, tolerance=1e-4):
                preserved.add("transform")
            else:
                lost.add("transform")
                warnings.append("transform lacks an exact source/expected snapshot comparison")

        for relation in sorted(task.preserve_relations - {"asset_identity", "material_slots", "transform"}):
            observed = set(manifest.metadata.get("observed_preserved_relations", ()))
            if relation in observed:
                preserved.add(relation)
            else:
                lost.add(relation)

        preserved_set = frozenset(preserved & set(task.preserve_relations))
        lost_set = frozenset(lost | (task.preserve_relations - preserved_set))
        if lost_set:
            warnings.append("requested relations were not proven by source/result evidence: " + ", ".join(sorted(lost_set)))
        status = TaskStatus.SUCCEEDED if not lost_set else TaskStatus.DEGRADED
        artifact = ArtifactRef(
            artifact_id=f"{manifest.transfer_id}:validated",
            kind=ArtifactKind.BUNDLE,
            uri=str(result_path),
            provider_id="assetsbridge",
        )
        return TaskResult(
            status=status,
            route=TaskRoute.ASSET_TRANSFER.value,
            backend="assetsbridge",
            artifacts=(artifact,),
            preserved_relations=preserved_set,
            lost_relations=lost_set,
            details={
                "validated_item": result_item,
                "source_item": source_item,
                "validation_mode": "source_snapshot_and_expected_values",
            },
            warnings=tuple(dict.fromkeys(warnings)),
            next_action=None if status is TaskStatus.SUCCEEDED else "inspect source/result evidence and re-run validation",
            resume_pointer=None if status is TaskStatus.SUCCEEDED else "stage.validate_asset",
        )

    @staticmethod
    def _find_item(document: dict[str, Any], manifest: TransferManifest) -> dict[str, Any] | None:
        identifiers = {
            value
            for value in (
                manifest.asset_id,
                str(manifest.metadata.get("ue5_asset_path", "")),
                str(manifest.metadata.get("model", "")),
            )
            if value
        }
        if not identifiers:
            return None
        return next(
            (
                item
                for item in document.get("objects", [])
                if isinstance(item, dict)
                and (
                    str(item.get("objectId", "")) in identifiers
                    or str(item.get("model", "")) in identifiers
                )
            ),
            None,
        )

    @classmethod
    def _identity_matches(
        cls,
        result_item: dict[str, Any],
        manifest: TransferManifest,
        source_item: dict[str, Any] | None,
    ) -> bool:
        result_tokens = {str(result_item.get("objectId", "")), str(result_item.get("model", ""))} - {""}
        expected_tokens = {
            value
            for value in (
                manifest.asset_id,
                str(manifest.metadata.get("ue5_asset_path", "")),
                str(manifest.metadata.get("model", "")),
            )
            if value
        }
        if not result_tokens or not result_tokens.intersection(expected_tokens):
            return False
        if source_item is None:
            return True
        source_tokens = {str(source_item.get("objectId", "")), str(source_item.get("model", ""))} - {""}
        return bool(result_tokens.intersection(source_tokens))

    @staticmethod
    def _material_slots(value: Any) -> list[Any] | None:
        """Normalize material slots while ignoring exporter bookkeeping fields."""

        if not isinstance(value, (list, tuple)):
            return None
        normalized: list[Any] = []
        for slot in value:
            if not isinstance(slot, dict):
                normalized.append(slot)
                continue
            normalized.append(
                {
                    "idx": slot.get("idx"),
                    "internalPath": slot.get("internalPath"),
                }
            )
        return normalized

    @classmethod
    def _expected_world_data(
        cls,
        manifest: TransferManifest,
        source_world: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        explicit = manifest.metadata.get("expected_world_data") or manifest.metadata.get("expected_worldData")
        if explicit is not None:
            return cls._world_data({"worldData": explicit})
        if source_world is None:
            return None
        expected = deepcopy(source_world)
        delta = manifest.metadata.get("delta")
        if isinstance(delta, (list, tuple)) and len(delta) == 3:
            expected["location"] = [left + float(right) for left, right in zip(expected["location"], delta)]
        return expected

    @staticmethod
    def _world_data(item: dict[str, Any] | None) -> dict[str, Any] | None:
        if item is None:
            return None
        raw = item.get("worldData")
        if not isinstance(raw, dict):
            return None
        normalized: dict[str, Any] = {}
        for key in ("location", "rotation", "scale"):
            value = raw.get(key)
            if isinstance(value, dict):
                value = [value.get(axis) for axis in ("x", "y", "z")]
            if not isinstance(value, (list, tuple)) or len(value) != 3:
                return None
            try:
                normalized[key] = [float(component) for component in value]
            except (TypeError, ValueError):
                return None
        return normalized

    @classmethod
    def _same_json(cls, actual: Any, expected: Any, tolerance: float | None = None) -> bool:
        if tolerance is not None and isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
            return len(actual) == len(expected) and all(cls._same_json(left, right, tolerance) for left, right in zip(actual, expected))
        if tolerance is not None and isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            return isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=tolerance)
        return actual == expected
