import json
import os
from pathlib import Path

import unreal

result={"engine":unreal.SystemLibrary.get_engine_version(),"status":"failed"}
try:
    paths=["/Game/Characters/SK_Test.SK_Test","/Game/Characters/SK_Test"]
    obj=None; loaded_path=None
    for path in paths:
        obj=unreal.EditorAssetLibrary.load_asset(path)
        if obj: loaded_path=path; break
    result["loaded_path"]=loaded_path
    result["class"]=obj.get_class().get_name() if obj else None
    if obj:
        result["members"]=[x for x in dir(obj) if "morph" in x.lower() or "skeleton" in x.lower() or "material" in x.lower()]
        for prop in ("skeleton","morph_targets","materials"):
            try: result[prop]=str(obj.get_editor_property(prop))
            except Exception as exc: result[prop+"_error"]=str(exc)
    result["status"]="succeeded" if obj else "failed"
except Exception as exc: result.update({"error_type":type(exc).__name__,"error":str(exc)})
Path(os.environ["AINATIVE_UE5_PROBE_OUTPUT"]).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(result,ensure_ascii=False))
