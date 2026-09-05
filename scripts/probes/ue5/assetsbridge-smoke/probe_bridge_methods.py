import json
import os
from pathlib import Path

import unreal

names = ["AssetsBridgeTools", "BridgeManager", "BridgeExport", "BridgeAssets", "BridgeSelection"]
result = {"engine": unreal.SystemLibrary.get_engine_version(), "classes": {}}
for name in names:
    cls = getattr(unreal, name, None)
    result["classes"][name] = {"present": cls is not None, "members": sorted(x for x in dir(cls) if not x.startswith("_") ) if cls else []}
out=Path(os.environ["AINATIVE_UE5_PROBE_OUTPUT"])
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(result,ensure_ascii=False))
