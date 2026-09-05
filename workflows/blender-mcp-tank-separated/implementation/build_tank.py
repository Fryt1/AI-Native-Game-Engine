import bpy
import math
from mathutils import Vector

OUTPUT_BLEND = r"__OUTPUT_BLEND__"
OUTPUT_RENDER = r"__OUTPUT_RENDER__"

# Reset the scene while preserving no pre-existing asset state for this fixture.
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for collection in list(bpy.data.collections):
    if collection.name != "Collection" and collection.users == 0:
        bpy.data.collections.remove(collection)

scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.length_unit = "METERS"

def collection(name, parent=None):
    value = bpy.data.collections.get(name)
    if value is None:
        value = bpy.data.collections.new(name)
    owner = parent or scene.collection
    if value.name not in owner.children:
        try:
            owner.children.link(value)
        except RuntimeError:
            pass
    return value

tank = collection("Tank_Separated")
collections = {name: collection(name, tank) for name in (
    "Hull", "Tracks", "Wheels", "Turret", "Armament", "Details", "Presentation"
)}

def material(name, color, metallic=0.0, roughness=0.65):
    value = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    value.diffuse_color = (*color, 1.0)
    value.use_nodes = True
    bsdf = value.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
    return value

body_mat = material("Tank_Body_Green", (0.16, 0.30, 0.10), 0.15, 0.58)
dark_mat = material("Tank_Track_Rubber", (0.025, 0.032, 0.028), 0.0, 0.9)
metal_mat = material("Tank_Metal", (0.12, 0.14, 0.12), 0.75, 0.28)
accent_mat = material("Tank_Accent", (0.34, 0.42, 0.12), 0.1, 0.5)
glass_mat = material("Tank_Optics", (0.02, 0.12, 0.18), 0.2, 0.18)
red_mat = material("Tank_Light_Red", (0.65, 0.025, 0.015), 0.1, 0.35)

root = bpy.data.objects.new("Tank_Root", None)
collections["Hull"].objects.link(root)
root["asset_role"] = "tank_root"
root["separated_parts"] = True

parts = []

