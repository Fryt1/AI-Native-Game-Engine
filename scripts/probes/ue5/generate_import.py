"""Apply from-blender.json through AssetsBridge's UE5 GenerateImport."""

import json
import os
from pathlib import Path

import unreal


def main() -> int:
    bridge = os.environ["AINATIVE_BRIDGE_DIR"]
    result_file = Path(os.environ["AINATIVE_RESULT_FILE"])
    result = {"engine": unreal.SystemLibrary.get_engine_version(), "bridge": bridge, "status": "failed"}
    try:
        unreal.AssetsBridgeTools.set_export_root(bridge)
        ok, message = unreal.BridgeManager.generate_import()
        saved = None
        if ok:
            try:
                saved = bool(unreal.EditorLoadingAndSavingUtils.save_dirty_packages(False, True))
            except Exception as save_exc:
                result["save_warning"] = str(save_exc)
        result.update({"ok": bool(ok), "message": str(message), "saved_dirty_packages": saved, "status": "succeeded" if ok else "failed"})
    except Exception as exc:
        result.update({"error_type": type(exc).__name__, "error": str(exc)})
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
