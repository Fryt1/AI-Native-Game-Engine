from json import dumps
from pathlib import Path
from subprocess import CompletedProcess

from ainative.orchestration.contracts import BlenderCallSurface, TaskResult, TaskStatus
from ainative.toolsets.blender_editor.execution import (
    BlenderAddonSurface,
    BlenderCliSurface,
    BlenderExecutor,
    BlenderOperationRequest,
)


def test_cli_surface_invokes_background_python_script():
    calls = []

    def runner(args, **kwargs):
        calls.append((args, kwargs))
        result_file = Path(args[args.index("--result-file") + 1])
        result_file.write_text(dumps({"status": "succeeded"}), encoding="utf-8")
        return CompletedProcess(args, 0, stdout="ok", stderr="")

    surface = BlenderCliSurface("blender-test", runner=runner)
    request = BlenderOperationRequest(task_id="cli-1", operation="modify", call_surface=BlenderCallSurface.CLI_PYTHON, parameters={"script": "modify.py", "blend_file": "source.blend"})

    result = surface.execute(request)

    assert result.status is TaskStatus.SUCCEEDED
    args = calls[0][0]
    assert args[:5] == ["blender-test", "--background", "source.blend", "--python", "modify.py"]
    assert "--request-file" in args
    assert "--result-file" in args


def test_blender_executor_delegates_to_selected_addon_surface():
    seen = []

    def execute(request):
        seen.append(request.operation)
        return TaskResult(status=TaskStatus.SUCCEEDED, route="host_operation")

    executor = BlenderExecutor({BlenderCallSurface.ADDON: BlenderAddonSurface(execute)})
    request = BlenderOperationRequest(task_id="addon-1", operation="inspect-selection", call_surface=BlenderCallSurface.ADDON)

    result = executor.execute(request)

    assert result.status is TaskStatus.SUCCEEDED
    assert seen == ["inspect-selection"]
