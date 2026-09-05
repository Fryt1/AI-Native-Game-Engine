"""Endpoint used by the core to call the upstream AssetsBridge Add-on."""

from __future__ import annotations

import json
import os
from pathlib import Path

import bpy


def main() -> int:
    bridge = Path(os.environ["AINATIVE_BRIDGE_DIR"])
    operation = os.environ["AINATIVE_BLENDER_OPERATION"]
    result_file = Path(os.environ["AINATIVE_BLENDER_RESULT_FILE"])
    result = {"blender_version": bpy.app.version_string, "operation": operation, "status": "failed"}
    try:
        bpy.ops.preferences.addon_enable(module="AssetsBridge")
        preferences = bpy.context.preferences.addons["AssetsBridge"].preferences
        preferences.filepaths[0].path = str(bridge / "AssetsBridge.json")
        preferences.warn_missing_ucx = False
        if operation == "import":
            outcome = bpy.ops.assetsbridge.imports()
            if os.environ.get("AINATIVE_BLENDER_EDIT_FILE"):
                bpy.ops.wm.save_as_mainfile(filepath=os.environ["AINATIVE_BLENDER_EDIT_FILE"])
            result.update({"operator_result": str(outcome), "status": "succeeded" if "FINISHED" in str(outcome) else "failed", "saved_file": os.environ.get("AINATIVE_BLENDER_EDIT_FILE")})
        elif operation == "export":
            bpy.ops.object.select_all(action="DESELECT")
            objects = [obj for obj in bpy.data.objects if obj.get("AB_model")]
            if not objects:
                raise RuntimeError("AssetsBridge export found no imported object with AB_model metadata")
            for obj in objects:
                obj.select_set(True)
            bpy.context.view_layer.objects.active = objects[0]
            outcome = bpy.ops.assetsbridge.exports()
            result.update({"operator_result": str(outcome), "status": "succeeded" if "FINISHED" in str(outcome) else "failed", "exported_object_count": len(objects)})
            if (bridge / "from-blender.json").is_file():
                result["from_blender"] = str(bridge / "from-blender.json")
        else:
            raise ValueError(f"unsupported external AssetsBridge operation: {operation}")
    except Exception as exc:
        result.update({"error_type": type(exc).__name__, "error": str(exc)})
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
