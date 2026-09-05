import json
import os
from pathlib import Path

import unreal

bridge=os.environ["AINATIVE_BRIDGE_DIR"]
result={"engine":unreal.SystemLibrary.get_engine_version(),"bridge":bridge,"status":"failed"}
try:
    unreal.AssetsBridgeTools.set_export_root(bridge)
    ok,message=unreal.BridgeManager.generate_import()
    result.update({"ok":bool(ok),"message":str(message),"status":"succeeded" if ok else "failed"})
except Exception as exc:
    result.update({"error_type":type(exc).__name__,"error":str(exc)})
Path(os.environ["AINATIVE_UE5_PROBE_OUTPUT"]).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(result,ensure_ascii=False))
