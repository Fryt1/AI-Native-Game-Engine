import os
from pathlib import Path

import pytest

from ainative.agent import WorkflowGuide
from ainative.orchestration import RuntimeContext
from ainative.orchestration.contracts import (
    BlenderCallSurface,
    StepPlan,
    TaskContract,
    TaskRoute,
    TaskStatus,
    TransferBackendKind,
)
from ainative.toolsets.blender_editor.execution import (
    BlenderCliSurface,
    BlenderExecutor,
)
from ainative.toolsets.transfer_direct import DirectTransferBackend, FileTransferIO
from ainative.toolsets.validation_workflow import ManifestValidator
from tests.support.plan_factory import (
    call,
    execute_local_tool_and_submit,
    plan_for,
    stage_plan,
)

BLENDER = Path(os.environ.get("BLENDER_EXECUTABLE", r"E:\blender\blender.exe"))


class ReadyUE5:
    executor_id = "direct-test-ue5"
    host_id = "ue5"

    def is_ready(self):
        return True

    def execute(self, request):
        raise NotImplementedError

    def export_asset(self, manifest):
        raise NotImplementedError

    def import_asset(self, manifest):
        raise NotImplementedError


def direct_plan(task):
    transfer = call("transfer.direct", "direct", "transfer_to_edit_host", "transfer-1")
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
    return_call = call("transfer.direct", "direct", "return_to_target", "return-1", depends_on=(modify.call_id,))
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
def test_direct_transfer_workflow_uses_real_blender_and_reports_file_result(tmp_path: Path):
    source = Path.cwd() / "projects" / "fixtures" / "blender" / "real-cli-glb" / "asset.glb"
    assert source.is_file()
    exchange = tmp_path / "exchange.glb"
    target = tmp_path / "target.glb"
    edit = tmp_path / "edit.blend"
    modified = tmp_path / "modified.blend"
    task = TaskContract(
        task_id="direct-real-workflow",
        objective="Send a mesh file to UE5 without identity restoration",
        route=TaskRoute.ASSET_TRANSFER,
        preferred_backend=TransferBackendKind.DIRECT,
        preferred_call_surface=BlenderCallSurface.CLI_PYTHON,
        source_context={"app": "ue5", "asset_id": "direct-asset", "asset_path": str(source)},
        target_context={"app": "ue5", "asset_path": str(target)},
        metadata={"edit_app": "blender", "export_file": str(exchange), "blender_edit_file": str(edit), "modified_blend_file": str(modified), "delta": [2, 0, 0], "result_dir": str(tmp_path)},
    )
    blender = BlenderExecutor({BlenderCallSurface.CLI_PYTHON: BlenderCliSurface(BLENDER)})
    runtime = RuntimeContext(blender=blender, ue5=ReadyUE5(), transfer_backends={TransferBackendKind.DIRECT: DirectTransferBackend(FileTransferIO())}, validator=ManifestValidator())

    plan = direct_plan(task)
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
    assert result.backend == "direct"
    assert result.stages_completed == ("stage.transfer_to_edit_host", "stage.modify_asset", "stage.return_to_target", "stage.validate_asset")
    assert exchange.is_file() and target.is_file() and target.read_bytes() == exchange.read_bytes()
