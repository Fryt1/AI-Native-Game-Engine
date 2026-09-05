"""Blender --background --python entry point for the CLI Call Surface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
IMPLEMENTATIONS_DIR = SCRIPT_DIR
if str(IMPLEMENTATIONS_DIR) not in sys.path:
    sys.path.insert(0, str(IMPLEMENTATIONS_DIR))

from blender_addon.operations import execute_operation


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv if argv is None else argv)
    if "--" in args:
        args = args[args.index("--") + 1 :]
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-file", required=True, type=Path)
    parser.add_argument("--result-file", required=True, type=Path)
    ns = parser.parse_args(args)
    request = json.loads(ns.request_file.read_text(encoding="utf-8"))
    result = execute_operation(request["operation"], request.get("parameters", {}))
    ns.result_file.parent.mkdir(parents=True, exist_ok=True)
    ns.result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result.get("status") == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
