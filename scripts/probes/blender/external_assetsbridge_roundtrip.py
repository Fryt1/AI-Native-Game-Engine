"""Run the external AssetsBridge Blender Add-on against a bridge directory."""

import json
import os
from pathlib import Path

import bpy


def main() -> int:
    bridge = Path(os.environ["AINATIVE_BRIDGE_DIR"])
    result_file = Path(os.environ["AINATIVE_RESULT_FILE"])
    result = {"blender_version": bpy.app.version_string, "status": "failed"}
    try:
        bpy.ops.preferences.addon_enable(module="AssetsBridge")
        preferences = bpy.context.preferences.addons["AssetsBridge"].preferences
        preferences.filepaths[0].path = str(bridge / "AssetsBridge.json")
        preferences.warn_missing_ucx = False
        import_result = bpy.ops.assetsbridge.imports()
        bpy.ops.object.select_all(action="DESELECT")
        imported = [obj for obj in bpy.data.objects if obj.get("AB_model")]
        if not imported:
            raise RuntimeError("AssetsBridge imported no object with AB_model metadata")
        obj = imported[0]
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        obj.location.x += 1.0
        export_result = bpy.ops.assetsbridge.exports()
        document = json.loads((bridge / "from-blender.json").read_text(encoding="utf-8"))
        item = document["objects"][0]
        export_path = Path(item["exportLocation"])
        result.update({"import_result": str(import_result), "export_result": str(export_result), "object": {"name": obj.name, "model": obj.get("AB_model"), "location": list(obj.location)}, "from_blender_exists": True, "export_file": str(export_path), "export_file_exists": export_path.is_file(), "exported_object_count": len(document.get("objects", []))})
        result["status"] = "succeeded" if export_path.is_file() else "failed"
    except Exception as exc:
        result.update({"error_type": type(exc).__name__, "error": str(exc)})
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
