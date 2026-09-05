import json
import os
from pathlib import Path

import unreal


def serial(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [serial(item) for item in value]
    if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
        try: return [serial(item) for item in value]
        except TypeError: pass
    return str(value)

result={"engine":unreal.SystemLibrary.get_engine_version(),"classes":{}}
for clsname, methods in {"BridgeManager":["start_export","generate_import","import_asset"],"AssetsBridgeTools":["get_export_info","write_bridge_export_file","read_bridge_export_file","get_export_root"]}.items():
    cls=getattr(unreal,clsname); result[clsname]={m:str(getattr(cls,m,None).__doc__) for m in methods}
for name in ("BridgeExport","BridgeAssets","BridgeSelection"):
    cls=getattr(unreal,name); obj=cls(); result[name]={"properties":[p for p in dir(obj) if not p.startswith('_')],"tuple":serial(obj.to_tuple())}
out=Path(os.environ["AINATIVE_UE5_PROBE_OUTPUT"]); out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(result,ensure_ascii=False))
