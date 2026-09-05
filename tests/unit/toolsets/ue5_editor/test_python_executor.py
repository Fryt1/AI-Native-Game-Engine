import json
import sys
from pathlib import Path
from subprocess import CompletedProcess

from ainative.orchestration.contracts import TaskStatus
from ainative.toolsets.ue5_editor.execution import UnrealEditorPythonExecutor


def test_ue5_python_executor_runs_injected_command_and_reads_result(tmp_path: Path):
    project = tmp_path / "Test.uproject"
    project.write_text("{}", encoding="utf-8")
    script = tmp_path / "entry.py"
    script.write_text("# entry", encoding="utf-8")

    def runner(args, **kwargs):
        output = Path(kwargs["env"]["AINATIVE_UE5_RESULT_FILE"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"status": "succeeded"}), encoding="utf-8")
        return CompletedProcess(args, 0, stdout="ok", stderr="")

    executor = UnrealEditorPythonExecutor(sys.executable, project, script, runner=runner)
    result = executor.inspect()

    assert result.status is TaskStatus.SUCCEEDED
    assert result.call_surface == "ue5-python"
    operations = tuple(tool.operation for tool in executor.toolsets()[0].tools)
    assert "create_level_from_template" in operations
    assert "inspect_level" in operations


def test_ue5_python_executor_editor_mode_keeps_visible_editor_contract(tmp_path: Path):
    project = tmp_path / "Test.uproject"
    project.write_text("{}", encoding="utf-8")
    script = tmp_path / "entry.py"
    script.write_text("# entry", encoding="utf-8")
    captured = {}

    def runner(args, **kwargs):
        captured["args"] = args
        output = Path(kwargs["env"]["AINATIVE_UE5_RESULT_FILE"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"status": "succeeded"}), encoding="utf-8")
        return CompletedProcess(args, 0, stdout="ok", stderr="")

    executor = UnrealEditorPythonExecutor(
        sys.executable,
        project,
        script,
        runner=runner,
        launch_mode="editor",
        extra_args=("-dx11",),
    )
    result = executor.inspect()

    assert result.status is TaskStatus.SUCCEEDED
    assert captured["args"][:3] == [sys.executable, str(project), "-nop4"]
    assert "-dx11" in captured["args"]
    assert "-unattended" not in captured["args"]
    assert "-nullrhi" not in captured["args"]
