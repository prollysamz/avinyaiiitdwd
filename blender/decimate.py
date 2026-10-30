"""
Reduce the triangle count of named meshes in a shipped .glb, keeping everything else (morph targets,
node names, materials). Baked normal maps carry the fine detail, so a lighter mesh reads the same.

  blender --background --python blender/decimate.py -- in.glb out.glb Mesh_Name=ratio [Mesh_Name=ratio ...]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
import lib  # noqa: E402

A = lib.args()
src, dst, targets = A[0], A[1], dict((k, float(v)) for k, v in (a.split("=") for a in A[2:]))
lib.reset()
bpy.ops.import_scene.gltf(filepath=src)
for o in bpy.data.objects:
    if o.type == "MESH" and o.name in targets:
        before = len(o.data.polygons)
        m = o.modifiers.new("Decimate", "DECIMATE")
        m.decimate_type = "COLLAPSE"
        m.ratio = targets[o.name]
        m.use_collapse_triangulate = True
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier=m.name)
        print("DECIMATED", o.name, before, "->", len(o.data.polygons))
lib.export_glb(dst, morph=True)
