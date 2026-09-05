import json
import os
from pathlib import Path

import unreal

result={"engine":unreal.SystemLibrary.get_engine_version(),"status":"failed"}
try:
    data=unreal.AssetsBridgeTools.get_asset_data_from_path("/Engine/BasicShapes/Cube.Cube")
    result["asset_data"] = str(data)
    export_info, ok, message = unreal.AssetsBridgeTools.get_export_info(data)
    result.update({"ok":bool(ok),"message":str(message),"export_info":str(export_info),"export_info_tuple":export_info.to_tuple() if export_info else None,"status":"succeeded" if ok else "failed"})
except Exception as exc:
    result.update({"error_type":type(exc).__name__,"error":str(exc)})
# Best effort serialization for Unreal structs.
def serial(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
        try:
            return [serial(v) for v in value]
        except TypeError:
            pass
    return str(value)

out=Path(os.environ["AINATIVE_UE5_PROBE_OUTPUT"]); out.write_text(json.dumps(serial(result),ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(serial(result),ensure_ascii=False))

