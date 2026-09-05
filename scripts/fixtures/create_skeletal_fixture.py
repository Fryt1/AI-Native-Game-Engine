"""Create a minimal skinned mesh + morph target GLB fixture in Blender."""

from __future__ import annotations

import json
import os
from pathlib import Path

import bpy


def main() -> int:
    out = Path(os.environ["AINATIVE_SKELETAL_OUT"])
    out.mkdir(parents=True, exist_ok=True)
    blend = out / "skeletal-source.blend"
    glb = out / "skeletal-source.glb"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    vertices = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (4, 0, 3, 7)]
    mesh = bpy.data.meshes.new("SK_TestMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("SK_Test", mesh)
    bpy.context.collection.objects.link(obj)
    arm_data = bpy.data.armatures.new("SK_TestArmature")
    armature = bpy.data.objects.new("SK_TestArmature", arm_data)
    bpy.context.collection.objects.link(armature)
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bone = arm_data.edit_bones.new("root")
    bone.head = (0, 0, -1)
    bone.tail = (0, 0, 1)
    bpy.ops.object.mode_set(mode="OBJECT")
    armature.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    group = obj.vertex_groups.new(name="root")
    group.add(list(range(len(vertices))), 1.0, "REPLACE")
    modifier = obj.modifiers.new(name="Armature", type="ARMATURE")
    modifier.object = armature
    obj.shape_key_add(name="Basis")
    smile = obj.shape_key_add(name="Smile")
    smile.data[6].co.x += 0.35
    obj["AB_stringType"] = "SkeletalMesh"
    obj["AB_shortName"] = "SK_Test"
    obj["AB_isExportRoot"] = True
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB", use_selection=True, export_apply=True, export_skins=True, export_all_influences=True, export_morph=True, export_morph_normal=True, export_animations=False, export_extras=True, export_draco_mesh_compression_enable=False)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    result = {"status": "succeeded", "blend": str(blend), "glb": str(glb), "blend_bytes": blend.stat().st_size, "glb_bytes": glb.stat().st_size, "shape_keys": [key.name for key in obj.data.shape_keys.key_blocks], "bones": [bone.name for bone in arm_data.bones]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
