"""Blender-side operations used by the Add-on and CLI entry point."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _module(bpy_module: Any | None) -> Any:
    if bpy_module is not None:
        return bpy_module
    import bpy  # type: ignore[import-not-found]

    return bpy


def _vector(value: Any, default=(0.0, 0.0, 0.0)) -> tuple[float, float, float]:
    values = value if value is not None else default
    if len(values) != 3:
        raise ValueError("vector values must have three numbers")
    return tuple(float(item) for item in values)


def _object_summary(obj: Any) -> dict[str, Any]:
    return {
        "name": obj.name,
        "type": obj.type,
        "location": list(obj.location),
        "rotation_euler": list(obj.rotation_euler),
        "scale": list(obj.scale),
    }


def _configure_scene_for_unreal(bpy: Any) -> bool:
    units = bpy.context.scene.unit_settings
    changed = False
    if units.system != "METRIC":
        units.system = "METRIC"
        changed = True
    if abs(units.scale_length - 0.01) > 0.0001:
        units.scale_length = 0.01
        changed = True
    return changed


def _bridge_directory(params: dict[str, Any]) -> Path:
    value = params.get("bridge_dir")
    if not value:
        raise ValueError("bridge operation requires parameters['bridge_dir']")
    path = Path(str(value)).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _apply_bridge_item(obj: Any, item: dict[str, Any]) -> None:
    obj["AB_objectId"] = str(item.get("objectId", ""))
    obj["AB_model"] = str(item.get("model", ""))
    obj["AB_internalPath"] = str(item.get("internalPath", ""))
    obj["AB_relativeExportPath"] = str(item.get("relativeExportPath", ""))
    obj["AB_shortName"] = str(item.get("shortName", obj.name))
    obj["AB_exportLocation"] = str(item.get("exportLocation", ""))
    obj["AB_stringType"] = str(item.get("stringType", "StaticMesh"))
    obj["AB_ue5SkeletonPath"] = str(item.get("skeleton", ""))
    obj["AB_isExportRoot"] = True
    obj["AB_objectMaterials"] = item.get("objectMaterials", [])
    world = item.get("worldData") or {}
    if world.get("location"):
        obj.location = _vector([world["location"].get(axis, 0.0) for axis in ("x", "y", "z")])
    if world.get("rotation"):
        import math
        obj.rotation_euler = tuple(math.radians(float(world["rotation"].get(axis, 0.0))) for axis in ("x", "y", "z"))
    if world.get("scale"):
        obj.scale = _vector([world["scale"].get(axis, 1.0) for axis in ("x", "y", "z")], default=(1.0, 1.0, 1.0))


def _bridge_import(bpy: Any, params: dict[str, Any]) -> dict[str, Any]:
    _configure_scene_for_unreal(bpy)
    bridge = _bridge_directory(params)
    source = bridge / "from-unreal.json"
    if not source.is_file():
        return {"status": "failed", "errors": [f"Bridge file does not exist: {source}"]}
    document = json.loads(source.read_text(encoding="utf-8"))
    imported = []
    for item in document.get("objects", []):
        object_id = str(item.get("objectId", ""))
        existing = next((obj for obj in bpy.data.objects if obj.get("AB_objectId") == object_id), None) if object_id else None
        if existing is None:
            filepath = str(item.get("exportLocation", ""))
            if not filepath or not Path(filepath).is_file():
                return {"status": "failed", "errors": [f"Bridge export file does not exist: {filepath}"]}
            bpy.ops.import_scene.gltf(filepath=filepath, merge_vertices=False, import_shading="NORMALS", import_pack_images=True)
            existing = getattr(bpy.context, "active_object", None)
        if existing is None:
            return {"status": "failed", "errors": ["Blender did not create an active object for Bridge import"]}
        _apply_bridge_item(existing, item)
        imported.append(_object_summary(existing))
    return {"status": "succeeded", "objects": imported, "bridge_file": str(source)}


def _bridge_materials(obj: Any) -> list[dict[str, Any]]:
    if obj.type != "MESH" or not getattr(obj.data, "materials", None):
        return list(obj.get("AB_objectMaterials", []))
    original = {item.get("idx"): item for item in obj.get("AB_objectMaterials", []) if isinstance(item, dict)}
    result = []
    for idx, material in enumerate(obj.data.materials):
        stored = original.get(idx, {})
        result.append({"name": material.name if material else f"Material_{idx}", "idx": idx, "internalPath": stored.get("internalPath", "/Engine/EngineMaterials/WorldGridMaterial"), "originalIdx": stored.get("idx", -1)})
    return result


def _bridge_export(bpy: Any, params: dict[str, Any]) -> dict[str, Any]:
    bridge = _bridge_directory(params)
    obj = getattr(bpy.context, "active_object", None)
    if obj is None:
        return {"status": "failed", "errors": ["no active Blender object"]}
    short_name = str(obj.get("AB_shortName", obj.name))
    export_location_value = params.get("export_file") or obj.get("AB_exportLocation") or bridge / f"{short_name}.glb"
    export_location = Path(str(export_location_value))
    export_location.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(filepath=str(export_location), export_format="GLB", use_selection=True, export_apply=True, export_materials="EXPORT", export_extras=True, export_cameras=False, export_lights=False, export_draco_mesh_compression_enable=False)
    item = {
        "model": str(obj.get("AB_model", "")),
        "objectId": str(obj.get("AB_objectId", "")),
        "internalPath": str(obj.get("AB_internalPath", "")),
        "relativeExportPath": str(obj.get("AB_relativeExportPath", "")),
        "shortName": short_name,
        "exportLocation": str(export_location),
        "stringType": str(obj.get("AB_stringType", "StaticMesh")),
        "skeleton": str(obj.get("AB_ue5SkeletonPath", "")),
        "worldData": {"rotation": {"x": float(obj.rotation_euler.x * 57.295779513), "y": float(obj.rotation_euler.y * 57.295779513), "z": float(obj.rotation_euler.z * 57.295779513)}, "location": {"x": float(obj.location.x), "y": float(obj.location.y), "z": float(obj.location.z)}, "scale": {"x": float(obj.scale.x), "y": float(obj.scale.y), "z": float(obj.scale.z)}},
        "objectMaterials": _bridge_materials(obj),
        "materialChangeset": {"added": [], "removed": [], "unchanged": _bridge_materials(obj)},
        "textures": {},
    }
    target = bridge / "from-blender.json"
    target.write_text(json.dumps({"operation": "BlenderExport", "objects": [item]}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "succeeded", "objects": [item], "bridge_file": str(target)}


def execute_operation(operation: str, parameters: dict[str, Any] | None = None, bpy_module: Any | None = None) -> dict[str, Any]:
    """Execute a deterministic operation against a Blender context."""

    bpy = _module(bpy_module)
    params = parameters or {}
    active = getattr(getattr(bpy, "context", None), "active_object", None)

    if operation == "inspect-active":
        if active is None:
            return {"status": "failed", "errors": ["no active Blender object"]}
        return {"status": "succeeded", "object": _object_summary(active)}
    if operation == "configure-scene-unreal":
        return {"status": "succeeded", "changed": _configure_scene_for_unreal(bpy)}
    if operation == "import-bridge-json":
        result = _bridge_import(bpy, params)
        if result.get("status") == "succeeded" and params.get("save_after"):
            bpy.ops.wm.save_as_mainfile(filepath=str(params["save_after"]))
            result["saved_file"] = str(params["save_after"])
        return result
    if operation == "create-cube":
        bpy.ops.mesh.primitive_cube_add(location=_vector(params.get("location")))
        active = getattr(getattr(bpy, "context", None), "active_object", None)
    elif operation == "import-glb":
        filepath = str(params.get("filepath", ""))
        if not filepath:
            return {"status": "failed", "errors": ["import-glb requires parameters['filepath']"]}
        bpy.ops.import_scene.gltf(filepath=filepath, merge_vertices=False, import_shading="NORMALS")
        active = getattr(getattr(bpy, "context", None), "active_object", None)

    if active is None:
        return {"status": "failed", "errors": ["no active Blender object"]}

    if operation in {"create-cube", "import-glb"}:
        pass
    elif operation == "translate-active":
        active.location = tuple(a + b for a, b in zip(active.location, _vector(params.get("delta"))))
    elif operation == "set-location":
        active.location = _vector(params.get("location"))
    elif operation == "set-scale":
        active.scale = _vector(params.get("scale"), default=(1.0, 1.0, 1.0))
    elif operation == "rename-active":
        name = str(params.get("name", ""))
        if not name:
            return {"status": "failed", "errors": ["rename-active requires parameters['name']"]}
        active.name = name
    elif operation == "save-mainfile":
        filepath = str(params.get("filepath", ""))
        if not filepath:
            return {"status": "failed", "errors": ["save-mainfile requires parameters['filepath']"]}
        bpy.ops.wm.save_as_mainfile(filepath=filepath)
    elif operation == "export-glb":
        filepath = str(params.get("filepath", ""))
        if not filepath:
            return {"status": "failed", "errors": ["export-glb requires parameters['filepath']"]}
        bpy.ops.export_scene.gltf(filepath=filepath, export_format="GLB", export_draco_mesh_compression_enable=False)
    elif operation == "export-bridge-json":
        return _bridge_export(bpy, params)
    else:
        return {"status": "failed", "errors": [f"unsupported Blender operation: {operation}"]}

    save_after = params.get("save_after")
    if save_after:
        bpy.ops.wm.save_as_mainfile(filepath=str(save_after))
    return {"status": "succeeded", "object": _object_summary(active)}