def finish(obj, target_collection, role, bevel=0.0):
    for current in list(obj.users_collection):
        current.objects.unlink(obj)
    target_collection.objects.link(obj)
    obj.parent = root
    obj["asset_role"] = role
    obj["separated_part"] = True
    if bevel > 0.0:
        modifier = obj.modifiers.new("EdgeSoftening", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
    parts.append(obj)
    return obj

def cube(name, location, dimensions, target_collection, mat, role, bevel=0.08):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return finish(obj, target_collection, role, bevel)

def cylinder(name, location, radius, depth, target_collection, mat, role, rotation=(0, 0, 0), vertices=32, bevel=0.04):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return finish(obj, target_collection, role, bevel)

def torus(name, location, major, minor, target_collection, mat, role, rotation=(math.pi / 2, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=32, minor_segments=10, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return finish(obj, target_collection, role, 0.0)

# Hull: each armor section is intentionally separate.
cube("Tank_Body_Hull", (0, 0, 1.55), (7.2, 4.0, 1.45), collections["Hull"], body_mat, "hull", 0.18)
cube("Tank_Body_UpperArmor", (-0.25, 0, 2.55), (5.9, 3.45, 0.85), collections["Hull"], body_mat, "upper_armor", 0.12)
cube("Tank_EngineDeck", (-2.15, 0, 3.12), (2.25, 3.15, 0.25), collections["Hull"], accent_mat, "engine_deck", 0.05)
cube("Tank_FrontGlacis", (3.22, 0, 2.45), (0.28, 3.42, 0.9), collections["Hull"], body_mat, "front_glacis", 0.06)

# Tracks and road wheels, left and right remain independent.
for side_name, y in (("Left", 2.35), ("Right", -2.35)):
    cube(f"Tank_Track_{side_name}", (0, y, 0.95), (7.8, 0.62, 1.85), collections["Tracks"], dark_mat, "track_belt", 0.22)
    for index, x in enumerate((-2.9, -1.75, -0.6, 0.6, 1.75, 2.9)):
        cylinder(f"Tank_Wheel_{side_name}_{index:02d}", (x, y * 1.03, 0.96), 0.72, 0.72, collections["Wheels"], metal_mat, "road_wheel", rotation=(math.pi / 2, 0, 0), bevel=0.05)
        cylinder(f"Tank_WheelHub_{side_name}_{index:02d}", (x, y * 1.045, 0.96), 0.25, 0.78, collections["Wheels"], accent_mat, "wheel_hub", rotation=(math.pi / 2, 0, 0), bevel=0.03)
    for index, x in enumerate((-3.25, -2.6, -1.95, -1.3, -0.65, 0, 0.65, 1.3, 1.95, 2.6, 3.25)):
        cube(f"Tank_TrackLink_{side_name}_{index:02d}", (x, y * 1.09, 0.35), (0.48, 0.16, 0.28), collections["Tracks"], dark_mat, "track_link", 0.03)
        cube(f"Tank_TrackLinkTop_{side_name}_{index:02d}", (x, y * 1.09, 1.58), (0.48, 0.16, 0.28), collections["Tracks"], dark_mat, "track_link", 0.03)

# Turret and ring.
cylinder("Tank_TurretRing", (0, 0, 3.38), 1.85, 0.35, collections["Turret"], metal_mat, "turret_ring", bevel=0.05)
cube("Tank_Turret", (0.15, 0, 3.92), (3.35, 2.65, 1.05), collections["Turret"], body_mat, "turret", 0.2)
cube("Tank_TurretFrontArmor", (1.6, 0, 4.05), (0.3, 2.35, 0.85), collections["Turret"], accent_mat, "turret_front_armor", 0.07)
cylinder("Tank_CommanderCupola", (-0.35, 0, 4.68), 0.62, 0.42, collections["Turret"], accent_mat, "commander_cupola", bevel=0.05)
cylinder("Tank_CommanderHatch", (-0.35, 0, 4.92), 0.42, 0.10, collections["Details"], metal_mat, "commander_hatch", bevel=0.02)

# Armament: separate mantlet, barrel and muzzle brake.
cylinder("Tank_GunMantlet", (1.82, 0, 4.0), 0.58, 0.75, collections["Armament"], metal_mat, "gun_mantlet", rotation=(0, math.pi / 2, 0), bevel=0.05)
cylinder("Tank_MainBarrel", (4.0, 0, 4.0), 0.22, 4.1, collections["Armament"], metal_mat, "main_barrel", rotation=(0, math.pi / 2, 0), bevel=0.025)
cylinder("Tank_MuzzleBrake", (6.2, 0, 4.0), 0.38, 0.62, collections["Armament"], metal_mat, "muzzle_brake", rotation=(0, math.pi / 2, 0), bevel=0.04)
cylinder("Tank_CoaxialGun", (2.1, -0.48, 3.85), 0.08, 1.1, collections["Armament"], metal_mat, "coaxial_gun", rotation=(0, math.pi / 2, 0), bevel=0.015)

# Details: optics, lights, exhaust and antennas.
for name, loc in (("Tank_Optic_Left", (0.85, 0.58, 4.5)), ("Tank_Optic_Right", (0.85, -0.58, 4.5))):
    cylinder(name, loc, 0.16, 0.20, collections["Details"], glass_mat, "optic", bevel=0.02)
for side_name, y in (("Left", 1.63), ("Right", -1.63)):
    cylinder(f"Tank_Headlight_{side_name}", (3.48, y, 2.75), 0.20, 0.18, collections["Details"], glass_mat, "headlight", rotation=(math.pi / 2, 0, 0), bevel=0.025)
    cylinder(f"Tank_TailLight_{side_name}", (-3.55, y, 2.35), 0.13, 0.14, collections["Details"], red_mat, "tail_light", rotation=(math.pi / 2, 0, 0), bevel=0.02)
for index, x in enumerate((-2.75, -1.8, -0.85)):
    cylinder(f"Tank_Exhaust_{index:02d}", (x, 1.25, 3.45), 0.18, 0.48, collections["Details"], metal_mat, "exhaust", bevel=0.03)
for index, y in enumerate((-0.7, 0.7)):
    cylinder(f"Tank_Antenna_{index:02d}", (-0.65, y, 5.9), 0.025, 2.1, collections["Details"], metal_mat, "antenna", bevel=0.005)

# Presentation-only ground, camera and lights.
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
ground = bpy.context.object
ground.name = "Presentation_Ground"
ground.data.materials.append(material("Ground", (0.025, 0.035, 0.025), 0.0, 0.95))
for current in list(ground.users_collection):
    current.objects.unlink(ground)
collections["Presentation"].objects.link(ground)

def point_camera(camera, target):
    direction = Vector(target) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

bpy.ops.object.camera_add(location=(13, -15, 10))
camera = bpy.context.object
camera.name = "Presentation_Camera"
point_camera(camera, (0, 0, 2.4))
scene.camera = camera
for current in list(camera.users_collection):
    current.objects.unlink(camera)
collections["Presentation"].objects.link(camera)

bpy.ops.object.light_add(type="AREA", location=(4, -6, 13))
key = bpy.context.object
key.name = "Presentation_Key_Light"
key.data.energy = 1400
key.data.shape = "DISK"
key.data.size = 7
point_camera(key, (0, 0, 2))
for current in list(key.users_collection):
    current.objects.unlink(key)
collections["Presentation"].objects.link(key)

bpy.ops.object.light_add(type="AREA", location=(-7, 4, 7))
fill = bpy.context.object
fill.name = "Presentation_Fill_Light"
fill.data.energy = 900
fill.data.size = 6
point_camera(fill, (0, 0, 2))
for current in list(fill.users_collection):
    current.objects.unlink(fill)
collections["Presentation"].objects.link(fill)

scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 900
scene.render.resolution_y = 650
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = OUTPUT_RENDER
scene.world.color = (0.008, 0.012, 0.018)
bpy.ops.wm.save_as_mainfile(filepath=OUTPUT_BLEND)
bpy.ops.render.render(write_still=True)

result = {
    "status": "succeeded",
    "blend_file": OUTPUT_BLEND,
    "render_file": OUTPUT_RENDER,
    "part_count": len(parts),
    "part_names": sorted(obj.name for obj in parts),
    "collections": sorted(collections),
    "separated": True,
}

