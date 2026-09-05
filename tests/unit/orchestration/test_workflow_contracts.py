from pathlib import Path

from ainative.orchestration.contracts import (
    BlenderCallSurface,
    StepPlan,
    TaskContract,
    TaskResult,
    TaskRoute,
    TaskStatus,
    TransferBackendKind,
)
from ainative.orchestration.planning import check_workflow_tools
from ainative.registry import ToolsetRegistry
from ainative.toolsets.blender_editor.execution import (
    BlenderAddonSurface,
    BlenderExecutor,
)
from ainative.toolsets.transfer_assetsbridge import (
    AssetsBridgeBackend,
    AssetsBridgeJsonProtocol,
)
from ainative.toolsets.validation_workflow import AssetsBridgeValidator
from tests.support.plan_factory import call, plan_for, stage_plan


class ReadyConnector:
    def is_ready(self):
        return True

    def export_asset(self, manifest):
        raise AssertionError("Tool feasibility must not execute Tools")

    def import_asset(self, manifest):
        raise AssertionError("Tool feasibility must not execute Tools")


def test_agent_plan_stores_exact_calls_without_requirements_or_binding_pass():
    task = TaskContract(
        task_id="structured-roundtrip",
        objective="Edit a UE5 mesh in Blender and return it",
        route=TaskRoute.ASSET_TRANSFER,
        preferred_backend=TransferBackendKind.ASSETSBRIDGE,
        preserve_relations=frozenset({"asset_identity", "transform"}),
    )
    tool_call = call("blender.editor", "blender", "translate-active", "modify-1")
    plan = plan_for(
        task,
        (StepPlan("modify-asset", "Modify the edit-host asset", (stage_plan("stage.modify_asset", "Modify", "translate-active", (tool_call,)),)),),
    )

    stage = plan.workflow.steps[0].stages[0]
    assert stage.calls == (tool_call,)
    assert not hasattr(stage, "tool_requirements")


def test_full_plan_feasibility_checks_agent_selected_calls_before_execution(tmp_path: Path):
    task = TaskContract(
        task_id="check-roundtrip",
        objective="Edit a UE5 mesh in Blender and return it",
        route=TaskRoute.ASSET_TRANSFER,
        preferred_backend=TransferBackendKind.ASSETSBRIDGE,
    )
    calls = (
        call("blender.editor", "blender", "translate-active", "modify-1"),
        call("transfer.assetsbridge", "assetsbridge", "return_to_target", "return-1", depends_on=("modify-1",)),
        call("validation.workflow", "validator", "validate", "validate-1", depends_on=("return-1",)),
    )
    plan = plan_for(
        task,
        (StepPlan("execute", "Execute selected Tools", (stage_plan("stage.execute", "Execute", "", calls),)),),
    )
    blender = BlenderExecutor({
        BlenderCallSurface.ADDON: BlenderAddonSurface(
            lambda request: TaskResult(status=TaskStatus.SUCCEEDED, route=task.route.value)
        )
    })
    backend = AssetsBridgeBackend(ReadyConnector(), ReadyConnector())
    validator = AssetsBridgeValidator(AssetsBridgeJsonProtocol(tmp_path))
    registry = ToolsetRegistry({"blender": blender, "assetsbridge": backend, "validator": validator})

    issues = check_workflow_tools(plan, registry)

    assert issues == ()
    assert plan.workflow.steps[0].stages[0].calls == calls
