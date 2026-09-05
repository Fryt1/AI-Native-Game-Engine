from ainative.agent import WorkflowGuide
from ainative.orchestration import RuntimeContext
from ainative.orchestration.contracts import (
    BlenderCallSurface,
    StepPlan,
    TaskContract,
    TaskResult,
    TaskRoute,
    TaskStatus,
    ToolExecutionKind,
    TransferBackendKind,
)
from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.registry import toolset_from_operations
from ainative.toolsets.blender_editor.execution import BlenderExecutor
from ainative.toolsets.ports.host_executor import HostOperationRequest
from tests.support.plan_factory import (
    call,
    execute_local_tool_and_submit,
    plan_for,
    stage_plan,
)


class FakeBlenderSurface:
    call_surface = BlenderCallSurface.ADDON

    def __init__(self, events):
        self.events = events

    def is_ready(self):
        return True

    def execute(self, request):
        self.events.append(f"blender:{request.operation}")
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value)


class FakeUE5:
    executor_id = "fake-ue5"
    host_id = "ue5"

    def __init__(self, events):
        self.events = events

    def is_ready(self):
        return True

    def execute(self, request: HostOperationRequest):
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value)

    def export_asset(self, manifest: TransferManifest):
        self.events.append("ue5:export")
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value)

    def import_asset(self, manifest: TransferManifest):
        self.events.append("ue5:import")
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value)


class FakeBackend:
    backend_id = "assetsbridge"

    def __init__(self, events, ready=True):
        self.events = events
        self.ready = ready

    def is_ready(self):
        return self.ready

    def toolsets(self):
        return (
            toolset_from_operations(
                toolset_id="transfer.assetsbridge",
                provider_id=self.backend_id,
                execution_kind=ToolExecutionKind.TRANSFER,
                operations=("transfer_to_edit_host", "return_to_target"),
            ),
        )

    def export_source(self, manifest):
        self.events.append("backend:export")
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value)

    def import_for_edit(self, manifest):
        self.events.append("backend:import-for-edit")
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value)

    def export_modified(self, manifest):
        self.events.append("backend:export-modified")
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value)

    def import_target(self, manifest):
        self.events.append("backend:import-target")
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value)


class FakeValidator:
    validator_id = "fake-validator"

    def __init__(self, events):
        self.events = events

    def toolsets(self):
        return (
            toolset_from_operations(
                toolset_id="validation.workflow",
                provider_id=self.validator_id,
                execution_kind=ToolExecutionKind.VALIDATOR,
                operations=("validate",),
            ),
        )

    def validate(self, task, manifest):
        self.events.append("validator:validate")
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value, preserved_relations=task.preserve_relations)


def cross_host_runtime(events, backend):
    blender = BlenderExecutor({BlenderCallSurface.ADDON: FakeBlenderSurface(events)})
    return RuntimeContext(
        blender=blender,
        ue5=FakeUE5(events),
        transfer_backends={TransferBackendKind.ASSETSBRIDGE: backend},
        validator=FakeValidator(events),
    )


def roundtrip_plan(task):
    transfer = call("transfer.assetsbridge", "assetsbridge", "transfer_to_edit_host", "transfer-1")
    modify = call("blender.editor", "blender", "translate-active", "modify-1", depends_on=(transfer.call_id,))
    return_call = call("transfer.assetsbridge", "assetsbridge", "return_to_target", "return-1", depends_on=(modify.call_id,))
    validate = call("validation.workflow", "validator", "validate", "validate-1", depends_on=(return_call.call_id,))
    return plan_for(
        task,
        (
            StepPlan("transfer", "Transfer to Blender", (stage_plan("stage.transfer_to_edit_host", "Transfer to edit host", "transfer_to_edit_host", (transfer,)),)),
            StepPlan("modify", "Modify in Blender", (stage_plan("stage.modify_asset", "Modify asset", "translate-active", (modify,)),), depends_on=("transfer",)),
            StepPlan("return", "Return to target", (stage_plan("stage.return_to_target", "Return to target", "return_to_target", (return_call,)),), depends_on=("modify",)),
            StepPlan("validate", "Validate result", (stage_plan("stage.validate_asset", "Validate result", "validate", (validate,)),), depends_on=("return",)),
        ),
    )


def execute_agent_plan(task, plan, runtime):
    session = WorkflowGuide().start(task, plan, runtime)
    for stage in plan.workflow.stage_requests:
        for call_item in stage.calls:
            result = execute_local_tool_and_submit(session, stage, call_item)
            if result.status is not TaskStatus.SUCCEEDED:
                break
        if session.complete_stage(stage.stage_id).status is not TaskStatus.SUCCEEDED:
            break
    return session.finish()


def test_agent_executes_cross_host_tools_in_the_plan_order():
    events = []
    task = TaskContract(
        task_id="run-1",
        objective="Roundtrip a Static Mesh",
        route=TaskRoute.ASSET_TRANSFER,
        preserve_relations=frozenset({"asset_identity", "transform"}),
    )

    result = execute_agent_plan(task, roundtrip_plan(task), cross_host_runtime(events, FakeBackend(events)))

    assert result.status is TaskStatus.SUCCEEDED
    assert result.profile == "default"
    assert result.authority_id == "asset-roundtrip"
    assert result.stages_completed == ("stage.transfer_to_edit_host", "stage.modify_asset", "stage.return_to_target", "stage.validate_asset")
    assert result.preserved_relations == task.preserve_relations
    assert events == ["backend:export", "backend:import-for-edit", "blender:translate-active", "backend:export-modified", "backend:import-target", "validator:validate"]


def test_agent_blocks_selected_assetsbridge_branch_without_silent_downgrade():
    events = []
    task = TaskContract(
        task_id="blocked-bridge",
        objective="Return a mesh to its UE5 source asset",
        route=TaskRoute.ASSET_TRANSFER,
        preserve_relations=frozenset({"asset_identity"}),
    )

    session = WorkflowGuide().start(task, roundtrip_plan(task), cross_host_runtime(events, FakeBackend(events, ready=False)))
    result = session.finish()

    assert result.status is TaskStatus.BLOCKED
    assert any("Tool provider is not ready" in error for error in result.errors)
    assert all(issue.toolset_id == "transfer.assetsbridge" for issue in session.tool_issues)
    assert result.next_action is not None
    assert events == []
