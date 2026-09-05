"""Real Blender 4.2 bpy smoke test.

Run with the project's optional environment:
    .venv\\Scripts\\python.exe scripts\\e2e\\real_blender_bpy_smoke.py
"""

from __future__ import annotations

import json
from pathlib import Path

import bpy

PROJECT_ROOT = Path(__file__).resolve().parents[3]
import sys

IMPLEMENTATIONS_ROOT = PROJECT_ROOT / "src" / "ainative" / "toolsets" / "blender_editor" / "execution"
if str(IMPLEMENTATIONS_ROOT) not in sys.path:
    sys.path.insert(0, str(IMPLEMENTATIONS_ROOT))

import blender_addon
from blender_addon.operations import execute_operation


def main() -> int:
    output = PROJECT_ROOT / "artifacts" / "scratch" / "real-blender-bpy-smoke"
    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(location=(0.0, 0.0, 0.0))
    translated = execute_operation("translate-active", {"delta": [1, 2, 3]})
    scaled = execute_operation("set-scale", {"scale": [2, 3, 4]})
    blend_file = output / "asset.blend"
    saved = execute_operation("save-mainfile", {"filepath": str(blend_file)})
    blender_addon.register()
    blender_addon.unregister()
    result = {
        "status": "succeeded",
        "blender_version": bpy.app.version_string,
        "translated": translated,
        "scaled": scaled,
        "saved": saved,
        "blend_file": str(blend_file),
        "blend_bytes": blend_file.stat().st_size,
        "addon_register_cycle": "succeeded",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

