from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import unreal


def _asset_object_path(value: str) -> str:
    value = value.strip()
    if "'" in value:
        value = value.split("'")[-2] if value.count("'") >= 2 else value
    if "." in value.rsplit("/", 1)[-1]:
        return value
    name = value.rsplit("/", 1)[-1]
    return f"{value}.{name}"


def _request_parameters() -> dict[str, Any]:
    request_file = os.environ.get("AINATIVE_UE5_REQUEST_FILE")
    if not request_file or not Path(request_file).is_file():
        return {}
    payload = json.loads(Path(request_file).read_text(encoding="utf-8"))
    return dict(payload.get("parameters", {}))


def _export_asset_from_manifest(manifest_file: Path, bridge_dir: Path) -> dict[str, object]:
    raw = json.loads(manifest_file.read_text(encoding="utf-8"))
    asset_path = raw.get("metadata", {}).get("ue5_asset_path") or raw.get("asset_id") or raw.get("source_asset_path")
    if not asset_path:
        raise ValueError("manifest requires metadata.ue5_asset_path, asset_id, or source_asset_path")
    asset_data = unreal.AssetsBridgeTools.get_asset_data_from_path(_asset_object_path(str(asset_path)))
    export_info, info_ok, info_message = unreal.AssetsBridgeTools.get_export_info(asset_data)
    if not info_ok:
        raise RuntimeError(str(info_message))
    export_path = Path(str(export_info.export_location))
    export_path.parent.mkdir(parents=True, exist_ok=True)
    task = unreal.AssetExportTask()
    task.object = export_info.model_ptr
    task.exporter = unreal.GLTFStaticMeshExporter()
    task.filename = str(export_path)
    task.automated = True
    task.prompt = False
    task.replace_identical = True
    exported = unreal.Exporter.run_asset_export_task(task)
    if not exported:
        raise RuntimeError(f"UE5 glTF export failed: {export_path}")
    bridge_export = unreal.BridgeExport()
    bridge_export.operation = "UnrealExport"
    bridge_export.objects = [export_info]
    json_ok, json_message = unreal.AssetsBridgeTools.write_bridge_export_file(bridge_export)
    if not json_ok:
        raise RuntimeError(str(json_message))
    return {"export_path": str(export_path), "from_unreal": str(bridge_dir / "from-unreal.json"), "asset_info_message": str(info_message)}


def _editor_subsystem(class_name: str) -> Any | None:
    subsystem_class = getattr(unreal, class_name, None)
    if subsystem_class is None:
        return None
    getter = getattr(unreal, "get_editor_subsystem", None)
    if callable(getter):
        try:
            return getter(subsystem_class)
        except Exception:
            pass
    try:
        return subsystem_class()
    except Exception:
        return None


def _level_editor() -> Any | None:
    # EditorLevelLibrary remains the most predictable synchronous surface for
    # the current UE5.7 commandlet/editor launch used by this fixture. Prefer
    # it when available and keep LevelEditorSubsystem as the forward fallback.
    return getattr(unreal, "EditorLevelLibrary", None) or _editor_subsystem("LevelEditorSubsystem")


def _actor_editor() -> Any | None:
    # The legacy library spawn path is still reliable in the visible Editor;
    # use EditorActorSubsystem only when the library surface is unavailable.
    return getattr(unreal, "EditorLevelLibrary", None) or _editor_subsystem("EditorActorSubsystem")


def _level_actors() -> list[Any]:
    owner = _actor_editor()
    getter = getattr(owner, "get_all_level_actors", None) if owner is not None else None
    if callable(getter):
        return list(getter())
    raise RuntimeError("UE5 Python has no level actor enumeration capability")


def _selected_actors() -> list[Any]:
    owner = _actor_editor()
    getter = getattr(owner, "get_selected_level_actors", None) if owner is not None else None
    if callable(getter):
        return list(getter())
    return []


def _actor_label(actor: Any) -> str:
    getter = getattr(actor, "get_actor_label", None)
    return str(getter()) if callable(getter) else str(actor.get_name())


