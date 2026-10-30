"""Make self-contained Blender previews from the actual exported assets.

The procedural construction sources remain boat.py/outpost.py/city.py/wheel.py.
These packed .blend files show exactly the geometry and PBR maps the browser uses.
"""
import os
import math
import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for kind, location, target in (
    ("boat", (6, -8, 3.7), (0, 0, 1.8)),
    ("outpost", (-11, -16, 9), (0, 0, 3.6)),
    ("city", (-22, -28, 14), (0, 0, 7)),
    ("wheel", (-17, -23, 12), (0, 0, 7)),
):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, "public", "models", kind + "-realistic.glb"))
    for image in bpy.data.images:
        if image.has_data:
            image.pack()
    scene = bpy.context.scene
    world = bpy.data.worlds.new("Coastal daylight")
    world.use_nodes = True
    scene.world = world
    sky = world.node_tree.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_elevation = math.radians(26)
    sky.sun_rotation = math.radians(215)
    world.node_tree.links.new(sky.outputs[0], world.node_tree.nodes["Background"].inputs[0])
    bpy.ops.object.camera_add(location=location)
    cam = bpy.context.object
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 44
    scene.camera = cam
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = -1.8
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "blender", kind + "-realistic.blend"))
    print("PACKED_SOURCE", kind, flush=True)
