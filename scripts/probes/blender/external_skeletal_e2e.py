import json
import os
from pathlib import Path

import bpy

bridge=Path(os.environ["AINATIVE_BRIDGE_DIR"]); result_file=Path(os.environ["AINATIVE_RESULT_FILE"]); result={"blender_version":bpy.app.version_string,"status":"failed"}
try:
    bpy.ops.preferences.addon_enable(module="AssetsBridge")
    prefs=bpy.context.preferences.addons["AssetsBridge"].preferences; prefs.filepaths[0].path=str(bridge/"AssetsBridge.json"); prefs.warn_missing_ucx=False
    imported_result=bpy.ops.assetsbridge.imports()
    bpy.ops.object.select_all(action="DESELECT")
    candidates=[o for o in bpy.data.objects if o.get("AB_model")]
    if not candidates: raise RuntimeError("no imported AssetsBridge object")
    root=candidates[0]
    while root.parent: root=root.parent
    bpy.context.view_layer.objects.active=root; root.select_set(True)
    root.location.x += 1.0
    export_result=bpy.ops.assetsbridge.exports()
    doc=json.loads((bridge/"from-blender.json").read_text(encoding="utf-8")); items=doc.get("objects",[]); item=items[0] if items else {}
    export_path=Path(item.get("exportLocation",""))
    result.update({"status":"succeeded" if export_path.is_file() else "failed","import_result":str(imported_result),"export_result":str(export_result),"objects":[{"name":o.name,"type":o.type,"model":o.get("AB_model"),"string_type":o.get("AB_stringType"),"shape_keys":[k.name for k in o.data.shape_keys.key_blocks] if o.type=="MESH" and o.data.shape_keys else []} for o in bpy.data.objects if o.get("AB_model")],"from_blender":(bridge/"from-blender.json").is_file(),"export_file":str(export_path),"export_file_exists":export_path.is_file(),"morph_targets":item.get("morphTargets",[])})
except Exception as exc:
    result.update({"error_type":type(exc).__name__,"error":str(exc)})
result_file.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(result,ensure_ascii=False))
