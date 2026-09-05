"""Validate the local Skill package before routing."""

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
        "workflows/routing.md",
        "workflows/workflow-selection.md",
        "workflows/index.md",
        "workflows/asset-edit.md",
        "workflows/host-operation.md",
        "workflows/asset-roundtrip.md",
        "workflows/native-blender-operation.md",
        "workflows/provider-artifact-apply.md",
        "workflows/profiles/default.md",
        "workflows/profiles/interactive.md",
        "workflows/profiles/headless-batch.md",
        "workflows/stages/resolve-context.md",
        "workflows/stages/read-state.md",
        "workflows/stages/resolve-asset.md",
        "workflows/stages/create-level-from-template.md",
        "workflows/stages/transfer-to-edit-host.md",
        "workflows/stages/modify-asset.md",
        "workflows/stages/apply-change.md",
        "workflows/stages/return-to-target.md",
        "workflows/stages/publish-result.md",
        "workflows/stages/validate-asset.md",
        "workflows/stages/validate-result.md",
        "workflows/stages/provider-artifact.md",
        "workflows/stages/apply-artifact.md",
        "workflows/governance/failure-recovery.md",
        "knowledge/index.md",
        "knowledge/stage-kinds/change.md",
        "knowledge/stage-kinds/investigation.md",
        "knowledge/stage-kinds/planning.md",
        "knowledge/objects/geometry.md",
        "knowledge/objects/skeleton-binding.md",
        "knowledge/objects/animation.md",
        "knowledge/objects/material-texture.md",
        "knowledge/objects/effects-simulation.md",
        "knowledge/objects/scene-level.md",
        "knowledge/objects/references-metadata.md",
        "knowledge/objects/project-runtime-performance.md",
        "knowledge/operations/create.md",
        "knowledge/operations/configure.md",
        "knowledge/operations/import.md",
        "knowledge/operations/export.md",
        "knowledge/operations/modify.md",
        "knowledge/operations/repair.md",
        "knowledge/operations/optimize.md",
        "knowledge/operations/convert.md",
        "knowledge/operations/batch.md",
        "knowledge/operations/publish.md",
        "references/tool-contract.md",
        "toolsets/README.md",
        "toolsets/ue5-editor/TOOLSET.md",
        "toolsets/blender-editor/TOOLSET.md",
        "toolsets/transfer-assetsbridge/TOOLSET.md",
        "toolsets/transfer-direct/TOOLSET.md",
        "toolsets/artifact-provider/TOOLSET.md",
        "toolsets/workflow-validation/TOOLSET.md",
        "references/blender-call-surfaces.md",
        "references/assetsbridge-backend.md",
        "references/direct-transfer-backend.md",
        "references/transfer-manifest.md",
        "references/ue5-call-surfaces.md",
        "scripts/docs/README.md",
        "scripts/docs/blender-cli.md",
        "scripts/docs/ue5-python.md",
        "scripts/docs/assetsbridge-json.md",
        "templates/toolset-template.md",
        "templates/stage-template.md",
        "templates/workflow-template.md",
        "templates/workflow-plan-template.md",
        "templates/workflow-plan-template.json",
        "templates/workflow-plan-schema.json",
    )
    missing = tuple(path for path in required if not (package_root / path).is_file())
    return IntegrityReport(ok=not missing, package_root=str(package_root), missing=missing, checked=required)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package_root", type=Path, nargs="?", default=Path(__file__).parents[1])
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
