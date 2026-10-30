"""
2D renders of the three island models, for the About section.

  blender --background --python blender/vignettes.py -- <outpost|pandemonium|carnival> <out.png>

Each island is its real exported model sitting on a floating rock chunk, lit for its chapter,
rendered on a transparent background.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bmesh  # noqa: E402
import bpy  # noqa: E402
import lib  # noqa: E402
from lib import Mat, hexcol  # noqa: E402
from mathutils import Vector  # noqa: E402

A = lib.args()
ISLAND, OUT = A[0], A[1]
MODELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "models")

lib.reset()
sc = bpy.context.scene
rnd = random.Random(4)


def link(o):
    sc.collection.objects.link(o)
    return o


def rock_chunk(radius, depth, top_mat, rock_mat, rim=0.35):
    """Floating island: flat top, jagged tapering underside."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=5, radius=1.0)
    for v in list(bm.verts):
        if v.co.z > 0.0:
            bm.verts.remove(v)
    top = []
    for v in bm.verts:
        a = math.atan2(v.co.y, v.co.x)
        n = math.sin(a * 5 + v.co.z * 7) * 0.5 + math.sin(a * 11 - v.co.z * 13) * 0.5
        s = 1 + 0.07 * n
        z = v.co.z
        v.co.x *= radius * s
        v.co.y *= radius * s
        v.co.z = z * depth * (1 + 0.2 * math.sin(a * 3 + 1.2))
        # taper the lower half toward a point and roughen it
        t = -z
        v.co.x *= (1 - 0.55 * t ** 1.4)
        v.co.y *= (1 - 0.55 * t ** 1.4)
        v.co += Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * 0.07 * t * radius
    # cap
    rim_verts = [v for v in bm.verts if abs(v.co.z) < 1e-4]
    rim_verts.sort(key=lambda v: math.atan2(v.co.y, v.co.x))
    for v in bm.verts:
        v.co.z = min(v.co.z, 0.0)
    try:
        bm.faces.new(rim_verts)
    except ValueError:
        pass
    me = bpy.data.meshes.new("Chunk")
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    # rock on the sides, ground material on the cap (cap = faces with normal +Z)
    me.materials.append(rock_mat.m)
    me.materials.append(top_mat.m)
    for p in me.polygons:
        p.material_index = 1 if p.normal.z > 0.9 and p.center.z > -0.05 else 0
    o = link(bpy.data.objects.new("Chunk", me))
    return o


def rock_material():
    m = Mat("ChunkRock")
    n = m.noise(m.mapping(scale=(0.6, 0.6, 1.8)).outputs[0], 2.5, 6, 0.6, 0.7)
    f = m.noise(m.mapping(scale=(1, 1, 1)).outputs[0], 18.0, 6, 0.6, 0.3)
    col = m.ramp(m.math("ADD", m.math("MULTIPLY", n, 0.7), m.math("MULTIPLY", f, 0.3)), [(0.2, "#2c211b"), (0.55, "#4d3b2e"), (0.9, "#7b6044")]).outputs["Color"]
    m.set(**{"Base Color": col, "Roughness": 0.92})
    bp = m.node("ShaderNodeBump"); bp.inputs["Strength"].default_value = 1.0; bp.inputs["Distance"].default_value = 0.08
    m.link(f, bp.inputs["Height"]); m.link(bp.outputs["Normal"], m.bsdf.inputs["Normal"])
    return m


