import json
import os
from pathlib import Path

import unreal

result = {
    "engine": str(unreal.SystemLibrary.get_engine_version()),
    "bridge_types": sorted(name for name in dir(unreal) if "Bridge" in name or "bridge" in name),
    "asset_tools": sorted(name for name in dir(unreal) if "Asset" in name and "Tool" in name),
}
path = Path(os.environ.get("AINATIVE_UE5_PROBE_OUTPUT", "ue5-python-probe.json"))
path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
