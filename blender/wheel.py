"""
Carnival Ferris wheel.

  blender --background --python blender/wheel.py -- public/models/wheel.glb blender/wheel.blend

Wheel axis is Blender +Y (glTF Z); the wheel plane is X–Z; origin = ground centre under the hub.
Nodes: Wheel_Frame (static), Wheel_Rotor (spins), Cab0…Cab11 (children of the rotor, counter-rotated by the app).
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bmesh  # noqa: E402
import bpy  # noqa: E402
import lib  # noqa: E402
from lib import Mat, Scene, hexcol  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

A = lib.args()
OUT_GLB = A[0] if A else "wheel.glb"
OUT_BLEND = A[1] if len(A) > 1 else ""
FAST = "--fast" in sys.argv

lib.reset()
S = Scene("Wheel")
R, HUB, DEPTH, N_CAB = 6.0, 7.6, 0.62, 12


# ================================================================ materials
def steel_paint(name, color, wear="#6a3b22", rough=0.5, metallic=0.25):
    """Painted steel: chipped paint reveals rust at edges (noise-driven), subtle brush streaks."""
    m = Mat(name)
    n_big = m.noise(m.mapping(scale=(2, 2, 2)).outputs[0], 3.0, 5, 0.6, 0.4)
    n_fine = m.noise(m.mapping(scale=(14, 14, 14)).outputs[0], 14.0, 6, 0.6, 0.3)
    chip = m.math("GREATER_THAN", m.math("ADD", m.math("MULTIPLY", n_big, 0.5), m.math("MULTIPLY", n_fine, 0.5)), 0.68)
    col = m.mix(m.math("MULTIPLY", n_big, 0.18), hexcol(color), hexcol("#7c6c58"))
    col = m.mix(m.math("MULTIPLY", chip, 0.85), col, hexcol(wear))
    m.set(**{"Base Color": col, "Metallic": metallic})
    r = m.mix(chip, (rough, rough, rough, 1), (0.85, 0.85, 0.85, 1))
    m.link(r, m.bsdf.inputs["Roughness"])
    bp = m.node("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.18; bp.inputs["Distance"].default_value = 0.004
    m.link(n_fine, bp.inputs["Height"]); m.link(bp.outputs["Normal"], m.bsdf.inputs["Normal"])
    return m


def metal(name, color, rough, tarnish="#4b3a1c"):
    m = Mat(name)
    n = m.noise(m.mapping(scale=(14, 14, 14)).outputs[0], 7.0, 5, 0.6, 0.5)
    m.set(**{"Base Color": m.mix(m.math("MULTIPLY", n, 0.9), hexcol(color), hexcol(tarnish)), "Metallic": 1.0})
    r = m.ramp(n, [(0, (rough - 0.1,) * 3 + (1,)), (1, (rough + 0.2,) * 3 + (1,))])
    m.link(r.outputs["Color"], m.bsdf.inputs["Roughness"])
    return m


def wood(name, ramp):
    m = Mat(name)
    mp = m.mapping(scale=(2, 40, 2))
    n = m.noise(mp.outputs[0], 6.0, 5, 0.6, 0.8)
    f = m.noise(m.mapping(scale=(30, 3, 30)).outputs[0], 40.0, 4, 0.5)
    m.set(**{"Base Color": m.ramp(m.math("ADD", m.math("MULTIPLY", n, 0.6), m.math("MULTIPLY", f, 0.4)), [(0.15, ramp[0]), (0.5, ramp[1]), (0.85, ramp[2])]).outputs["Color"], "Roughness": 0.72})
    bp = m.node("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.3; bp.inputs["Distance"].default_value = 0.01
    m.link(f, bp.inputs["Height"]); m.link(bp.outputs["Normal"], m.bsdf.inputs["Normal"])
    return m


def lamp(name, color, strength):
    m = Mat(name)
    m.set(**{"Base Color": "#1a1208", "Roughness": 0.3, "Emission Color": color, "Emission Strength": strength})
    return m


def glass(name):
    m = Mat(name)
    m.set(**{"Base Color": "#1c262c", "Roughness": 0.05, "Emission Color": "#ffc27a", "Emission Strength": 0.9})
    return m


STEEL = steel_paint("SteelCream", "#bdbbb0", rough=0.4, metallic=0.42)
STEEL_R = steel_paint("SteelRed", "#934c42", wear="#4a2018", rough=0.45)
FRAME = steel_paint("SteelFrame", "#d9cfb6", rough=0.55)
BRASS = metal("Brass", "#e0b860", 0.3)
IRON = metal("Iron", "#2d2a27", 0.5, "#171614")
WOOD = wood("Planks", ["#5c3b22", "#85583a", "#a27650"])
LAMP_A, LAMP_B = lamp("LampA", "#ffc25a", 5.0), lamp("LampB", "#ff7a4a", 5.0)
GLASS = glass("Glass")


def tube(name, a, b, r, mat_, sink=None, seg=8):
    a, b = Vector(a), Vector(b)
    d = b - a
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=d.length)
    q = Vector((0, 0, 1)).rotation_difference(d.normalized())
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=q.to_matrix())
    return S.mesh(name, bm, mat_, loc=tuple((a + b) / 2), smooth=True)


# ================================================================ static frame
frame = []


def F(o):
    frame.append(o)
    return o


for sz in (-1, 1):
    top = (0, sz * (DEPTH + 0.55), HUB)
    feet = [(-3.8, sz * 2.0, 0.0), (3.8, sz * 2.0, 0.0)]
    for fx in feet:
        F(tube(f"Leg{sz}{fx[0]}", fx, top, 0.13, FRAME, seg=10))
    for f in (0.2, 0.42, 0.64):
        p0 = Vector(feet[0]).lerp(Vector(top), f); p1 = Vector(feet[1]).lerp(Vector(top), f)
        F(tube(f"Cross{sz}{f}", p0, p1, 0.05, FRAME, seg=6))
    for f0, f1 in ((0.0, 0.2), (0.2, 0.42), (0.42, 0.64)):
        a0, a1 = Vector(feet[0]).lerp(Vector(top), f0), Vector(feet[0]).lerp(Vector(top), f1)
        b0, b1 = Vector(feet[1]).lerp(Vector(top), f0), Vector(feet[1]).lerp(Vector(top), f1)
        F(tube(f"BraceA{sz}{f0}", a0, b1, 0.035, FRAME, seg=6))
        F(tube(f"BraceB{sz}{f0}", b0, a1, 0.035, FRAME, seg=6))
    for fx in feet:  # footing plates + bolts
        F(S.box(f"Foot{sz}{fx[0]}", (0.5, 0.5, 0.18), (fx[0], fx[1], 0.09), material=IRON, bevel=0.02))
    bear = S.box(f"Bearing{sz}", (0.6, 0.4, 0.6), top, material=IRON, bevel=0.04)
    F(bear)
    F(S.cyl(f"BearingCap{sz}", 0.27, 0.27, 0.12, (top[0], top[1] + sz * 0.22, top[2]), rot=(math.radians(90), 0, 0), material=BRASS, verts=24))
for sz in (-1, 1):
    F(S.box(f"Sill{sz}", (8.4, 0.4, 0.22), (0, sz * 2.0, 0.11), material=IRON, bevel=0.03))
F(S.cyl("Axle", 0.17, 0.17, 2 * (DEPTH + 0.95), (0, 0, HUB), rot=(math.radians(90), 0, 0), material=IRON, verts=20))
# boarding platform, steps, rail and a ticket booth
F(S.box("Platform", (3.0, 3.4, 0.42), (0, 0, 0.21), material=WOOD, bevel=0.015))
for i in range(4):
    F(S.box(f"Step{i}", (0.34, 1.6, 0.1), (1.75 + i * 0.3, 0, 0.35 - i * 0.1), material=WOOD, bevel=0.01))
for sy in (-1.65, 1.65):
    F(S.tube(f"PlatRail{sy}", [(-1.4, sy, 0.95), (1.4, sy, 0.95)], 0.025, BRASS))
    for x in (-1.4, 0, 1.4):
        F(S.cyl(f"PlatPost{sy}{x}", 0.025, 0.025, 0.55, (x, sy, 0.68), material=BRASS, verts=8))
F(S.box("Booth", (0.9, 0.9, 1.5), (-1.9, 1.9, 0.75), material=STEEL_R, bevel=0.03))
F(S.cyl("BoothRoof", 0.0, 0.85, 0.5, (-1.9, 1.9, 1.75), material=STEEL, verts=4, bevel=0.0) if False else S.cyl("BoothRoof", 0.85, 0.0, 0.5, (-1.9, 1.9, 1.75), material=STEEL, verts=4))
# painted name board above the platform
F(S.box("SignBoard", (2.0, 0.08, 0.5), (0, -2.15, 2.3), material=STEEL_R, bevel=0.015))
frame_obj = lib.join(frame, "Wheel_Frame")


# ================================================================ rotor
rotor_parts = []


def Rp(o):
    rotor_parts.append(o)
    return o


Ri, Rb = R - 0.45, R
for z in (-DEPTH, DEPTH):
    ring_o = S.torus(f"Rim{z}", R, 0.085, (0, z, HUB), rot=(math.radians(90), 0, 0), material=STEEL, major=120, minor=8)
    ring_i = S.torus(f"RimIn{z}", Ri, 0.05, (0, z, HUB), rot=(math.radians(90), 0, 0), material=STEEL, major=96, minor=6)
    Rp(ring_o); Rp(ring_i)
    n = 48
    for i in range(n):  # lattice between the rims
        a0, a1 = i / n * math.tau, (i + 1) / n * math.tau
        p = lambda a, rr: (math.cos(a) * rr, z, HUB + math.sin(a) * rr)
        Rp(tube(f"Lat{z}{i}a", p(a0, R), p(a1, Ri), 0.018, STEEL, seg=5))
        Rp(tube(f"Lat{z}{i}b", p(a0, Ri), p(a0, R), 0.018, STEEL, seg=5))
    for i in range(24):  # spokes to the hub, tangential like a bicycle wheel
        a = i / 24 * math.tau
        off = 0.5 if i % 2 else -0.5
        Rp(tube(f"Spoke{z}{i}", (math.cos(a + off) * 0.7, z * 0.95, HUB + math.sin(a + off) * 0.7), (math.cos(a) * Ri, z, HUB + math.sin(a) * Ri), 0.014, IRON, seg=5))
    Rp(S.cyl(f"Flange{z}", 0.85, 0.85, 0.09, (0, z * 0.95, HUB), rot=(math.radians(90), 0, 0), material=STEEL_R, verts=32))
for i in range(24):  # ties between the two rims
    a = i / 24 * math.tau
    Rp(tube(f"Tie{i}", (math.cos(a) * R, -DEPTH, HUB + math.sin(a) * R), (math.cos(a) * R, DEPTH, HUB + math.sin(a) * R), 0.03, STEEL, seg=6))
    a2 = (i + 0.5) / 24 * math.tau
    Rp(tube(f"TieIn{i}", (math.cos(a2) * Ri, -DEPTH, HUB + math.sin(a2) * Ri), (math.cos(a2) * Ri, DEPTH, HUB + math.sin(a2) * Ri), 0.02, STEEL, seg=5))
Rp(S.cyl("HubDrum", 0.45, 0.45, 2 * DEPTH + 0.1, (0, 0, HUB), rot=(math.radians(90), 0, 0), material=STEEL_R, verts=32))
for i in range(48):  # lamps along the outer rim, two alternating colours
    a = i / 48 * math.tau
    Rp(S.sphere(f"Lamp{i}", 0.085, (math.cos(a) * (R + 0.11), DEPTH + 0.02, HUB + math.sin(a) * (R + 0.11)), material=LAMP_A if i % 2 else LAMP_B, seg=10, rings=7))
    Rp(S.sphere(f"LampB{i}", 0.085, (math.cos(a) * (R + 0.11), -DEPTH - 0.02, HUB + math.sin(a) * (R + 0.11)), material=LAMP_B if i % 2 else LAMP_A, seg=10, rings=7))
for i in range(24):  # hanger brackets for the cabins
    a = i / 24 * math.tau
Rp_obj = lib.join(rotor_parts, "Wheel_Rotor")
Rp_obj.data.transform(Matrix.Translation((0, 0, -HUB)))   # pivot on the hub so the app can spin the node
Rp_obj.location = (0, 0, HUB)


# ================================================================ cabins
def cabin(name, body_hex):
    """Gondola with origin at the hanger pivot: tapered painted tub, lit glazed band, ribbed roof, bench inside."""
    paint = steel_paint(f"Paint_{name}", body_hex, rough=0.4, metallic=0.1)
    roof = steel_paint(f"Roof_{name}", "#f0e6cc", rough=0.45, metallic=0.1)
    parts = []

    def P(o):
        parts.append(o)
        return o

    P(S.cyl("Tub", 0.56, 0.42, 0.42, (0, 0, -1.2), material=paint, verts=14, bevel=0.01))
    P(S.cyl("TubBase", 0.43, 0.43, 0.04, (0, 0, -1.43), material=IRON, verts=14))
    P(S.cyl("Band", 0.55, 0.57, 0.3, (0, 0, -0.88), material=GLASS, verts=14, caps=False))
    for k in range(7):
        a = k / 7 * math.tau
        P(S.cyl(f"Pillar{k}", 0.022, 0.022, 0.32, (math.cos(a) * 0.565, math.sin(a) * 0.565, -0.88), material=paint, verts=6))
    P(S.cyl("Roof", 0.72, 0.0, 0.34, (0, 0, -0.55), material=roof, verts=14))
    P(S.torus("RoofRim", 0.7, 0.025, (0, 0, -0.72), material=BRASS, major=32, minor=6))
    P(S.sphere("Finial", 0.045, (0, 0, -0.37), material=BRASS, seg=10, rings=7))
    P(S.cyl("Hanger", 0.022, 0.022, 0.37, (0, 0, -0.185), material=IRON, verts=8))
    P(S.cyl("Axle", 0.03, 0.03, 1.4, (0, 0, 0.0), rot=(math.radians(90), 0, 0), material=BRASS, verts=10))
    P(S.box("Seat", (0.7, 0.28, 0.07), (0, 0, -1.08), material=WOOD, bevel=0.012))
    P(S.box("Rail", (0.92, 0.04, 0.04), (0, 0.42, -0.98), material=BRASS, bevel=0.005))
    o = lib.join(parts, name)
    return o


cab_defs = [("Cab_A", "#c8352f"), ("Cab_B", "#e8a92f"), ("Cab_C", "#2a8fa3"), ("Cab_D", "#efe3c6")]
cab_objs = [cabin(n, c) for n, c in cab_defs]

# ---- bake each static piece, then instantiate cabins around the rim
body_list = [frame_obj, Rp_obj] + cab_objs
if not FAST:
    lib.unwrap(frame_obj, margin=0.003); lib.bake_atlas(frame_obj, size=2048, ao=True, ao_strength=0.48, emissive=False, name="wheel_frame", samples=12)
    lib.unwrap(Rp_obj, margin=0.003); lib.bake_atlas(Rp_obj, size=2048, ao=True, ao_strength=0.48, emissive=True, name="wheel_rotor", samples=12)
    for o in cab_objs:
        lib.unwrap(o, margin=0.004); lib.bake_atlas(o, size=512, ao=True, emissive=True, name=o.name.lower(), samples=10)

for o in cab_objs:
    o.parent = None
    S.sc.collection.objects.unlink(o)
    S.link(o, Rp_obj)
    o.hide_render = False
originals = list(cab_objs)
for i in range(N_CAB):
    a = i / N_CAB * math.tau
    src = originals[i % 4]
    c = src.copy()
    c.name = f"Cab{i}"
    S.sc.collection.objects.link(c)
    c.parent = Rp_obj
    c.location = (math.cos(a) * R, 0, math.sin(a) * R)  # relative to the hub pivot
for o in originals:
    bpy.data.objects.remove(o, do_unlink=True)  # keep only the Cab0…11 instances (they share baked meshes)

frame_obj.parent = S.root
Rp_obj.parent = S.root
if OUT_BLEND:
    lib.save_blend(OUT_BLEND)
lib.export_glb(OUT_GLB, morph=False)
