"""Export the Engine BasicShapes Cube through the AssetsBridge UE5 API."""

import json
import os
from pathlib import Path

import unreal


def main() -> int:
    bridge = Path(os.environ["AINATIVE_BRIDGE_DIR"])
    result_file = Path(os.environ["AINATIVE_RESULT_FILE"])
    bridge.mkdir(parents=True, exist_ok=True)
    result = {"engine": unreal.SystemLibrary.get_engine_version(), "status": "failed"}
    try:
        unreal.AssetsBridgeTools.set_export_root(str(bridge))
        asset_data = unreal.AssetsBridgeTools.get_asset_data_from_path("/Engine/BasicShapes/Cube.Cube")
        export_info, info_ok, info_message = unreal.AssetsBridgeTools.get_export_info(asset_data)
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
        bridge_export = unreal.BridgeExport()
        bridge_export.operation = "UnrealExport"
        bridge_export.objects = [export_info]
        json_ok, json_message = unreal.AssetsBridgeTools.write_bridge_export_file(bridge_export)
        result.update({"asset_info_ok": bool(info_ok), "asset_info_message": str(info_message), "exported": bool(exported), "export_path": str(export_path), "export_exists": export_path.is_file(), "json_ok": bool(json_ok), "json_message": str(json_message), "from_unreal": str(bridge / "from-unreal.json"), "from_unreal_exists": (bridge / "from-unreal.json").is_file()})
        result["status"] = "succeeded" if exported and json_ok and export_path.is_file() else "failed"
    except Exception as exc:
        result.update({"error_type": type(exc).__name__, "error": str(exc)})
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
