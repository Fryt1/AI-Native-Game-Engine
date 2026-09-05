import sys
from pathlib import Path
from types import SimpleNamespace

ADDON_ROOT = Path(__file__).parents[4] / "src" / "ainative" / "toolsets" / "blender_editor" / "execution"
sys.path.insert(0, str(ADDON_ROOT))

from blender_addon.operations import execute_operation


class FakeObject:
    name = "Cube"
    type = "MESH"
    location = (0.0, 0.0, 0.0)
    rotation_euler = (0.0, 0.0, 0.0)
    scale = (1.0, 1.0, 1.0)


def fake_bpy():
    return SimpleNamespace(context=SimpleNamespace(active_object=FakeObject()))


def test_translate_active_is_deterministic_without_real_blender():
    bpy = fake_bpy()

    result = execute_operation("translate-active", {"delta": [1, 2, 3]}, bpy)

    assert result["status"] == "succeeded"
    assert result["object"]["location"] == [1.0, 2.0, 3.0]


def test_unknown_operation_returns_explicit_error():
    result = execute_operation("unknown-operation", {}, fake_bpy())

    assert result["status"] == "failed"
    assert "unsupported Blender operation" in result["errors"][0]
