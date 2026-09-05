"""Read-only probe for a local Unreal Editor executable."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path


def find_executable() -> str | None:
    configured = os.environ.get("UE5_EDITOR")
    candidates = [configured, shutil.which("UnrealEditor.exe"), r"D:\\UnrealEngine\\ue5.7.1\\UnrealEngine\\Engine\\Binaries\\Win64\\UnrealEditor.exe"]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate).resolve())
    return None


def main() -> int:
    executable = find_executable()
    if not executable:
        print(json.dumps({"ok": True, "available": False, "executable": None, "reason": "no Unreal Editor executable was found"}, ensure_ascii=False, indent=2))
        return 0
    version_file = Path(executable).with_name("UnrealEditor.version")
    version = None
    if version_file.is_file():
        try:
            version = json.loads(version_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            version = version_file.read_text(encoding="utf-8", errors="replace").strip()
    print(json.dumps({"ok": True, "available": True, "executable": executable, "version": version, "version_file": str(version_file) if version_file.is_file() else None}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
