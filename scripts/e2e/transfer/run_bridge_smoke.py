"""Run the complete local Bridge-shaped smoke workflow.

This uses a real Blender executable and the repository's JSON UE5 endpoint. It
verifies the Agent/Skill plan, Bridge JSON files, Blender import/modify/export,
and manifest validation without pretending a live UE5 editor command was run.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC = PROJECT_ROOT / "src"
SKILL_ROOT = PROJECT_ROOT / "skills" / "ai-native-workflow-orchestration"
for path in (SRC, SKILL_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from support.plan_fixtures import asset_roundtrip_plan, execute_agent_plan

from ainative.orchestration import RuntimeContext
from ainative.orchestration.contracts import (
    BlenderCallSurface,
    TaskContract,
    TaskResult,
    TaskRoute,
    TaskStatus,
    TransferBackendKind,
)
from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.toolsets.blender_editor.execution import (
    BlenderCliSurface,
    BlenderExecutor,
    BlenderOperationRequest,
)
from ainative.toolsets.transfer_assetsbridge import (
    AssetsBridgeBackend,
    AssetsBridgeJsonProtocol,
    JsonUE5BridgeConnector,
    LocalBlenderBridgeConnector,
)
from ainative.toolsets.validation_workflow import AssetsBridgeValidator


def find_blender() -> Path | None:
    configured = os.environ.get("BLENDER_EXECUTABLE")
    candidates = [
        configured,
        shutil.which("blender"),
        r"E:\blender\blender.exe",
        r"D:\Blender\Blender-5.0.0\blender-5.0.0-windows-x64\blender.exe",
        r"D:\Blender\Blender-4.2.0\blender-4.2.0-windows-x64\blender.exe",
    ]
    return next((Path(candidate) for candidate in candidates if candidate and Path(candidate).is_file()), None)


class ReadyJsonUE5:
    executor_id = "json-ue5-smoke"
    host_id = "ue5"

    def is_ready(self) -> bool:
        return True

    def execute(self, request):
        raise NotImplementedError

    def export_asset(self, manifest):
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value)

    def import_asset(self, manifest):
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "artifacts" / "scratch" / "bridge-smoke")
    args = parser.parse_args()
    blender_exe = find_blender()
    if blender_exe is None:
        print(json.dumps({"status": "blocked", "reason": "no Blender executable found"}, ensure_ascii=False, indent=2))
        return 2
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    source = out / "source.blend"
    source_glb = out / "source.glb"
    edit = out / "edit.blend"
    modified = out / "modified.blend"
    modified_glb = out / "modified.glb"
    cli = BlenderCliSurface(blender_exe)
    create = cli.execute(BlenderOperationRequest(task_id="bridge-smoke-create", operation="create-cube", call_surface=BlenderCallSurface.CLI_PYTHON, parameters={"location": [0, 0, 0], "save_after": str(source), "result_file": str(out / "create.json")}))
    export = cli.execute(BlenderOperationRequest(task_id="bridge-smoke-source-export", operation="export-glb", call_surface=BlenderCallSurface.CLI_PYTHON, parameters={"blend_file": str(source), "filepath": str(source_glb), "result_file": str(out / "source-export.json")}))
    if create.status.value != "succeeded" or export.status.value != "succeeded":
        print(json.dumps({"status": "failed", "create": create.errors, "export": export.errors}, ensure_ascii=False, indent=2))
        return 1
    protocol = AssetsBridgeJsonProtocol(out)
    blender = BlenderExecutor({BlenderCallSurface.CLI_PYTHON: cli})
    backend = AssetsBridgeBackend(JsonUE5BridgeConnector(protocol), LocalBlenderBridgeConnector(blender, out, BlenderCallSurface.CLI_PYTHON))
    task = TaskContract(
        task_id="bridge-smoke",
        objective="Edit the UE5 Static Mesh in Blender and return it to the original asset.",
        route=TaskRoute.ASSET_TRANSFER,
        profile="default",
        asset_type="static_mesh",
        direction="ue5_to_blender_to_ue5",
        preserve_relations=frozenset({"asset_identity", "material_slots", "transform"}),
        preferred_backend=TransferBackendKind.ASSETSBRIDGE,
        preferred_call_surface=BlenderCallSurface.CLI_PYTHON,
        source_context={"app": "ue5", "asset_id": "/Game/Meshes/SM_Test"},
        target_context={"app": "ue5"},
        metadata={"edit_app": "blender", "source_export_file": str(source_glb), "export_file": str(modified_glb), "blender_edit_file": str(edit), "modified_blend_file": str(modified), "blender_operation": "translate-active", "delta": [1, 0, 0], "file_format": "glb", "result_dir": str(out)},
    )
    manifest = TransferManifest.from_task(task)
    protocol.write("from_unreal", protocol.document_for_manifest(manifest, "UnrealExport"))
    runtime = RuntimeContext(blender=blender, ue5=ReadyJsonUE5(), transfer_backends={TransferBackendKind.ASSETSBRIDGE: backend}, validator=AssetsBridgeValidator(protocol))
    plan = asset_roundtrip_plan(task, "assetsbridge")
    run = execute_agent_plan(task, plan, runtime, manifest=manifest)
    payload = {"status": run.status.value, "skill_id": "ai-native-workflow-orchestration", "route": run.route, "workflow_id": run.workflow_id, "profile": run.profile, "authority_id": run.authority_id, "backend": run.backend, "call_surface": run.call_surface, "steps_completed": list(run.steps_completed), "stages_completed": list(run.stages_completed), "preserved_relations": sorted(run.preserved_relations), "lost_relations": sorted(run.lost_relations), "artifacts": [artifact.uri for artifact in run.artifacts], "files": {name: path.is_file() for name, path in {"source_blend": source, "source_glb": source_glb, "edit_blend": edit, "modified_blend": modified, "modified_glb": modified_glb, "from_unreal": out / "from-unreal.json", "from_blender": out / "from-blender.json"}.items()}}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if run.status.value == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())




