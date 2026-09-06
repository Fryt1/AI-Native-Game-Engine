from __future__ import annotations

import json
from pathlib import Path

from ainative.cli.execute import (
    ToolExecutionContext,
    execute_resolved,
    to_execution_result,
)
from ainative.orchestration import RuntimeContext
from ainative.orchestration.contracts import (
    BlenderCallSurface,
    TaskContract,
    TaskResult,
    TaskRoute,
    TaskStatus,
    ToolCall,
    ToolExecutionKind,
    TransferBackendKind,
)
from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.registry import toolset_from_operations
from ainative.toolsets.transfer_direct import DirectTransferBackend


class FakeHost:
    executor_id = "fake-host"
    host_id = "blender"

    def is_ready(self):
        return True

    def toolsets(self):
        return (
            toolset_from_operations(
                toolset_id="blender.editor",
                provider_id="blender",
                execution_kind=ToolExecutionKind.HOST,
                operations={"set-location": "Set object location"},
            ),
        )

    def execute(self, request):
        return TaskResult(
            status=TaskStatus.SUCCEEDED,
            route=TaskRoute.HOST_OPERATION.value,
            details={"location": request.parameters["location"], "applied": True},
        )


def test_project_tool_cli_execution_round_trip(tmp_path: Path):
    host = FakeHost()
    runtime = RuntimeContext(executors={"blender": host})
    task = TaskContract(
        task_id="cli-task",
        objective="Move an object",
        route=TaskRoute.HOST_OPERATION,
        metadata={},
    )
    call = ToolCall(
        call_id="cli-1",
        toolset_id="blender.editor",
        tool_id="blender.editor.set_location",
        arguments={"location": [1, 2, 3]},
    )
    resolved = runtime.resolve_tool(call)
    task_result = execute_resolved(runtime, call, resolved, ToolExecutionContext(task=task, plan_host_app="blender"))
    execution = to_execution_result(call, task_result)

    assert execution.status is TaskStatus.SUCCEEDED
    assert execution.outputs == {"location": [1, 2, 3], "applied": True}
    payload = json.dumps(execution.to_dict(), ensure_ascii=False)
    assert '"kind": "tool"' in payload
    assert '"tool_id": "blender.editor.set_location"' in payload


class FakeDirectIO:
    def __init__(self):
        self.events = []

    def is_ready(self):
        return True

    def export_source(self, manifest):
        self.events.append("export_source")
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value)

    def import_target(self, manifest):
        self.events.append("import_target")
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value)


class FakeTransferBlender:
    def __init__(self, events):
        self.events = events

    def execute(self, request):
        self.events.append(request.operation)
        return TaskResult(status=TaskStatus.SUCCEEDED, route=TaskRoute.ASSET_TRANSFER.value)

    def can_use(self, surface):
        return True

    def is_ready(self):
        return True


def test_direct_transfer_execution_uses_blender_import_and_export_seams():
    events = []
    io = FakeDirectIO()
    backend = DirectTransferBackend(io)
    task = TaskContract(
        task_id="direct-execution",
        objective="move a file through Blender",
        route=TaskRoute.ASSET_TRANSFER,
        preferred_backend=TransferBackendKind.DIRECT,
        source_context={"app": "ue5"},
        target_context={"app": "ue5"},
    )
    runtime = RuntimeContext(
        executors={"blender": FakeTransferBlender(events)},
        transfer_backends={TransferBackendKind.DIRECT: backend},
    )
    manifest = TransferManifest.from_task(task)
    call = ToolCall(
        call_id="direct-transfer",
        toolset_id="transfer.direct",
        tool_id="transfer.direct.transfer_to_edit_host",
    )
    resolved = runtime.resolve_tool(call)

    result = execute_resolved(
        runtime,
        call,
        resolved,
        ToolExecutionContext(
            task=task,
            manifest=manifest,
            plan_route=TaskRoute.ASSET_TRANSFER.value,
            plan_host_app="blender",
            plan_blender_call_surface=BlenderCallSurface.CLI_PYTHON.value,
            plan_transfer_backend=TransferBackendKind.DIRECT.value,
        ),
    )

    assert result.status is TaskStatus.SUCCEEDED
    assert io.events == ["export_source"]
    assert events == ["import-glb"]
