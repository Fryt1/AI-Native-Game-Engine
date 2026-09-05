import importlib.util
import json
import sys
from pathlib import Path

import bpy

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ADDON_ROOT = PROJECT_ROOT / "vendor" / "assetsbridge" / "blender-addon" / "AssetsBridgeAddon"
RESULT_FILE = PROJECT_ROOT / "artifacts" / "evidence" / "assetsbridge" / "assetsbridge-addon-probe.json"
spec = importlib.util.spec_from_file_location("AssetsBridge", ADDON_ROOT / "__init__.py", submodule_search_locations=[str(ADDON_ROOT)])
if spec is None or spec.loader is None:
    raise RuntimeError(f"AssetsBridge Add-on entrypoint is missing: {ADDON_ROOT}")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
result = {"blender_version": bpy.app.version_string, "addon": str(ADDON_ROOT), "status": "failed"}
try:
    spec.loader.exec_module(module)
    module.register()
    result["registered"] = True
    module.unregister()
    result["unregistered"] = True
    result["status"] = "succeeded"
except Exception as exc:
    result["error_type"] = type(exc).__name__
    result["error"] = str(exc)
RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
RESULT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
