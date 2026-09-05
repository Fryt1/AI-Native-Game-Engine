import sys
from pathlib import Path
from subprocess import CompletedProcess

from ainative.orchestration.contracts import TaskStatus
from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.toolsets.ue5_editor.execution import UnrealEditorCommandExecutor


def test_ue5_command_executor_keeps_project_command_injected(tmp_path: Path):
    project = tmp_path / "Test.uproject"
    project.write_text("{}", encoding="utf-8")
    calls = []
    manifest = TransferManifest("t1", "asset", "ue5", "blender")

    def builder(operation, selected):
        assert selected is manifest
        return [sys.executable, "-c", "print('ue5')", operation]

    def runner(args, **kwargs):
        calls.append(args)
        return CompletedProcess(args, 0, stdout="ue5", stderr="")

    executor = UnrealEditorCommandExecutor(sys.executable, project, command_builder=builder, runner=runner)

    result = executor.export_asset(manifest)

    assert result.status is TaskStatus.SUCCEEDED
    assert calls[0][-1] == "export_asset"
