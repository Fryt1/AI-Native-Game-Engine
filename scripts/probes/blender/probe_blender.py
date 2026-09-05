"""Read-only probe for a local Blender executable."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


def find_executable() -> str | None:
    configured = os.environ.get("BLENDER_EXECUTABLE")
    candidates = [configured, shutil.which("blender"), r"D:\Blender\Blender-5.0.0\blender-5.0.0-windows-x64\blender.exe", r"D:\Blender\Blender-4.2.0\blender-4.2.0-windows-x64\blender.exe", r"D:\Blender\4.2\blender.exe"]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate).resolve())
    return None


def main() -> int:
    executable = find_executable()
    if not executable:
        print(json.dumps({"ok": True, "available": False, "executable": None, "reason": "no Blender executable was found"}, ensure_ascii=False, indent=2))
        return 0
    completed = subprocess.run([executable, "--version"], capture_output=True, text=True, check=False)
    print(json.dumps({"ok": completed.returncode == 0, "available": completed.returncode == 0, "executable": executable, "version": (completed.stdout or completed.stderr).strip()}, ensure_ascii=False, indent=2))
    return 0 if completed.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
