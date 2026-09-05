import json
import os
from pathlib import Path

import bpy

bridge=Path(os.environ["AINATIVE_BRIDGE_DIR"]); result_file=Path(os.environ["AINATIVE_RESULT_FILE"]); result={"blender_version":bpy.app.version_string,"status":"failed"}
try:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.preferences.addon_enable(module="AssetsBridge")
    prefs=bpy.context.preferences.addons["AssetsBridge"].preferences; prefs.filepaths[0].path=str(bridge/"AssetsBridge.json"); prefs.warn_missing_ucx=False
    bpy.ops.mesh.primitive_cube_add()
    obj=bpy.context.active_object; obj.name="SM_PBR_Test"; obj["AB_shortName"]="SM_PBR_Test"; obj["AB_internalPath"]="/Game/PBR"; obj["AB_exportLocation"]=str(bridge/"Game"/"PBR"/"SM_PBR_Test.glb")
    material=bpy.data.materials.new("M_PBR_Test"); material.use_nodes=True; obj.data.materials.append(material)
    bsdf=material.node_tree.nodes.get("Principled BSDF"); bsdf.inputs["Base Color"].default_value=(0.2,0.5,0.8,1.0); bsdf.inputs["Metallic"].default_value=0.4; bsdf.inputs["Roughness"].default_value=0.35
    bpy.context.view_layer.objects.active=obj; obj.select_set(True)
    bake_out=bpy.ops.assetsbridge.bake_pbr(resolution="128",samples=1,margin=2,flip_normal_green=True,bake_ao=False,bake_emissive=False,re_unwrap=True,consolidate_materials=True)
    export_out=bpy.ops.assetsbridge.exports()
    doc=json.loads((bridge/"from-blender.json").read_text(encoding="utf-8")); item=doc["objects"][0]; textures=item.get("textures",{}); export_path=Path(item.get("exportLocation",""))
    result.update({"operator_result":str(bake_out),"export_result":str(export_out),"status":"succeeded" if "FINISHED" in str(bake_out) and "FINISHED" in str(export_out) else "failed","textures":textures,"texture_files":{role:Path(block.get("file","")).is_file() if isinstance(block,dict) else False for role,block in textures.items() if role not in ("master","materialInstance")},"export_file":str(export_path),"export_file_exists":export_path.is_file(),"manifest_has_textures":bool(textures.get("baseColor") and textures.get("orm") and textures.get("normal"))})
except Exception as exc:
    result.update({"error_type":type(exc).__name__,"error":str(exc)})
result_file.parent.mkdir(parents=True,exist_ok=True); result_file.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(result,ensure_ascii=False))
