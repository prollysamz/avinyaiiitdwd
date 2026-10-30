"""Bake seamless coastal PBR surfaces in Blender for terrain and buildings.

blender --background --python blender/coastal_materials.py
Textures are neutral so the terrain's geological vertex colours remain useful.
"""
import os
import sys
import math
import bpy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
from lib import Mat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "public", "textures", "coast")
os.makedirs(OUT, exist_ok=True)
lib.reset()
bpy.ops.mesh.primitive_plane_add(size=4)
plane = bpy.context.object
plane.name = "Coastal material swatch · four metres"

def seamless(m, scale, detail=4):
    # Tileable noise from UV coordinates on a 4D torus. Each edge samples the
    # same coordinates and derivatives as its opposite edge, including normals.
    sep = m.node("ShaderNodeSeparateXYZ")
    m.link(m.coord.outputs["UV"], sep.inputs[0])
    u = m.math("MULTIPLY", sep.outputs[0], math.tau)
    v = m.math("MULTIPLY", sep.outputs[1], math.tau)
    combine = m.node("ShaderNodeCombineXYZ")
    m.link(m.math("COSINE", u), combine.inputs[0])
    m.link(m.math("SINE", u), combine.inputs[1])
    m.link(m.math("COSINE", v), combine.inputs[2])
    n = m.node("ShaderNodeTexNoise", noise_dimensions="4D")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = 0.65
    m.link(combine.outputs[0], n.inputs["Vector"])
    m.link(m.math("SINE", v), n.inputs["W"])
    return n.outputs["Fac"]

def make_surface(kind):
    m = Mat(kind)
    large, fine, micro = seamless(m, 1.4), seamless(m, 16), seamless(m, 85, 2)
    if kind == "sand":
        # Fine grains and low, meandering ripples: no large dune ridges in a
        # four-metre texture tile.
        sep = m.node("ShaderNodeSeparateXYZ"); m.link(m.coord.outputs["UV"], sep.inputs[0])
        phase = m.math("ADD", m.math("MULTIPLY", sep.outputs[0], math.tau * 16), m.math("MULTIPLY", large, 3))
        ripple = m.math("MULTIPLY", m.math("SINE", phase), 0.025)
        height = m.math("ADD", m.math("MULTIPLY", fine, 0.15), ripple)
        color = m.ramp(m.math("ADD", m.math("MULTIPLY", fine, 0.35), m.math("MULTIPLY", large, 0.65)), [(0.12, "#c3beb0"), (0.5, "#ded9cc"), (0.88, "#eee9de")]).outputs[0]
        rough, depth = 0.9, 0.018
    elif kind == "rock":
        fissure = m.math("POWER", m.math("SUBTRACT", 1, m.math("ABSOLUTE", m.math("SUBTRACT", m.math("MULTIPLY", large, 2), 1))), 6)
        height = m.math("ADD", m.math("MULTIPLY", fine, 0.4), m.math("MULTIPLY", fissure, 0.25))
        joints = m.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
        joints.inputs["Scale"].default_value = 7
        # Periodic coordinates keep the fractured stone tile seamless.
        sep = m.node("ShaderNodeSeparateXYZ"); m.link(m.coord.outputs["UV"], sep.inputs[0])
        coords = m.node("ShaderNodeCombineXYZ")
        m.link(m.math("COSINE", m.math("MULTIPLY", sep.outputs[0], math.tau)), coords.inputs[0])
        m.link(m.math("SINE", m.math("MULTIPLY", sep.outputs[0], math.tau)), coords.inputs[1])
        m.link(m.math("COSINE", m.math("MULTIPLY", sep.outputs[1], math.tau)), coords.inputs[2])
        m.link(coords.outputs[0], joints.inputs["Vector"])
        cracks = m.math("MINIMUM", m.math("MULTIPLY", joints.outputs["Distance"], 14), 1)
        height = m.math("ADD", height, m.math("MULTIPLY", cracks, .3))
        color = m.ramp(large, [(0.15, "#8d8981"), (0.5, "#b8b5ad"), (0.85, "#d3d0c7")]).outputs[0]
        color = m.mix(m.math("MULTIPLY", fine, 0.12), color, lib.hexcol("#625f58"))
        color = m.mix(m.math("SUBTRACT", 1, cracks), color, lib.hexcol("#686259"))
        rough, depth = 0.86, 0.19
    elif kind == "ground":
        height = m.math("ADD", m.math("MULTIPLY", fine, 0.6), m.math("MULTIPLY", micro, 0.35))
        color = m.ramp(large, [(0.15, "#89877d"), (0.5, "#b6b4a8"), (0.85, "#d5d4c6")]).outputs[0]
        rough, depth = 0.96, 0.022
    else:
        height = m.math("ADD", m.math("MULTIPLY", fine, 0.18), m.math("MULTIPLY", micro, 0.15))
        color = m.ramp(large, [(0.15, "#8b8983"), (0.5, "#b5b3ad"), (0.85, "#d3d0c8")]).outputs[0]
        rough, depth = 0.76, 0.012
    m.set(**{"Base Color": color, "Roughness": m.math("ADD", rough - 0.09, m.math("MULTIPLY", fine, 0.16))})
    bump = m.node("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.75
    bump.inputs["Distance"].default_value = depth
    m.link(height, bump.inputs["Height"])
    m.link(bump.outputs["Normal"], m.bsdf.inputs["Normal"])
    return m

sources = []
for index, kind in enumerate(("sand", "rock", "ground", "concrete")):
    material = make_surface(kind)
    # Keep the original nodes on a separate swatch in the editable source.
    swatch = plane.copy(); swatch.data = plane.data.copy()
    bpy.context.scene.collection.objects.link(swatch)
    swatch.name = kind + " · procedural source"
    swatch.location.x = index * 4.5
    swatch.data.materials.clear(); swatch.data.materials.append(material.m.copy())
    swatch.hide_render = True
    plane.data.materials.clear(); plane.data.materials.append(material.m)
    lib._setup_cycles(8)
    for suffix, bake, srgb in (("color", "DIFFUSE", True), ("normal", "NORMAL", False), ("roughness", "ROUGHNESS", False)):
        image = lib._new_image(kind + "_" + suffix, 2048, srgb)
        lib._prep_slots(plane, image)
        if bake == "DIFFUSE":
            lib._bake(plane, bake, pass_filter={"COLOR"})
        elif bake == "NORMAL":
            lib._bake(plane, bake, normal_space="TANGENT")
        else:
            lib._bake(plane, bake)
        # Ship 1024px JPEGs: the surfaces tile every four metres, so 1024px is still ~4 mm a pixel,
        # and the full 2048px PNG set was ~50 MB of first-visit download.
        image.scale(1024, 1024)
        image.filepath_raw = os.path.join(OUT, kind + "-" + suffix + ".jpg")
        image.file_format = "JPEG"
        bpy.context.scene.render.image_settings.quality = 92 if suffix == "normal" else 84
        image.save()
        image.pack()
    print("COAST_BAKED", kind, flush=True)
bpy.data.objects.remove(plane, do_unlink=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "blender", "coastal-materials.blend"))
print("COAST_READY", flush=True)
