import json
from pathlib import Path

import bpy

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RESULT_FILE = PROJECT_ROOT / "artifacts" / "evidence" / "assetsbridge" / "assetsbridge-addon-probe.json"
result = {"blender_version": bpy.app.version_string, "status": "failed"}
try:
    enabled = bpy.ops.preferences.addon_enable(module="AssetsBridge")
    result["enable_result"] = str(enabled)
    result["registered"] = "AssetsBridge" in bpy.context.preferences.addons
    if result["registered"]:
        bpy.ops.preferences.addon_disable(module="AssetsBridge")
        result["disabled"] = "AssetsBridge" not in bpy.context.preferences.addons
    result["status"] = "succeeded" if result.get("registered") and result.get("disabled") else "failed"
except Exception as exc:
    result["error_type"] = type(exc).__name__
    result["error"] = str(exc)
RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
RESULT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
