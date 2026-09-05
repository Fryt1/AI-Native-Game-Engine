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
    TaskContract,
    TaskResult,
    TaskRoute,
    TaskStatus,
    ToolCall,
    ToolExecutionKind,
)
from ainative.registry import toolset_from_operations


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
    runtime = RuntimeContext(blender=host)
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
