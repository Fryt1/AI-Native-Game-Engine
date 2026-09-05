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


def test_bridge_import_rejects_a_document_from_another_transfer(tmp_path: Path):
    bridge = tmp_path / "bridge"
    bridge.mkdir()
    (bridge / "from-unreal.json").write_text(
        '{"operation":"UnrealExport","transfer_id":"old-transfer","objects":[]}',
        encoding="utf-8",
    )
    units = SimpleNamespace(system="METRIC", scale_length=0.01)
    bpy = SimpleNamespace(context=SimpleNamespace(scene=SimpleNamespace(unit_settings=units), active_object=None))

    result = execute_operation(
        "import-bridge-json",
        {"bridge_dir": str(bridge), "transfer_id": "current-transfer"},
        bpy,
    )

    assert result["status"] == "failed"
    assert "old-transfer" in result["errors"][0]
