"""Validate the local Skill package before routing.

The gate exists so a required prompt asset cannot silently disappear. Every file
listed here is one an Agent is told to read; a missing one is a broken Skill.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    ok: bool
    package_root: str
    missing: tuple[str, ...] = ()
    checked: tuple[str, ...] = ()


def check_package(package_root: Path) -> IntegrityReport:
    required = (
        "SKILL.md",
        "guidance/index.md",
        "guidance/asset-edit.md",
        "guidance/host-operation.md",
        "guidance/asset-roundtrip.md",
        "guidance/native-blender-operation.md",
        "guidance/provider-artifact-apply.md",
        "guidance/failure-recovery.md",
        "references/tool-contract.md",
        "references/blender-call-surfaces.md",
        "references/ue5-call-surfaces.md",
        "templates/workflow-template.md",
        "templates/workflow-plan-template.md",
        "templates/workflow-plan-template.json",
    )
    missing = tuple(path for path in required if not (package_root / path).is_file())
    return IntegrityReport(ok=not missing, package_root=str(package_root), missing=missing, checked=required)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_root", type=Path, nargs="?", default=Path(__file__).resolve().parent)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    report = check_package(args.package_root.resolve())
    if args.as_json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print("OK" if report.ok else "MISSING: " + ", ".join(report.missing))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
