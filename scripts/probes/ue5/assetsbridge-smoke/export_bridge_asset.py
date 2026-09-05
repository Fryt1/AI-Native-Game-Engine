import json
import os
from pathlib import Path

import unreal

bridge=Path(os.environ["AINATIVE_BRIDGE_DIR"])
bridge.mkdir(parents=True,exist_ok=True)
result={"engine":unreal.SystemLibrary.get_engine_version(),"status":"failed"}
try:
    ok_root=unreal.AssetsBridgeTools.set_export_root(str(bridge))
    asset_data=unreal.AssetsBridgeTools.get_asset_data_from_path("/Engine/BasicShapes/Cube.Cube")
    export_info, ok_info, info_message=unreal.AssetsBridgeTools.get_export_info(asset_data)
    export_path=Path(str(export_info.export_location))
    export_path.parent.mkdir(parents=True,exist_ok=True)
    task=unreal.AssetExportTask()
    task.object=export_info.model_ptr
    task.exporter=unreal.GLTFStaticMeshExporter()
    task.filename=str(export_path)
    task.automated=True; task.prompt=False; task.replace_identical=True
    exported=unreal.Exporter.run_asset_export_task(task)
    bridge_export=unreal.BridgeExport()
    bridge_export.operation="UnrealExport"
    bridge_export.objects=[export_info]
    ok_json,message_json=unreal.AssetsBridgeTools.write_bridge_export_file(bridge_export)
    result.update({"set_export_root":bool(ok_root) if isinstance(ok_root,bool) else str(ok_root),"asset_info_ok":bool(ok_info),"asset_info_message":str(info_message),"exported":bool(exported),"export_path":str(export_path),"export_exists":export_path.is_file(),"json_ok":bool(ok_json),"json_message":str(message_json),"from_unreal":str(bridge/"from-unreal.json"),"from_unreal_exists":(bridge/"from-unreal.json").is_file(),"status":"succeeded" if exported and ok_json and export_path.is_file() else "failed"})
except Exception as exc:
    result.update({"error_type":type(exc).__name__,"error":str(exc)})
Path(os.environ["AINATIVE_UE5_PROBE_OUTPUT"]).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(result,ensure_ascii=False))
