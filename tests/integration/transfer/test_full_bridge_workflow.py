import os
from pathlib import Path

import pytest

from ainative.agent import WorkflowGuide
from ainative.orchestration import RuntimeContext
from ainative.orchestration.contracts import (
    BlenderCallSurface,
    StepPlan,
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
)
from ainative.toolsets.transfer_assetsbridge import (
    AssetsBridgeBackend,
    AssetsBridgeJsonProtocol,
    JsonUE5BridgeConnector,
    LocalBlenderBridgeConnector,
)
from ainative.toolsets.validation_workflow import AssetsBridgeValidator
from tests.support.plan_factory import (
    call,
    execute_local_tool_and_submit,
    plan_for,
    stage_plan,
)

BLENDER = Path(os.environ.get("BLENDER_EXECUTABLE", r"E:\blender\blender.exe"))


class ReadyJsonUE5:
    executor_id = "json-ue5-test"
    host_id = "ue5"

    def is_ready(self):
        return True

    def execute(self, request):
        raise NotImplementedError

    def export_asset(self, manifest):
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value)

    def import_asset(self, manifest):
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value)


def bridge_plan(task):
    transfer = call("transfer.assetsbridge", "assetsbridge", "transfer_to_edit_host", "transfer-1")
    modify = call(
        "blender.editor",
        "blender",
        "translate-active",
        "modify-1",
        {
            "blend_file": str(task.metadata["blender_edit_file"]),
            "save_after": str(task.metadata["modified_blend_file"]),
            "delta": task.metadata["delta"],
        },
        depends_on=(transfer.call_id,),
    )
    return_call = call("transfer.assetsbridge", "assetsbridge", "return_to_target", "return-1", depends_on=(modify.call_id,))
    validate = call("validation.workflow", "validator", "validate", "validate-1", depends_on=(return_call.call_id,))
    return plan_for(
        task,
        (
            StepPlan("transfer", "Transfer to Blender", (stage_plan("stage.transfer_to_edit_host", "Transfer to edit host", "transfer_to_edit_host", (transfer,)),)),
            StepPlan("modify", "Modify in Blender", (stage_plan("stage.modify_asset", "Modify asset", "translate-active", (modify,)),), depends_on=("transfer",)),
            StepPlan("return", "Return to UE5", (stage_plan("stage.return_to_target", "Return to target", "return_to_target", (return_call,)),), depends_on=("modify",)),
            StepPlan("validate", "Validate result", (stage_plan("stage.validate_asset", "Validate result", "validate", (validate,)),), depends_on=("return",)),
        ),
    )


@pytest.mark.skipif(not BLENDER.is_file(), reason="official Blender executable is not installed")
def test_full_assetsbridge_json_workflow_with_real_blender(tmp_path: Path):
    project = Path.cwd()
    source = project / "projects" / "fixtures" / "blender" / "real-cli-glb" / "asset.glb"
    assert source.is_file()
    bridge_dir = tmp_path / "bridge"
    edit_file = bridge_dir / "edit.blend"
    modified_file = bridge_dir / "modified.blend"
    modified_glb = bridge_dir / "modified.glb"
    protocol = AssetsBridgeJsonProtocol(bridge_dir)
    blender = BlenderExecutor({BlenderCallSurface.CLI_PYTHON: BlenderCliSurface(BLENDER)})
    backend = AssetsBridgeBackend(JsonUE5BridgeConnector(protocol), LocalBlenderBridgeConnector(blender, bridge_dir, BlenderCallSurface.CLI_PYTHON))
    task = TaskContract(
        task_id="integration-bridge",
        objective="Roundtrip a Static Mesh through the Bridge JSON contract",
        route=TaskRoute.ASSET_TRANSFER,
        preferred_call_surface=BlenderCallSurface.CLI_PYTHON,
        preferred_backend=TransferBackendKind.ASSETSBRIDGE,
        preserve_relations=frozenset({"asset_identity", "material_slots", "transform"}),
        source_context={"app": "ue5", "asset_id": "/Game/Meshes/SM_Test"},
        target_context={"app": "ue5"},
        metadata={
            "edit_app": "blender",
            "source_export_file": str(source),
            "export_file": str(modified_glb),
            "blender_edit_file": str(edit_file),
            "modified_blend_file": str(modified_file),
            "delta": [1, 0, 0],
            "file_format": "glb",
            "objectMaterials": [
                {"name": "WorldGridMaterial", "idx": 0, "internalPath": "/Engine/EngineMaterials/WorldGridMaterial", "originalIdx": -1}
            ],
        },
    )
    protocol.write("from_unreal", protocol.document_for_manifest(TransferManifest.from_task(task), "UnrealExport"))

    runtime = RuntimeContext(blender=blender, ue5=ReadyJsonUE5(), transfer_backends={TransferBackendKind.ASSETSBRIDGE: backend}, validator=AssetsBridgeValidator(protocol))
    plan = bridge_plan(task)
    session = WorkflowGuide().start(task, plan, runtime)
    for stage in plan.workflow.stage_requests:
        for call_item in stage.calls:
            result = execute_local_tool_and_submit(session, stage, call_item)
            if result.status is not TaskStatus.SUCCEEDED:
                break
        if session.complete_stage(stage.stage_id).status is not TaskStatus.SUCCEEDED:
            break
    result = session.finish()

    assert result.status is TaskStatus.SUCCEEDED
    assert result.stages_completed == ("stage.transfer_to_edit_host", "stage.modify_asset", "stage.return_to_target", "stage.validate_asset")
    assert result.preserved_relations == task.preserve_relations
    assert modified_file.is_file() and modified_glb.is_file() and (bridge_dir / "from-blender.json").is_file()
