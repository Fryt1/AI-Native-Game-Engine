import json
from pathlib import Path

import bpy

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BRIDGE = PROJECT_ROOT / "artifacts" / "scratch" / "assetsbridge-addon-bridge-e2e"
RESULT_FILE = BRIDGE / "result.json"
result = {"blender_version": bpy.app.version_string, "status": "failed"}
try:
    bpy.ops.preferences.addon_enable(module="AssetsBridge")
    prefs = bpy.context.preferences.addons["AssetsBridge"].preferences
    prefs.filepaths[0].path = str(BRIDGE / "AssetsBridge.json")
    prefs.warn_missing_ucx = False
    import_result = bpy.ops.assetsbridge.imports()
    obj = next((o for o in bpy.data.objects if o.get("AB_objectId") == "/Game/Meshes/SM_Test"), None)
    if obj is None:
        raise RuntimeError("imported object with AB_objectId not found")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    obj.location.x += 1.0
    export_result = bpy.ops.assetsbridge.exports()
    result["import_result"] = str(import_result)
    result["export_result"] = str(export_result)
    result["object"] = {"name": obj.name, "object_id": obj.get("AB_objectId"), "location": list(obj.location)}
    output = json.loads((BRIDGE / "from-blender.json").read_text(encoding="utf-8"))
    item = output["objects"][0]
    export_path = Path(item["exportLocation"])
    result.update({"from_blender_exists": True, "export_file": str(export_path), "export_file_exists": export_path.is_file(), "exported_object_count": len(output.get("objects", [])), "status": "succeeded" if export_path.is_file() and item["objectId"] == "/Game/Meshes/SM_Test" else "failed"})
except Exception as exc:
    result["error_type"] = type(exc).__name__
    result["error"] = str(exc)
RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
RESULT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
