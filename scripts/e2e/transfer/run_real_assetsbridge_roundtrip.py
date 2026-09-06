"""Run the complete Agent/Skill/Workflow-driven AssetsBridge round-trip."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
E2E_ROOT = ROOT / "scripts" / "e2e"
if str(E2E_ROOT) not in sys.path:
    sys.path.insert(0, str(E2E_ROOT))

from support.plan_fixtures import asset_roundtrip_plan, execute_agent_plan

from ainative.orchestration import RuntimeContext
from ainative.orchestration.contracts import (
    BlenderCallSurface,
    TaskContract,
    TaskRoute,
    TransferBackendKind,
)
from ainative.toolsets.blender_editor.execution import (
    BlenderCliSurface,
    BlenderExecutor,
)
from ainative.toolsets.transfer_assetsbridge import (
    AssetsBridgeBackend,
    AssetsBridgeJsonProtocol,
    ExternalBlenderAssetsBridgeConnector,
)
from ainative.toolsets.ue5_editor.execution import UnrealEditorPythonExecutor
from ainative.toolsets.validation_workflow import AssetsBridgeValidator

DEFAULT_UE5 = Path(r"D:\UnrealEngine\ue5.7.1\UnrealEngine\Engine\Binaries\Win64\UnrealEditor-Cmd.exe")
DEFAULT_BLENDER = Path(r"E:\blender\blender.exe")
DEFAULT_PROJECT = ROOT / "projects" / "fixtures" / "ue5" / "assetsbridge-smoke" / "AssetsBridgeSmoke.uproject"
DEFAULT_ADDON = ROOT / "vendor" / "assetsbridge" / "blender-addon" / "AssetsBridgeAddon"


def find_existing(path: Path) -> bool:
    return path.is_file() or path.is_dir()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ue5-editor", type=Path, default=DEFAULT_UE5)
    parser.add_argument("--uproject", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--blender", type=Path, default=DEFAULT_BLENDER)
    parser.add_argument("--addon-root", type=Path, default=DEFAULT_ADDON)
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts" / "evidence" / "blender-ue5-roundtrip")
    args = parser.parse_args()
    required = (args.ue5_editor, args.uproject, args.blender, args.addon_root / "__init__.py", ROOT / "src" / "ainative" / "toolsets" / "ue5_editor" / "execution" / "bridge_entry.py")
    missing = [str(path) for path in required if not find_existing(path)]
    if missing:
        print(json.dumps({"status": "blocked", "missing": missing}, ensure_ascii=False, indent=2))
        return 2

    out = args.out.resolve()
    bridge = out / "bridge"
    out.mkdir(parents=True, exist_ok=True)
    bridge.mkdir(parents=True, exist_ok=True)
    edit_file = bridge / "edit.blend"
    modified_file = bridge / "modified.blend"
    export_file = bridge / "Engine" / "BasicShapes" / "Cube.glb"
    task = TaskContract(
        task_id="real-assetsbridge-roundtrip",
        objective="Edit the UE5 Static Mesh in Blender and return it to the original asset.",
        route=TaskRoute.ASSET_TRANSFER,
        profile="default",
        asset_type="static_mesh",
        direction="ue5_to_blender_to_ue5",
        preserve_relations=frozenset({"asset_identity", "material_slots", "transform"}),
        preferred_backend=TransferBackendKind.ASSETSBRIDGE,
        preferred_call_surface=BlenderCallSurface.CLI_PYTHON,
        source_context={"app": "ue5", "asset_id": "/Engine/BasicShapes/Cube.Cube"},
        target_context={"app": "ue5"},
        metadata={"edit_app": "blender", "ue5_asset_path": "/Engine/BasicShapes/Cube.Cube", "export_file": str(export_file), "blender_edit_file": str(edit_file), "modified_blend_file": str(modified_file), "result_dir": str(out), "blender_operation": "translate-active", "delta": [1, 0, 0], "file_format": "glb"},
    )
    blender_executor = BlenderExecutor({BlenderCallSurface.CLI_PYTHON: BlenderCliSurface(args.blender)})
    ue5_executor = UnrealEditorPythonExecutor(args.ue5_editor, args.uproject, ROOT / "src" / "ainative" / "toolsets" / "ue5_editor" / "execution" / "bridge_entry.py", bridge_dir=bridge, timeout=180)
    blender_connector = ExternalBlenderAssetsBridgeConnector(args.blender, args.addon_root, bridge, out, timeout=120)
    backend = AssetsBridgeBackend(ue5_executor, blender_connector)
    protocol = AssetsBridgeJsonProtocol(bridge)
    runtime = RuntimeContext(executors={"blender": blender_executor, "ue5": ue5_executor}, transfer_backends={TransferBackendKind.ASSETSBRIDGE: backend}, validator=AssetsBridgeValidator(protocol))
    plan = asset_roundtrip_plan(task, "assetsbridge")
    run = execute_agent_plan(task, plan, runtime)
    result = {
        "status": run.status.value,
        "agent_plan": {"skill_id": "ai-native-workflow-orchestration", "route": run.route, "workflow_id": run.workflow_id, "profile": run.profile, "authority_id": run.authority_id, "backend": run.backend, "call_surface": run.call_surface, "modification_method": run.modification_method},
        "steps_completed": list(run.steps_completed),
        "stages_completed": list(run.stages_completed),
        "preserved_relations": sorted(run.preserved_relations),
        "lost_relations": sorted(run.lost_relations),
        "warnings": list(run.warnings),
        "errors": list(run.errors),
        "resume_pointer": run.resume_pointer,
        "artifacts": [artifact.uri for artifact in run.artifacts],
        "files": {name: path.is_file() for name, path in {"from_unreal": bridge / "from-unreal.json", "from_blender": bridge / "from-blender.json", "export_glb": export_file, "edit_blend": edit_file, "modified_blend": modified_file}.items()},
        "output_dir": str(out),
    }
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if run.status.value == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())


