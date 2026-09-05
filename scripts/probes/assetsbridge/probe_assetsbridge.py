"""Read-only probe for an AssetsBridge shared directory and optional components."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bridge_dir", type=Path)
    parser.add_argument("--ue5-plugin", type=Path)
    parser.add_argument("--blender-addon", type=Path)
    args = parser.parse_args()
    bridge = args.bridge_dir.resolve()
    result = {
        "ok": True,
        "bridge_dir": str(bridge),
        "bridge_dir_exists": bridge.is_dir(),
        "from_unreal": str(bridge / "from-unreal.json"),
        "from_unreal_exists": (bridge / "from-unreal.json").is_file(),
        "from_blender": str(bridge / "from-blender.json"),
        "from_blender_exists": (bridge / "from-blender.json").is_file(),
        "ue5_plugin_exists": args.ue5_plugin.is_dir() if args.ue5_plugin else None,
        "blender_addon_exists": args.blender_addon.is_dir() if args.blender_addon else None,
        "full_roundtrip_ready": bridge.is_dir() and (args.ue5_plugin.is_dir() if args.ue5_plugin else False) and (args.blender_addon.is_dir() if args.blender_addon else False),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
