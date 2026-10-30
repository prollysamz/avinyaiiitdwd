"""Run: blender --background --python blender/ocean.py

Authors a real Ocean modifier, samples its evaluated displacement into a seamless
normal map for the live renderer, and saves the editable ocean.blend source.
No Cycles shader is exported: glTF cannot preserve the Ocean modifier or water BSDF.
"""
import os
import bpy
import numpy as np
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "public", "textures", "water")
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
N, SIZE = 512, 64.0
axis = np.linspace(-SIZE / 2, SIZE / 2, N + 1)
x, y = np.meshgrid(axis, axis)
vertices = np.column_stack((x.ravel(), y.ravel(), np.zeros(x.size)))
i = np.arange(N)[:, None] * (N + 1) + np.arange(N)[None, :]
faces = np.stack((i, i + 1, i + N + 2, i + N + 1), axis=-1).reshape(-1, 4)
mesh = bpy.data.meshes.new("Ocean sampling grid")
mesh.from_pydata(vertices.tolist(), [], faces.tolist())
mesh.update()
ocean = bpy.data.objects.new("Ocean · spectral wind waves", mesh)
scene.collection.objects.link(ocean)
mod = ocean.modifiers.new("Ocean · 64m wind spectrum", "OCEAN")
mod.geometry_mode = "DISPLACE"
mod.resolution = 9
mod.viewport_resolution = 9
mod.spatial_size = int(SIZE)
mod.size = 1
mod.wave_scale = 0.48
mod.choppiness = 0.65
mod.wind_velocity = 9
mod.wave_scale_min = 0.04
mod.wave_alignment = 0.35
mod.wave_direction = 0.55
mod.damping = 0.55
mod.random_seed = 23
mod.time = 1.7
evaluated = ocean.evaluated_get(bpy.context.evaluated_depsgraph_get())
sample = evaluated.to_mesh()
co = np.empty(len(sample.vertices) * 3, dtype=np.float32)
sample.vertices.foreach_get("co", co)
height = co.reshape(N + 1, N + 1, 3)[:N, :N, 2]
# Central differences keep the map exactly periodic across its texture borders.
dx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) / (2 * SIZE / N)
dy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) / (2 * SIZE / N)
normal = np.stack((-dx, -dy, np.ones_like(dx)), axis=-1)
normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
rgba = np.ones((N, N, 4), dtype=np.float32)
rgba[:, :, :3] = normal * 0.5 + 0.5
img = bpy.data.images.new("Ocean spectral normal · linear", N, N, alpha=False)
img.colorspace_settings.name = "Non-Color"
img.pixels.foreach_set(rgba.ravel())
img.filepath_raw = os.path.join(OUT, "ocean-normal.png")
img.file_format = "PNG"
img.save()
img.pack()
evaluated.to_mesh_clear()
for poly in mesh.polygons:
    poly.use_smooth = True
mat = bpy.data.materials.new("Sea water · IOR 1.333")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = (0.015, 0.10, 0.12, 1)
bsdf.inputs["Roughness"].default_value = 0.12
bsdf.inputs["IOR"].default_value = 1.333
bsdf.inputs["Transmission Weight"].default_value = 1.0
absorb = mat.node_tree.nodes.new("ShaderNodeVolumeAbsorption")
absorb.inputs["Color"].default_value = (0.12, 0.55, 0.62, 1)
absorb.inputs["Density"].default_value = 0.08
mat.node_tree.links.new(absorb.outputs[0], mat.node_tree.nodes.get("Material Output").inputs["Volume"])
mesh.materials.append(mat)
world = bpy.data.worlds.new("Golden hour ocean")
world.use_nodes = True
scene.world = world
sky = world.node_tree.nodes.new("ShaderNodeTexSky")
sky.sky_type = "MULTIPLE_SCATTERING"
sky.sun_elevation = 0.24
sky.sun_rotation = 3.8
world.node_tree.links.new(sky.outputs[0], world.node_tree.nodes["Background"].inputs[0])
bpy.ops.object.camera_add(location=(8, -20, 3.5))
cam = bpy.context.object
cam.rotation_euler = (Vector((0, 8, 0)) - cam.location).to_track_quat("-Z", "Y").to_euler()
cam.data.lens = 42
scene.camera = cam
scene.render.engine = "CYCLES"
scene.cycles.samples = 32
scene.cycles.use_denoising = True
scene.view_settings.view_transform = "AgX"
bpy.context.view_layer.objects.active = ocean
bpy.ops.object.select_all(action="DESELECT")
ocean.select_set(True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "blender", "ocean.blend"))
print(f"OCEAN_READY: {img.filepath_raw}; height range {height.min():.3f}..{height.max():.3f}m")
