import json
import os
from pathlib import Path

import unreal

result={"engine":unreal.SystemLibrary.get_engine_version(),"status":"failed"}
try:
    tools=unreal.AssetToolsHelpers.get_asset_tools()
    existing=unreal.EditorAssetLibrary.load_asset("/Game/Materials/_Core/M_ORM.M_ORM")
    material=existing
    if material is None:
        factory=unreal.MaterialFactoryNew()
        material=tools.create_asset("M_ORM","/Game/Materials/_Core",unreal.Material,factory)
    if material is None: raise RuntimeError("could not create M_ORM")
    unreal.EditorAssetLibrary.save_asset(material.get_path_name(), only_if_is_dirty=False)
    result.update({"status":"succeeded","path":material.get_path_name(),"class":material.get_class().get_name()})
except Exception as exc: result.update({"error_type":type(exc).__name__,"error":str(exc)})
Path(os.environ["AINATIVE_UE5_PROBE_OUTPUT"]).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(result,ensure_ascii=False))
