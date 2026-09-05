import json
import os
from pathlib import Path

import pytest

from ainative.orchestration.contracts import BlenderCallSurface
from ainative.toolsets.blender_editor.execution import (
    BlenderCliSurface,
    BlenderOperationRequest,
)

BLENDER = Path(os.environ.get("BLENDER_EXECUTABLE", r"D:\Blender\Blender-4.2.0\blender-4.2.0-windows-x64\blender.exe"))


@pytest.mark.skipif(not BLENDER.is_file(), reason="official Blender executable is not installed")
def test_real_blender_cli_create_modify_export_import_and_inspect(tmp_path: Path):
    surface = BlenderCliSurface(executable=BLENDER)
    source = tmp_path / "source.blend"
    modified = tmp_path / "modified.blend"
    exchange = tmp_path / "asset.glb"
    imported = tmp_path / "imported.blend"

    created = surface.execute(BlenderOperationRequest(task_id="real-cli-create", operation="create-cube", call_surface=BlenderCallSurface.CLI_PYTHON, parameters={"location": [0, 0, 0], "save_after": str(source), "result_file": str(tmp_path / "create-result.json")}))
    changed = surface.execute(BlenderOperationRequest(task_id="real-cli-modify", operation="translate-active", call_surface=BlenderCallSurface.CLI_PYTHON, parameters={"blend_file": str(source), "delta": [7, 0, 0], "save_after": str(modified), "result_file": str(tmp_path / "modify-result.json")}))
    exported = surface.execute(BlenderOperationRequest(task_id="real-cli-export", operation="export-glb", call_surface=BlenderCallSurface.CLI_PYTHON, parameters={"blend_file": str(modified), "filepath": str(exchange), "result_file": str(tmp_path / "export-result.json")}))
    imported_result = surface.execute(BlenderOperationRequest(task_id="real-cli-import", operation="import-glb", call_surface=BlenderCallSurface.CLI_PYTHON, parameters={"filepath": str(exchange), "save_after": str(imported), "result_file": str(tmp_path / "import-result.json")}))
    inspected = surface.execute(BlenderOperationRequest(task_id="real-cli-inspect", operation="inspect-active", call_surface=BlenderCallSurface.CLI_PYTHON, parameters={"blend_file": str(modified), "result_file": str(tmp_path / "inspect-result.json")}))

    assert created.status.value == "succeeded"
    assert changed.status.value == "succeeded"
    assert exported.status.value == "succeeded"
    assert imported_result.status.value == "succeeded"
    assert inspected.status.value == "succeeded"
    assert source.is_file() and modified.is_file() and exchange.is_file() and imported.is_file()
    payload = json.loads((tmp_path / "inspect-result.json").read_text(encoding="utf-8"))
    assert payload["object"]["location"] == [7.0, 0.0, 0.0]
