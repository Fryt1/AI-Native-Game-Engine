from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ainative.orchestration.contracts.manifest import TransferManifest


@dataclass(frozen=True, slots=True)
class AssetsBridgeJsonProtocol:
    """File protocol used by the AssetsBridge UE5 plugin and Blender add-on."""

    bridge_dir: Path

    @property
    def from_unreal(self) -> Path:
        return self.bridge_dir / "from-unreal.json"

    @property
    def from_blender(self) -> Path:
        return self.bridge_dir / "from-blender.json"

    def is_ready(self) -> bool:
        return self.bridge_dir.is_dir()

    def _path_for(self, direction: str) -> Path:
        if direction == "from_unreal":
            return self.from_unreal
        if direction == "from_blender":
            return self.from_blender
        raise ValueError(f"unsupported AssetsBridge JSON direction: {direction}")

    def read(self, direction: str) -> dict[str, Any]:
        return json.loads(self._path_for(direction).read_text(encoding="utf-8"))

    def write(self, direction: str, document: dict[str, Any]) -> Path:
        path = self._path_for(direction)
        self.bridge_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def document_for_manifest(self, manifest: TransferManifest, operation: str) -> dict[str, Any]:
        """Build the subset of the public Bridge JSON shape we own."""

        object_data = {
            "model": manifest.metadata.get("model", ""),
            "objectId": manifest.asset_id,
            "internalPath": manifest.metadata.get("internalPath", ""),
            "relativeExportPath": manifest.metadata.get("relativeExportPath", ""),
            "shortName": manifest.metadata.get("shortName", Path(manifest.export_file or manifest.asset_id).stem),
            "exportLocation": manifest.metadata.get("source_export_file", manifest.export_file or ""),
            "stringType": "SkeletalMesh" if manifest.metadata.get("asset_type") == "skeletal_mesh" else "StaticMesh",
            "skeleton": manifest.metadata.get("skeleton", ""),
            "worldData": manifest.metadata.get("worldData", {"rotation": {"x": 0, "y": 0, "z": 0}, "location": {"x": 0, "y": 0, "z": 0}, "scale": {"x": 1, "y": 1, "z": 1}}),
            "objectMaterials": manifest.metadata.get("objectMaterials", []),
            "materialChangeset": manifest.metadata.get("materialChangeset", {"added": [], "removed": [], "unchanged": []}),
            "textures": manifest.metadata.get("textures", {}),
        }
        return {"operation": operation, "objects": [object_data]}
