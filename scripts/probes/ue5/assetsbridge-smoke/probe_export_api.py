import json
import os
from pathlib import Path

import unreal

result={}
for cls, methods in {"Exporter":["run_asset_export_task"],"AssetExportTask":["object","exporter","filename","automated","prompt","replace_identical"],"GLTFStaticMeshExporter":["static_class"]}.items():
    obj=getattr(unreal,cls,None); result[cls]={"present":obj is not None}
    if obj:
        result[cls]["members"]=[m for m in dir(obj) if not m.startswith('_')]
        for method in methods:
            try: result[cls][method]=str(getattr(obj,method,None).__doc__)
            except Exception as e: result[cls][method]=str(e)
Path(os.environ["AINATIVE_UE5_PROBE_OUTPUT"]).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(result,ensure_ascii=False))