def _actor_summary(actor: Any) -> dict[str, Any]:
    location = actor.get_actor_location()
    rotation = actor.get_actor_rotation()
    scale = actor.get_actor_scale3d()
    return {
        "name": str(actor.get_name()),
        "label": _actor_label(actor),
        "path": str(actor.get_path_name()),
        "class": str(actor.get_class().get_name()),
        "location": [float(location.x), float(location.y), float(location.z)],
        "rotation": [float(rotation.pitch), float(rotation.yaw), float(rotation.roll)],
        "scale": [float(scale.x), float(scale.y), float(scale.z)],
    }


def _load_level_if_requested(parameters: dict[str, Any]) -> None:
    level_path = parameters.get("level_path")
    if not level_path:
        return
    owner = _level_editor()
    loader = getattr(owner, "load_level", None) if owner is not None else None
    if not callable(loader):
        raise RuntimeError("UE5 Python has no level load capability")
    loaded = loader(str(level_path))
    if loaded is False:
        raise RuntimeError(f"could not load level: {level_path}")


def _level_asset_path(value: Any, default: str | None = None) -> str:
    text = str(value if value is not None else (default or "")).strip()
    text = text.removesuffix(".umap")
    if "." in text.rsplit("/", 1)[-1]:
        text = text.rsplit(".", 1)[0]
    return text


def _asset_exists(asset_path: str) -> bool:
    library = getattr(unreal, "EditorAssetLibrary", None)
    checker = getattr(library, "does_asset_exist", None) if library is not None else None
    if not callable(checker):
        raise RuntimeError("UE5 Python does not expose EditorAssetLibrary.does_asset_exist")
    candidates = [asset_path]
    object_path = _asset_object_path(asset_path)
    if object_path not in candidates:
        candidates.append(object_path)
    return any(bool(checker(candidate)) for candidate in candidates)


def _current_level_path() -> str | None:
    owner = _level_editor()
    getter = getattr(owner, "get_editor_world", None) if owner is not None else None
    world = getter() if callable(getter) else None
    if world is None or not callable(getattr(world, "get_path_name", None)):
        return None
    path = str(world.get_path_name())
    return path.split(":", 1)[0].split(".", 1)[0]


