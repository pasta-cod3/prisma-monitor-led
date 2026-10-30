#!/usr/bin/env python3
import math
import sys

import bpy
from mathutils import Vector


argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None, n=1):
    if name in argv:
        i = argv.index(name)
        vals = argv[i + 1:i + 1 + n]
        return vals[0] if n == 1 else vals
    return default


FRAMES = int(arg("--frames", 72))
SAMPLES = int(arg("--samples", 192))
RES = [int(v) for v in (arg("--res", ["1280", "720"], 2))]
STILL_ONLY = "--still-only" in argv
OUT = arg("--out", "blender/out")
DEVICE = arg("--device", "GPU")


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights):
        for b in list(block):
            block.remove(b)


def pbr(name, base, metallic=0.0, roughness=0.5, emission=None, emission_strength=0.0, clearcoat=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*base, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = clearcoat
    if emission is not None:
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emission, 1)
            bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


def cube(name, size, loc, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = Vector(size) / 2
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(mat)
    bevel = o.modifiers.new("Bevel", "BEVEL")
    bevel.width = min(size) * 0.03
    bevel.segments = 3
    return o


clear_scene()
scene = bpy.context.scene
W, H = 10.0, 5.6

bezel_mat = pbr("Bezel", (0.09, 0.1, 0.12), metallic=0.9, roughness=0.32, clearcoat=0.4)
screen_mat = pbr("Screen", (0.01, 0.01, 0.012), metallic=0.0, roughness=0.06, clearcoat=1.0)
stand_mat = pbr("Stand", (0.06, 0.07, 0.09), metallic=0.85, roughness=0.3)
led_mat = pbr("LED", (0, 0, 0), emission=(1, 1, 1), emission_strength=6.0, roughness=0.5)

parts = []
parts.append(cube("Bezel", (W + 0.4, H + 0.4, 0.35), (0, 0, 0), bezel_mat))
screen = cube("Screen", (W - 0.4, H - 0.4, 0.1), (0, 0, 0.18), screen_mat)
parts.append(screen)
parts.append(cube("Neck", (0.7, 2.8, 0.5), (0, -H / 2 - 1.4, -0.4), stand_mat))
bpy.ops.mesh.primitive_cylinder_add(radius=2.7, depth=0.25, location=(0, -H / 2 - 2.8, -0.2))
base = bpy.context.active_object
base.name = "Base"
base.scale.y = 0.7
base.rotation_euler.x = math.pi / 2
base.data.materials.append(stand_mat)
parts.append(base)

led_objs = []
span = (W - 1.4) / 5
for i in range(5):
    cx = -W / 2 + 0.7 + span * (i + 0.5)
    o = cube("LED_%d" % i, (span - 0.25, 0.22, 0.2), (cx, -H / 2 - 0.02, 0.22), led_mat)
    led_objs.append(o)
    parts.append(o)

bpy.ops.object.select_all(action="DESELECT")
for o in parts:
    o.select_set(True)
pivot = bpy.data.objects.new("Pivot", None)
bpy.context.collection.objects.link(pivot)
pivot.location = (0, 0, 0)
for o in parts:
    o.parent = pivot


world = bpy.data.worlds.new("Studio")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.02, 0.025, 0.035, 1)
bg.inputs["Strength"].default_value = 0.6


def area_light(name, loc, rot, size, power, color=(1, 1, 1)):
    light = bpy.data.lights.new(name, "AREA")
    light.energy = power
    light.size = size
    light.color = color
    o = bpy.data.objects.new(name, light)
    o.location = loc
    o.rotation_euler = rot
    bpy.context.collection.objects.link(o)


area_light("Key", (8, 6, 12), (math.radians(-35), math.radians(28), 0), 8, 1800)
area_light("Fill", (-10, 2, 8), (math.radians(-20), math.radians(-40), 0), 10, 700, (0.8, 0.85, 1.0))
area_light("Rim", (0, 4, -10), (math.radians(60), 0, math.radians(180)), 8, 1200, (0.7, 0.8, 1.0))

bpy.ops.mesh.primitive_plane_add(size=120, location=(0, -H / 2 - 3.0, -0.2))
floor = bpy.context.active_object
floor.rotation_euler.x = math.pi / 2
floor.data.materials.append(pbr("Floor", (0.015, 0.018, 0.022), metallic=0.3, roughness=0.18))


bpy.ops.object.camera_add(location=(0, 0.3, 26), rotation=(math.radians(88), 0, 0))
cam = bpy.context.active_object
cam.data.lens = 70
scene.camera = cam
bpy.ops.object.empty_add(location=(0, -0.3, 0))
target = bpy.context.active_object
con = cam.constraints.new("TRACK_TO")
con.target = target
con.track_axis = "TRACK_NEGATIVE_Z"
con.up_axis = "UP_Y"


scene.render.engine = "CYCLES"
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    if DEVICE.upper() == "GPU":
        for api in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
            try:
                prefs.compute_device_type = api
                prefs.get_devices()
                if any(d.type != "CPU" for d in prefs.devices):
                    scene.cycles.device = "GPU"
                    for d in prefs.devices:
                        d.use = True
                    break
            except Exception:
                continue
except Exception:
    pass

scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = RES
scene.render.film_transparent = True
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.view_settings.view_transform = "AGX" if "AgX" in [v.name for v in bpy.data.scenes[0].view_settings.bl_rna.properties["view_transform"].enum_items] else "Filmic"

scene.render.filepath = "%s/still.png" % OUT
bpy.ops.render.render(write_still=True)
print("Fermo immagine salvato in %s/still.png" % OUT)

if not STILL_ONLY:
    for f in range(FRAMES):
        pivot.rotation_euler.z = 2 * math.pi * f / FRAMES
        scene.render.filepath = "%s/turntable/frame_%03d.png" % (OUT, f)
        bpy.ops.render.render(write_still=True)
        print("Fotogramma %d/%d" % (f + 1, FRAMES))
    print("Sequenza turntable salvata in %s/turntable/" % OUT)
