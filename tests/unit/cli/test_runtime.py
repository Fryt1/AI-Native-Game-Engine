from pathlib import Path

import pytest

from ainative.cli.runner import build_runtime
from ainative.orchestration.contracts import TransferBackendKind
from ainative.toolsets.transfer_assetsbridge.local import JsonUE5BridgeConnector
from ainative.toolsets.ue5_editor.execution import UnrealEditorPythonExecutor


def test_build_runtime_wires_real_ue5_executor_into_assetsbridge(tmp_path: Path):
    project = tmp_path / "Game.uproject"
    script = tmp_path / "bridge.py"
    project.write_text("{}", encoding="utf-8")
    script.write_text("# bridge", encoding="utf-8")

    runtime = build_runtime(
        {
            "blender": {"executable": "blender"},
            "ue5": {"executable": "ue5", "project": str(project), "script": str(script)},
            "assetsbridge": {"directory": str(tmp_path / "bridge")},
        }
    )

    backend = runtime.transfer_backends[TransferBackendKind.ASSETSBRIDGE]
    assert (tmp_path / "bridge").is_dir()
    assert isinstance(runtime.ue5, UnrealEditorPythonExecutor)
    assert backend.ue5_connector is runtime.ue5
    assert not isinstance(backend.ue5_connector, JsonUE5BridgeConnector)


def test_build_runtime_requires_explicit_protocol_only_mode_without_ue5(tmp_path: Path):
    with pytest.raises(ValueError, match="protocol_only=true"):
        build_runtime(
            {
                "blender": {"executable": "blender"},
                "assetsbridge": {"directory": str(tmp_path / "bridge")},
            }
        )


def test_build_runtime_allows_explicit_protocol_only_mode(tmp_path: Path):
    runtime = build_runtime(
        {
            "blender": {"executable": "blender"},
            "assetsbridge": {"directory": str(tmp_path / "bridge"), "protocol_only": True},
        }
    )

    backend = runtime.transfer_backends[TransferBackendKind.ASSETSBRIDGE]
    assert isinstance(backend.ue5_connector, JsonUE5BridgeConnector)