def _expected_object_token(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("class") or value.get("name") or value.get("label")
    return str(value).strip()


def _matches_expected_object(summary: dict[str, Any], expected: str) -> bool:
    token = expected.lower()
    candidates = (str(summary.get("class", "")), str(summary.get("name", "")), str(summary.get("label", "")))
    return any(token == candidate.lower() or token in candidate.lower() for candidate in candidates)


def _expected_level_objects(parameters: dict[str, Any]) -> list[str]:
    raw = parameters.get("expected_default_objects")
    if raw is None:
        raw = ["DirectionalLight", "SkyLight"]
    if isinstance(raw, (str, dict)):
        raw = [raw]
    expected = [_expected_object_token(value) for value in raw]
    return [value for value in expected if value]


def _inspect_level(parameters: dict[str, Any]) -> dict[str, Any]:
    target_level = _level_asset_path(parameters.get("level_path") or parameters.get("target_level") or parameters.get("target"))
    if target_level:
        _load_level_if_requested({"level_path": target_level})
    actors = [_actor_summary(actor) for actor in _level_actors()]
    expected = _expected_level_objects(parameters)
    missing = [token for token in expected if not any(_matches_expected_object(actor, token) for actor in actors)]
    loaded_level = _current_level_path()
    if target_level and loaded_level and loaded_level != target_level:
        raise RuntimeError(f"loaded level {loaded_level} does not match target level {target_level}")
    if missing:
        raise RuntimeError("level is missing expected default objects: " + ", ".join(missing))
    return {
        "level_path": target_level or loaded_level,
        "loaded_level": loaded_level,
        "actor_count": len(actors),
        "actors": actors,
        "expected_default_objects": expected,
        "missing_default_objects": missing,
        "default_objects_valid": not missing,
    }


def _create_level_from_template(parameters: dict[str, Any]) -> dict[str, Any]:
    template_level = _level_asset_path(parameters.get("template") or parameters.get("template_level"), "/Engine/Maps/Templates/Template_Default")
    target_level = _level_asset_path(parameters.get("target") or parameters.get("target_level"), "/Game/DefaultLightingLevel")
    if not target_level.startswith("/Game/"):
        raise ValueError("target level must be a project asset under /Game")
    if target_level == template_level:
        raise ValueError("target level must differ from the template level")
    if not _asset_exists(template_level):
        raise ValueError(f"UE5 level template does not exist: {template_level}")
    target_exists = _asset_exists(target_level)
    reuse_existing = bool(parameters.get("reuse_existing", False))
    if target_exists and not reuse_existing:
        raise ValueError(f"target level already exists: {target_level}; set reuse_existing=true to inspect it")

    created = False
    if not target_exists:
        owner = _editor_subsystem("LevelEditorSubsystem")
        creator = getattr(owner, "new_level_from_template", None) if owner is not None else None
        if not callable(creator):
            owner = _level_editor()
            creator = getattr(owner, "new_level_from_template", None) if owner is not None else None
        if not callable(creator):
            raise RuntimeError("UE5 Python does not expose new_level_from_template")
        created = bool(creator(target_level, template_level))
        if not created:
            raise RuntimeError(f"could not create level {target_level} from template {template_level}")

    _load_level_if_requested({"level_path": target_level})
    inspected = _inspect_level({
        "level_path": target_level,
        "expected_default_objects": parameters.get("expected_default_objects"),
    })
    saved = bool(_save_level({"level_path": target_level}))
    if not saved:
        raise RuntimeError(f"created level was not saved: {target_level}")
    return {
        "template": template_level,
        "target_level": target_level,
        "created": created,
        "reused_existing": target_exists,
        "open_after_create": True,
        "saved": saved,
        **inspected,
    }


def _resolve_actor(parameters: dict[str, Any]) -> Any:
    requested = parameters.get("actor_path") or parameters.get("object_path") or parameters.get("actor_name") or parameters.get("name") or parameters.get("label")
    candidates = _level_actors()
    if requested:
        needle = str(requested)
        matches = [actor for actor in candidates if needle in {str(actor.get_name()), _actor_label(actor), str(actor.get_path_name())}]
        if not matches:
            matches = [actor for actor in candidates if needle.lower() in {str(actor.get_name()).lower(), _actor_label(actor).lower(), str(actor.get_path_name()).lower()}]
        if not matches:
            raise ValueError(f"UE5 actor was not found: {needle}")
        return matches[0]
    selected = _selected_actors()
    if len(selected) == 1:
        return selected[0]
    if len(candidates) == 1:
        return candidates[0]
    raise ValueError("actor_path, actor_name, label, or exactly one selected actor is required")


def _vector(value: Any, current: Any | None = None) -> Any:
    if value is None:
        return current
    if isinstance(value, dict):
        values = [value.get(axis, 0.0) for axis in ("x", "y", "z")]
    else:
        values = list(value)
    if len(values) != 3:
        raise ValueError("UE5 vector values must have three numbers")
    return unreal.Vector(float(values[0]), float(values[1]), float(values[2]))


def _rotator(value: Any, current: Any | None = None) -> Any:
    if value is None:
        return current
    if isinstance(value, dict):
        values = [value.get(axis, 0.0) for axis in ("pitch", "yaw", "roll")]
        if all(axis not in value for axis in ("pitch", "yaw", "roll")):
            values = [value.get(axis, 0.0) for axis in ("x", "y", "z")]
    else:
        values = list(value)
    if len(values) != 3:
        raise ValueError("UE5 rotation values must have three numbers")
    return unreal.Rotator(float(values[0]), float(values[1]), float(values[2]))


def _set_actor_transform(parameters: dict[str, Any]) -> dict[str, Any]:
    actor = _resolve_actor(parameters)
    current_location = actor.get_actor_location()
    current_rotation = actor.get_actor_rotation()
    current_scale = actor.get_actor_scale3d()
    location = _vector(parameters.get("location"), current_location)
    delta = parameters.get("delta")
    if delta is not None:
        delta_vector = _vector(delta)
        location = unreal.Vector(current_location.x + delta_vector.x, current_location.y + delta_vector.y, current_location.z + delta_vector.z)
    rotation = _rotator(parameters.get("rotation"), current_rotation)
    scale = _vector(parameters.get("scale"), current_scale)
    if hasattr(actor, "modify"):
        actor.modify()
    if parameters.get("location") is not None or delta is not None:
        actor.set_actor_location(location, False, True)
    if parameters.get("rotation") is not None:
        actor.set_actor_rotation(rotation, False)
    if parameters.get("scale") is not None:
        actor.set_actor_scale3d(scale)
    result = {"actor": _actor_summary(actor), **_actor_summary(actor)}
    if parameters.get("auto_save"):
        result["saved"] = bool(_save_level({}))
    return result


def _list_actors(parameters: dict[str, Any]) -> dict[str, Any]:
    _load_level_if_requested(parameters)
    actors = [_actor_summary(actor) for actor in _level_actors()]
    return {"actor_count": len(actors), "actors": actors}


def _find_actor_by_label(label: str, attempts: int = 20) -> Any | None:
    for attempt in range(attempts):
        existing = next((actor for actor in _level_actors() if _actor_label(actor) == label), None)
        if existing is not None:
            return existing
        if attempt + 1 < attempts:
            time.sleep(0.25)
    return None


def _create_actor(parameters: dict[str, Any]) -> dict[str, Any]:
    level_path = str(parameters.get("level_path", "/Game/AINativeActorE2E"))
    label = str(parameters.get("label", "AINativeActorE2E"))
    asset_library = getattr(unreal, "EditorAssetLibrary", None)
    level_exists = bool(asset_library and callable(getattr(asset_library, "does_asset_exist", None)) and asset_library.does_asset_exist(level_path))
    owner = _level_editor()
    if not level_exists:
        creator = getattr(owner, "new_level", None) if owner is not None else None
        if not callable(creator):
            raise RuntimeError("UE5 Python does not expose a level creation capability")
        created = creator(level_path)
        if created is False or created is None:
            raise RuntimeError(f"could not create level: {level_path}")
    _load_level_if_requested({"level_path": level_path})

    actor = _find_actor_by_label(label)
    if actor is None:
        actor_class = getattr(unreal, "StaticMeshActor", None)
        actor_owner = _actor_editor()
        spawner = getattr(actor_owner, "spawn_actor_from_class", None) if actor_owner is not None else None
        if actor_class is None or not callable(spawner):
            raise RuntimeError("UE5 Python does not expose StaticMeshActor spawning")
        spawn_class = actor_class.static_class() if callable(getattr(actor_class, "static_class", None)) else actor_class
        actor = spawner(spawn_class, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator(0.0, 0.0, 0.0))
        if actor is None:
            raise RuntimeError("could not spawn StaticMeshActor")
        if hasattr(actor, "set_actor_label"):
            actor.set_actor_label(label, True)

    expected_package = level_path.rsplit("/", 1)[-1]
    actor_path = str(actor.get_path_name())
    if expected_package not in actor_path:
        _load_level_if_requested({"level_path": level_path})
        actor = _find_actor_by_label(label)
        if actor is None or expected_package not in str(actor.get_path_name()):
            raise RuntimeError(f"actor was created in the wrong level: {actor_path}")

    mesh_path = str(parameters.get("mesh_path", "/Engine/BasicShapes/Cube.Cube"))
    mesh = asset_library.load_asset(mesh_path) if asset_library is not None else None
    component = getattr(actor, "static_mesh_component", None)
    if mesh is not None and component is not None and hasattr(component, "set_static_mesh"):
        component.set_static_mesh(mesh)
    saved = bool(_save_level({"level_path": level_path}))
    return {"level_path": level_path, "saved": saved, "actor": _actor_summary(actor), **_actor_summary(actor)}


def _save_level(parameters: dict[str, Any]) -> dict[str, Any]:
    level_path = parameters.get("level_path")
    if level_path:
        _load_level_if_requested(parameters)
    owner = _level_editor()
    saver = getattr(owner, "save_current_level", None) if owner is not None else None
    if callable(saver):
        saved = bool(saver())
    else:
        saver = getattr(owner, "save_all_dirty_levels", None) if owner is not None else None
        saved = bool(saver()) if callable(saver) else bool(unreal.EditorLoadingAndSavingUtils.save_dirty_packages(False, True))
    return {"saved": saved, "level_path": str(level_path) if level_path else None}


def main() -> int:
    operation = os.environ.get("AINATIVE_UE5_OPERATION", "inspect")
    normalized = operation.replace("-", "_")
    output = Path(os.environ["AINATIVE_UE5_RESULT_FILE"])
    parameters = _request_parameters()
    result = {"status": "failed", "operation": operation, "engine": unreal.SystemLibrary.get_engine_version()}
    try:
        bridge_dir = Path(os.environ.get("AINATIVE_UE5_BRIDGE_DIR", "")).resolve() if os.environ.get("AINATIVE_UE5_BRIDGE_DIR") else None
        if bridge_dir:
            bridge_dir.mkdir(parents=True, exist_ok=True)
            unreal.AssetsBridgeTools.set_export_root(str(bridge_dir))
        if normalized not in {"inspect", "export_asset", "import_asset", "create_actor", "create_level_from_template", "inspect_level", "save_level"}:
            _load_level_if_requested(parameters)
        if normalized == "export_asset":
            manifest_file = Path(os.environ["AINATIVE_UE5_MANIFEST_FILE"])
            result.update(_export_asset_from_manifest(manifest_file, bridge_dir or manifest_file.parent))
            result["ok"] = True
        elif normalized == "import_asset":
            ok, message = unreal.BridgeManager.generate_import()
            saved = None
            if ok:
                try:
                    saved = bool(unreal.EditorLoadingAndSavingUtils.save_dirty_packages(False, True))
                except Exception as save_exc:
                    result["save_warning"] = str(save_exc)
            result.update({"ok": bool(ok), "message": str(message), "saved_dirty_packages": saved})
        elif normalized == "inspect":
            result.update({
                "ok": True,
                "bridge_types": sorted(name for name in dir(unreal) if "Bridge" in name),
                "editor_level_library_methods": sorted(name for name in dir(getattr(unreal, "EditorLevelLibrary", object)) if not name.startswith("_") and ("level" in name.lower() or "actor" in name.lower() or "map" in name.lower() or "world" in name.lower())),
                "editor_actor_subsystem_methods": sorted(name for name in dir(getattr(unreal, "EditorActorSubsystem", object)) if not name.startswith("_")),
                "static_mesh_actor_repr": repr(getattr(unreal, "StaticMeshActor", None)),
                "static_mesh_actor_type": type(getattr(unreal, "StaticMeshActor", None)).__name__,
                "static_mesh_actor_static_class": repr(getattr(getattr(unreal, "StaticMeshActor", None), "static_class", lambda: None)()),
                "spawn_actor_doc": str(getattr(getattr(unreal, "EditorLevelLibrary", object), "spawn_actor_from_class", None).__doc__),
                "status": "succeeded",
            })
        elif normalized == "list_actors":
            result.update({"ok": True, **_list_actors(parameters)})
        elif normalized == "create_actor":
            result.update({"ok": True, **_create_actor(parameters)})
        elif normalized == "create_level_from_template":
            result.update({"ok": True, **_create_level_from_template(parameters)})
        elif normalized == "inspect_level":
            result.update({"ok": True, **_inspect_level(parameters)})
        elif normalized in {"resolve_actor", "read_actor_transform"}:
            actor = _resolve_actor(parameters)
            result.update({"ok": True, "actor": _actor_summary(actor), **_actor_summary(actor)})
        elif normalized == "set_actor_transform":
            result.update({"ok": True, **_set_actor_transform(parameters)})
        elif normalized == "save_level":
            result.update({"ok": True, **_save_level(parameters)})
        else:
            result["message"] = f"unsupported UE5 operation: {operation}"
        if result.get("ok") is True:
            result["status"] = "succeeded"
    except Exception as exc:
        result.update({"error_type": type(exc).__name__, "error": str(exc), "errors": [str(exc)]})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    if os.environ.get("AINATIVE_UE5_EXIT_AFTER_OPERATION") == "1":
        try:
            unreal.SystemLibrary.quit_editor()
        except Exception:
            pass
    return 0 if result["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
