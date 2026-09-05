import json
import os
from pathlib import Path

import unreal

names=sorted(x for x in dir(unreal) if 'Export' in x or 'GLTF' in x or 'AssetTools' in x)
result={"engine":unreal.SystemLibrary.get_engine_version(),"names":names,"has_export_task":hasattr(unreal,"AssetExportTask"),"has_gltf_exporter":any("GLTF" in x for x in names)}
Path(os.environ["AINATIVE_UE5_PROBE_OUTPUT"]).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(result,ensure_ascii=False))
