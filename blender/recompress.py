"""
Re-encode a downloaded static glb: textures capped at MAX px, WebP, meshopt geometry.
  blender --background --python blender/recompress.py -- in.glb out.glb [max_px]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, lib

A = lib.args()
src, dst = A[0], A[1]
MAX = int(A[2]) if len(A) > 2 else 1024
lib.reset()
bpy.ops.import_scene.gltf(filepath=src)
for im in bpy.data.images:
    w, h = im.size
    if max(w, h) > MAX and w and h:
        s = MAX / max(w, h)
        im.scale(max(1, int(w * s)), max(1, int(h * s)))
        print("scaled", im.name, (w, h), "->", tuple(im.size))
lib.export_glb(dst, morph=False)