def ground_material(lo, hi):
    m = Mat("Ground")
    n = m.noise(m.mapping(scale=(1, 1, 1)).outputs[0], 3.0, 6, 0.6, 0.5)
    f = m.noise(m.mapping(scale=(1, 1, 1)).outputs[0], 40.0, 4, 0.5)
    m.set(**{"Base Color": m.mix(m.math("ADD", m.math("MULTIPLY", n, 0.7), m.math("MULTIPLY", f, 0.3)), hexcol(lo), hexcol(hi)), "Roughness": 0.95})
    bp = m.node("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.5; bp.inputs["Distance"].default_value = 0.05
    m.link(f, bp.inputs["Height"]); m.link(bp.outputs["Normal"], m.bsdf.inputs["Normal"])
    return m


def add_windows(mat_, hue, strength=3.0):
    """Lit-window emission for the city towers (the app applies this as a texture at runtime)."""
    nt = mat_.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    N = nt.nodes
    geo = N.new("ShaderNodeNewGeometry")
    sepp, sepn = N.new("ShaderNodeSeparateXYZ"), N.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sepp.inputs["Vector"]); nt.links.new(geo.outputs["Normal"], sepn.inputs["Vector"])

    def M(op, a=None, b=None):
        n = N.new("ShaderNodeMath"); n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                nt.links.new(v, n.inputs[i])
        return n.outputs[0]

    on_x = M("GREATER_THAN", M("ABSOLUTE", sepn.outputs["X"]), M("ABSOLUTE", sepn.outputs["Y"]))
    horiz = N.new("ShaderNodeMix"); horiz.data_type = "FLOAT"
    nt.links.new(on_x, horiz.inputs[0]); nt.links.new(sepp.outputs["X"], horiz.inputs[2]); nt.links.new(sepp.outputs["Y"], horiz.inputs[3])
    cu = M("MULTIPLY", horiz.outputs[0], 3.4)
    cv = M("MULTIPLY", sepp.outputs["Z"], 2.7)
    cell = N.new("ShaderNodeCombineXYZ")
    nt.links.new(M("FLOOR", cu), cell.inputs["X"]); nt.links.new(M("FLOOR", cv), cell.inputs["Y"])
    nt.links.new(M("ADD", M("FLOOR", M("MULTIPLY", sepp.outputs["X"], 0.37)), M("MULTIPLY", M("FLOOR", M("MULTIPLY", sepp.outputs["Y"], 0.41)), 7.0)), cell.inputs["Z"])
    wn = N.new("ShaderNodeTexWhiteNoise"); wn.noise_dimensions = "3D"
    nt.links.new(cell.outputs["Vector"], wn.inputs["Vector"])
    lit = M("GREATER_THAN", wn.outputs["Value"], 0.42)
    fu, fv = M("FRACT", cu), M("FRACT", cv)
    rect = M("MULTIPLY", M("MULTIPLY", M("GREATER_THAN", fu, 0.2), M("LESS_THAN", fu, 0.8)), M("MULTIPLY", M("GREATER_THAN", fv, 0.25), M("LESS_THAN", fv, 0.75)))
    mask = M("MULTIPLY", M("MULTIPLY", lit, rect), M("GREATER_THAN", M("SUBTRACT", 1.0, M("ABSOLUTE", sepn.outputs["Z"])), 0.5))
    bright = M("MULTIPLY", mask, M("ADD", 0.5, M("MULTIPLY", wn.outputs["Value"], 0.9)))
    em = N.new("ShaderNodeMix"); em.data_type = "RGBA"
    nt.links.new(bright, em.inputs[0]); em.inputs[6].default_value = (0, 0, 0, 1); em.inputs[7].default_value = hexcol(hue)
    nt.links.new(em.outputs[2], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = strength


def striped(name, a, b, n=14):
    m = Mat(name)
    g = m.node("ShaderNodeTexGradient", gradient_type="RADIAL")
    m.link(m.mapping(scale=(1, 1, 1)).outputs[0], g.inputs["Vector"])
    stripe = m.math("LESS_THAN", m.math("FRACT", m.math("MULTIPLY", g.outputs["Fac"], n)), 0.5)
    m.set(**{"Base Color": m.mix(stripe, hexcol(a), hexcol(b)), "Roughness": 0.7})
    return m


def import_model(fname):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(MODELS, fname))
    return [o for o in bpy.data.objects if o not in before]


def sun(color, strength, rot, energy_fill=None):
    d = bpy.data.lights.new("Sun", "SUN"); d.energy = strength; d.color = hexcol(color)[:3]; d.angle = math.radians(3)
    o = link(bpy.data.objects.new("Sun", d)); o.rotation_euler = tuple(math.radians(x) for x in rot)
    return o


def area(color, energy, loc, size=8):
    d = bpy.data.lights.new("Area", "AREA"); d.energy = energy; d.color = hexcol(color)[:3]; d.size = size
    o = link(bpy.data.objects.new("Area", d)); o.location = loc
    o.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return o


world = bpy.data.worlds.new("W"); sc.world = world; world.use_nodes = True
bg = world.node_tree.nodes["Background"]

if ISLAND == "outpost":
    objs = import_model("outpost.glb")
    link(bpy.data.objects.new("x", None)) if False else None
    chunk = rock_chunk(8.6, 6.0, ground_material("#b78a52", "#dcb77c"), rock_material())
    chunk.location = (0, 0, 2.0)  # the model's plinth sits at its own z = 0; sink it onto the chunk top
    for o in objs:
        if o.parent is None:
            o.location = (0, 0, 2.0)
    bg.inputs[0].default_value = hexcol("#f0c890"); bg.inputs[1].default_value = 1.0
    sun("#ffd4a0", 4.6, (52, 0, -50))
    area("#ffd9b0", 3500, (16, -22, -4), 14)
    cam_loc, cam_t, lens = (21, -26, 14), (0, 0, 3.4), 40
