import json
import os
from pathlib import Path

import unreal

source = os.environ["AINATIVE_BRIDGE_SOURCE"]
result = {"engine": unreal.SystemLibrary.get_engine_version(), "source": source, "status": "failed"}
try:
    obj, ok, message = unreal.BridgeManager.import_asset(source, "/Game/AI_Native_Imported", "StaticMesh", "")
    result.update({"ok": bool(ok), "message": str(message), "imported_object": str(obj), "object_name": obj.get_name() if obj else None, "status": "succeeded" if ok else "failed"})
except Exception as exc:
    result.update({"error_type": type(exc).__name__, "error": str(exc)})
out=Path(os.environ["AINATIVE_UE5_PROBE_OUTPUT"]); out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(result,ensure_ascii=False))