elif ISLAND == "pandemonium":
    objs = import_model("city.glb")
    for o in objs:
        if o.type == "MESH":
            for slot in o.material_slots:
                nm = slot.material.name
                if nm.startswith("Tower_"):
                    add_windows(slot.material, ["#ff2ea6", "#27e6ff", "#9a5bff"][int(nm[-1])])
    chunk = rock_chunk(11.8, 7.5, ground_material("#171428", "#2a2243"), rock_material(), rim=0.4)
    chunk.location = (0, 0, 0.0)
    for o in objs:
        if o.parent is None:
            o.location = (0, 0, 0.05)
    bg.inputs[0].default_value = hexcol("#5a1e7a"); bg.inputs[1].default_value = 0.9
    sun("#c8a0ff", 1.6, (40, 0, -40))
    area("#ff2ea6", 9000, (-18, -14, 8), 14)
    area("#27e6ff", 7000, (18, -12, 6), 14)
    cam_loc, cam_t, lens = (29, -37, 17), (0, 0, 4.2), 40
else:
    objs = import_model("wheel.glb")
    chunk = rock_chunk(9.4, 6.0, ground_material("#6a8a3a", "#9aae52"), rock_material())
    chunk.location = (0, 0, 0.9)
    for o in objs:
        if o.parent is None:
            o.location = (0, 0, 0.9)
    red, cream = striped("Tent", "#d4362d", "#f3e7cf"), striped("TentB", "#f0a52a", "#f3e7cf")
    for (x, y, s, m_) in ((-5.0, -3.2, 1.0, red), (4.8, -4.3, 0.75, cream), (-4.4, 3.6, 0.7, striped("TentC", "#2a9db4", "#f3e7cf"))):
        bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, segments=28, radius1=2.5 * s, radius2=2.5 * s, depth=1.5 * s)
        for v in bm.verts: v.co.z += 0.75 * s
        me = bpy.data.meshes.new("TentWall"); bm.to_mesh(me); bm.free(); me.materials.append(m_.m)
        w = link(bpy.data.objects.new("TentWall", me)); w.location = (x, y, 0.9)
        bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, segments=28, radius1=2.7 * s, radius2=0.0, depth=2.3 * s)
        for v in bm.verts: v.co.z += 1.15 * s
        me = bpy.data.meshes.new("TentRoof"); bm.to_mesh(me); bm.free(); me.materials.append(m_.m)
        r = link(bpy.data.objects.new("TentRoof", me)); r.location = (x, y, 0.9 + 1.5 * s)
        for p in me.polygons: p.use_smooth = True
    # string lights between the tents
    for (a, b) in (((-5.0, -3.2, 3.2), (-0.8, -4.2, 4.0)), ((-0.8, -4.2, 4.0), (4.8, -4.3, 2.6))):
        for i in range(1, 12):
            t = i / 12
            p = Vector(a).lerp(Vector(b), t); p.z -= math.sin(math.pi * t) * 0.7
            bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=0.09)
            me = bpy.data.meshes.new("Bulb"); bm.to_mesh(me); bm.free()
            lm = Mat("Bulb"); lm.set(**{"Base Color": "#1a1208", "Emission Color": "#ffc473", "Emission Strength": 8.0}); me.materials.append(lm.m)
            bo = link(bpy.data.objects.new("Bulb", me)); bo.location = (p.x, p.y, p.z + 0.9)
    bg.inputs[0].default_value = hexcol("#ffb36a"); bg.inputs[1].default_value = 1.0
    sun("#ffb070", 3.8, (60, 0, -58))
    area("#ffc890", 3000, (14, -20, -3), 12)
    area("#ffd08a", 5000, (-14, -16, 10), 10)
    cam_loc, cam_t, lens = (23, -32, 13.5), (0, 0, 3.4), 38

cam_d = bpy.data.cameras.new("Cam"); cam_d.lens = lens
cam = link(bpy.data.objects.new("Cam", cam_d)); cam.location = cam_loc
cam.rotation_euler = (Vector(cam_t) - Vector(cam_loc)).to_track_quat("-Z", "Y").to_euler()
sc.camera = cam
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 96; sc.cycles.use_denoising = True
sc.render.film_transparent = True
sc.render.resolution_x, sc.render.resolution_y = 1500, 1100
sc.view_settings.view_transform = "AgX"; sc.view_settings.exposure = -0.2
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
sc.render.filepath = os.path.abspath(OUT)
bpy.ops.render.render(write_still=True)
print("RENDERED", OUT)
