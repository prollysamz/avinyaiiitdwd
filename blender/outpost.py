"""
Last Outpost citadel — a Dune-style desert fortress.

  blender --background --python blender/outpost.py -- public/models/outpost.glb blender/outpost.blend

Origin is the centre of the plinth at ground level (z = 0). Everything is one baked PBR atlas
(sandstone ashlar with dust, dark stone, metal, cloth, lit slits) → single draw call.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bmesh  # noqa: E402
import bpy  # noqa: E402
import lib  # noqa: E402
from lib import Mat, Scene, hexcol  # noqa: E402
from mathutils import Vector  # noqa: E402

A = lib.args()
OUT_GLB = A[0] if A else "outpost.glb"
OUT_BLEND = A[1] if len(A) > 1 else ""
FAST = "--fast" in sys.argv
random.seed(11)

lib.reset()
S = Scene("Outpost")


# ================================================================= materials
def stone_mat(name, ramp, dust=True, rough=0.88, brick=True, streaks=True):
    """Triplanar ashlar masonry + strata + rain streaks + wind-blown sand banked against the base."""
    m = Mat(name)
    geo = m.node("ShaderNodeNewGeometry")
    nsep = m.node("ShaderNodeSeparateXYZ")
    m.link(geo.outputs["Normal"], nsep.inputs["Vector"])
    nx, ny, nz = m.math("ABSOLUTE", nsep.outputs["X"]), m.math("ABSOLUTE", nsep.outputs["Y"]), nsep.outputs["Z"]
    on_x = m.math("GREATER_THAN", nx, ny)  # walls facing along X use the YZ plane

    def brick_node(rot_z):
        mp = m.mapping(scale=(1, 1, 1), rot=(0, 0, rot_z))
        b = m.node("ShaderNodeTexBrick")
        b.offset = 0.5
        b.inputs["Scale"].default_value = 1.0
        b.inputs["Mortar Size"].default_value = 0.012
        b.inputs["Mortar Smooth"].default_value = 0.1
        b.inputs["Brick Width"].default_value = 1.5
        b.inputs["Row Height"].default_value = 0.75
        b.inputs["Color1"].default_value = (1, 1, 1, 1)
        b.inputs["Color2"].default_value = (0.82, 0.82, 0.82, 1)
        b.inputs["Mortar"].default_value = (0, 0, 0, 1)
        sp = m.node("ShaderNodeSeparateXYZ")
        sw = m.node("ShaderNodeCombineXYZ")
        m.link(mp.outputs[0], sp.inputs["Vector"])
        m.link(sp.outputs["X"], sw.inputs["X"])
        m.link(sp.outputs["Z"], sw.inputs["Y"])
        m.link(sw.outputs["Vector"], b.inputs["Vector"])
        return b

    b0, b1 = brick_node(0.0), brick_node(math.radians(90))
    tone = m.mix(on_x, b0.outputs["Color"], b1.outputs["Color"])
    tone_v = m.node("ShaderNodeRGBToBW")
    m.link(tone, tone_v.inputs["Color"])
    groove = m.math("LESS_THAN", tone_v.outputs["Val"], 0.05)          # 1 inside mortar joints
    brick_tone = m.math("ADD", 0.86, m.math("MULTIPLY", tone_v.outputs["Val"], 0.18))

    mp = m.mapping(scale=(1, 1, 1))
    strata = m.noise(m.mapping(scale=(0.5, 0.5, 3.4)).outputs[0], 2.4, 5, 0.6, 0.7)
    grain = m.noise(mp.outputs[0], 36.0, 6, 0.6, 0.2)
    large = m.noise(m.mapping(scale=(0.25, 0.25, 0.25)).outputs[0], 1.2, 4, 0.5, 0.5)
    streak = m.noise(m.mapping(scale=(1.6, 1.6, 0.12)).outputs[0], 2.0, 5, 0.6, 0.9)
    base_f = m.math("ADD", m.math("ADD", m.math("MULTIPLY", strata, 0.45), m.math("MULTIPLY", large, 0.4)), m.math("MULTIPLY", grain, 0.18))
    base = m.ramp(base_f, ramp).outputs["Color"]
    col = m.mix(m.math("MULTIPLY", m.math("SUBTRACT", 1.0, brick_tone), 1.2), base, (0.1, 0.07, 0.04, 1)) if brick else base
    if streaks:
        col = m.mix(m.math("MULTIPLY", m.math("GREATER_THAN", streak, 0.56), 0.28), col, hexcol("#3d2c1e"))
    flake_n = m.noise(m.mapping(scale=(1, 1, 1)).outputs[0], 5.0, 6, 0.6, 0.6)
    flake = m.math("MULTIPLY", m.math("GREATER_THAN", flake_n, 0.64), 0.85)
    col = m.mix(flake, col, hexcol("#55341f"))
    col = m.mix(m.math("MULTIPLY", groove, 0.75), col, hexcol("#25170d"))
    gz = m.node("ShaderNodeSeparateXYZ")
    pos = m.node("ShaderNodeNewGeometry")
    m.link(pos.outputs["Position"], gz.inputs["Vector"])
    low = m.math("LESS_THAN", gz.outputs["Z"], m.math("ADD", 1.05, m.math("MULTIPLY", grain, 0.9)))
    col = m.mix(m.math("MULTIPLY", low, 0.7), col, hexcol("#c4975a"))
    if dust:
        up = m.math("MULTIPLY", m.math("GREATER_THAN", nz, 0.8), m.math("ADD", 0.15, m.math("MULTIPLY", grain, 1.0)))
        col = m.mix(m.math("MULTIPLY", up, 0.55), col, hexcol("#d3aa6c"))
    m.set(**{"Base Color": col})
    rough_c = m.mix(m.math("MULTIPLY", grain, 0.4), (rough, rough, rough, 1), (min(rough + 0.1, 1.0),) * 3 + (1,))
    m.link(rough_c, m.bsdf.inputs["Roughness"])
    h = m.math("SUBTRACT", m.math("MULTIPLY", grain, 0.5), m.math("MULTIPLY", groove, 0.9))
    bp = m.node("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.48; bp.inputs["Distance"].default_value = 0.014
    m.link(h, bp.inputs["Height"]); m.link(bp.outputs["Normal"], m.bsdf.inputs["Normal"])
    return m


def rock_mat(name):
    m = Mat(name)
    big = m.noise(m.mapping(scale=(0.7, 0.7, 1.1)).outputs[0], 2.2, 5, 0.6, 0.6)
    fine = m.noise(m.mapping(scale=(1, 1, 1)).outputs[0], 30.0, 6, 0.6, 0.2)
    crack = m.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
    crack.inputs["Scale"].default_value = 3.2
    m.link(m.mapping(scale=(1, 1, 1)).outputs[0], crack.inputs["Vector"])
    col = m.ramp(m.math("ADD", m.math("MULTIPLY", big, 0.6), m.math("MULTIPLY", fine, 0.3)), [(0.0, "#3f2f24"), (0.5, "#6e543d"), (1.0, "#a2825a")]).outputs["Color"]
    col = m.mix(m.math("MULTIPLY", m.math("LESS_THAN", crack.outputs["Distance"], 0.04), 0.8), col, hexcol("#1d150f"))
    geo = m.node("ShaderNodeNewGeometry")
    sep = m.node("ShaderNodeSeparateXYZ"); m.link(geo.outputs["Normal"], sep.inputs["Vector"])
    sand = m.math("MULTIPLY", m.math("GREATER_THAN", sep.outputs["Z"], 0.8), m.math("MULTIPLY", fine, 0.7))
    col = m.mix(sand, col, hexcol("#caa972"))
    m.set(**{"Base Color": col, "Roughness": 0.92})
    h = m.math("ADD", fine, m.math("MULTIPLY", crack.outputs["Distance"], 1.5))
    bp = m.node("ShaderNodeBump"); bp.inputs["Strength"].default_value = 1.2; bp.inputs["Distance"].default_value = 0.05
    m.link(h, bp.inputs["Height"]); m.link(bp.outputs["Normal"], m.bsdf.inputs["Normal"])
    return m


def sand_mat(name):
    m = Mat(name)
    mp = m.mapping(scale=(1, 1, 1))
    rip = m.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="X")
    rip.inputs["Scale"].default_value = 14; rip.inputs["Distortion"].default_value = 5; rip.inputs["Detail"].default_value = 2
    m.link(mp.outputs[0], rip.inputs["Vector"])
    fine = m.noise(mp.outputs[0], 50.0, 4, 0.5)
    col = m.mix(m.math("MULTIPLY", rip.outputs["Fac"], 0.5), hexcol("#c79a5e"), hexcol("#dcb77c"))
    m.set(**{"Base Color": col, "Roughness": 0.95})
    bp = m.node("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.7; bp.inputs["Distance"].default_value = 0.03
    m.link(m.math("ADD", rip.outputs["Fac"], m.math("MULTIPLY", fine, 0.2)), bp.inputs["Height"]); m.link(bp.outputs["Normal"], m.bsdf.inputs["Normal"])
    return m


def metal(name, color, rough=0.45, metallic=0.9, rust="#5a3a22"):
    m = Mat(name)
    n = m.noise(m.mapping(scale=(8, 8, 8)).outputs[0], 6.0, 5, 0.6, 0.5)
    col = m.mix(m.math("MULTIPLY", n, 0.8), hexcol(color), hexcol(rust))
    m.set(**{"Base Color": col, "Metallic": metallic})
    r = m.ramp(n, [(0, (rough - 0.1,) * 3 + (1,)), (1, (rough + 0.25,) * 3 + (1,))])
    m.link(r.outputs["Color"], m.bsdf.inputs["Roughness"])
    return m


def cloth(name, color):
    m = Mat(name)
    n = m.noise(m.mapping(scale=(60, 60, 60)).outputs[0], 40.0, 3, 0.5)
    w = m.noise(m.mapping(scale=(4, 4, 4)).outputs[0], 3.0, 4, 0.6, 1.0)
    m.set(**{"Base Color": m.mix(m.math("MULTIPLY", w, 0.6), hexcol(color), hexcol("#4a2a18")), "Roughness": 0.92})
    bp = m.node("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.6; bp.inputs["Distance"].default_value = 0.004
    m.link(n, bp.inputs["Height"]); m.link(bp.outputs["Normal"], m.bsdf.inputs["Normal"])
    return m


def glow(name, color, strength):
    m = Mat(name)
    m.set(**{"Base Color": "#1a1208", "Roughness": 0.4, "Emission Color": color, "Emission Strength": strength})
    return m


M = {
    "sand": stone_mat("Sandstone", [(0.0, "#776650"), (0.5, "#ac9577"), (1.0, "#d0b895")]),
    "dark": stone_mat("DarkStone", [(0.0, "#2e2119"), (0.5, "#4d3a2b"), (1.0, "#74583c")], dust=True, rough=0.9),
    "rock": rock_mat("Rock"),
    "drift": sand_mat("SandDrift"),
    "iron": metal("Iron", "#35312d", 0.5, 0.9),
    "steel": metal("Steel", "#a8a39a", 0.4, 1.0, rust="#6a5a48"),
    "panel": metal("SolarPanel", "#1d2a3d", 0.25, 0.4, rust="#0d1520"),
    "banner": cloth("Banner", "#a93a22"),
    "rope": cloth("RopeCloth", "#b8995f"),
    "slit": glow("Slit", "#ffd49a", 2.1),
}
static = []


def add(o):
    static.append(o)
    return o


# ================================================================= geometry
def taper_box(name, w, d, h, top=0.8, loc=(0, 0, 0), mat=None, rot=0.0, bevel=0.03):
    """Battered (sloped) masonry volume: footprint w×d at the base, scaled by `top` at the roof."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        up = v.co.z > 0
        s = top if up else 1.0
        v.co.x *= w * s; v.co.y *= d * s; v.co.z = (v.co.z + 0.5) * h
    o = S.mesh(name, bm, mat or M["sand"], loc=loc, smooth=False)
    o.rotation_euler = (0, 0, rot)
    S.modifier(o, "BEVEL", width=bevel, segments=2, limit_method="ANGLE", angle_limit=math.radians(35))
    return add(o)


def box(name, size, loc, rot=(0, 0, 0), mat=None, bevel=0.015):
    return add(S.box(name, size, loc, rot, mat or M["sand"], bevel=bevel))


def slit(name, w, h, loc, facing):
    """Lit arrow-slit: dark recess frame with a glowing core, facing +x/-x/+y/-y."""
    sx, sy = (0.05, w) if facing in ("x", "-x") else (w, 0.05)
    box(name + "f", (sx + 0.06 if facing in ("x", "-x") else sx, sy + (0.06 if facing in ("x", "-x") else 0), h + 0.08), loc, mat=M["dark"], bevel=0.01)
    box(name, (sx, sy, h), (loc[0] + (0.01 if facing == "x" else -0.01 if facing == "-x" else 0), loc[1] + (0.01 if facing == "y" else -0.01 if facing == "-y" else 0), loc[2]), mat=M["slit"], bevel=0)


# ---- plinth with stepped, battered terraces
taper_box("Plinth", 7.6, 5.8, 0.9, 0.93, (0, 0, 0), M["dark"], bevel=0.05)
taper_box("Terrace", 6.9, 5.1, 0.7, 0.94, (0, 0, 0.9), M["sand"], bevel=0.04)

# ---- great keep (tall, battered, crowned)
KX, KY = -1.9, -0.7
taper_box("Keep", 2.2, 2.2, 6.0, 0.62, (KX, KY, 1.6), M["sand"], bevel=0.05)
taper_box("KeepPlinth", 2.7, 2.7, 0.9, 0.9, (KX, KY, 1.6), M["dark"], bevel=0.04)
box("KeepCrown", (1.95, 1.95, 0.3), (KX, KY, 7.75), mat=M["dark"], bevel=0.03)
for i in range(20):  # corbels under the crown
    a = i / 20 * math.tau
    box(f"Corbel{i}", (0.18, 0.18, 0.2), (KX + math.cos(a) * 0.93, KY + math.sin(a) * 0.93, 7.55), (0, 0, a), mat=M["dark"], bevel=0.01)
for i in range(12):  # crenellations
    a = i / 12 * math.tau
    box(f"Merlon{i}", (0.26, 0.2, 0.34), (KX + math.cos(a) * 0.92, KY + math.sin(a) * 0.92, 8.07), (0, 0, a), mat=M["sand"], bevel=0.012)
for f, off in (("y", 0.78), ("-y", -0.78), ("x", 0.78), ("-x", -0.78)):
    ax = (off, 0) if f in ("x", "-x") else (0, off)
    for k, z in enumerate((3.0, 4.4, 5.8)):
        w = 0.1
        slit(f"KeepSlit{f}{k}", w, 0.5, (KX + ax[0] * (1 - 0.13 * (z - 1.6) / 4), KY + ax[1] * (1 - 0.13 * (z - 1.6) / 4), z), f)

# ---- long hall with a recessed gate
HX, HY = 0.7, 0.9
taper_box("Hall", 5.4, 2.7, 2.2, 0.9, (HX, HY, 1.6), M["sand"], bevel=0.04)
box("HallCornice", (5.0, 2.6, 0.18), (HX, HY, 3.78), mat=M["dark"], bevel=0.02)
for i in range(9):
    slit(f"HallSlit{i}", 0.16, 0.55, (HX - 2.05 + i * 0.52, HY + 1.28, 3.0), "y")
# gate: dark arch frame on the front with steps
box("GateFrame", (1.5, 0.3, 1.6), (HX + 1.8, HY + 1.35, 2.5), mat=M["dark"], bevel=0.03)
box("GateCore", (0.95, 0.2, 1.25), (HX + 1.8, HY + 1.45, 2.34), mat=M["iron"], bevel=0.02)
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.5, radius2=0.5, depth=0.2)
arch = S.mesh("GateArch", bm, M["iron"], loc=(HX + 1.8, HY + 1.45, 2.95))
arch.rotation_euler = (math.radians(90), 0, 0)
add(arch)
for i in range(6):  # stairs climbing to the gate: the highest tread is nearest the door
    box(f"Step{i}", (2.0 - i * 0.04, 0.34, 0.14), (HX + 1.8, HY + 1.62 + (5 - i) * 0.3, 1.55 + 0.13 * i), mat=M["dark"], bevel=0.01)

# ---- annex + solar field
taper_box("Annex", 2.6, 2.3, 1.5, 0.92, (HX + 4.1, HY - 0.2, 1.6), M["sand"], bevel=0.04)
slit("AnnexSlit", 0.9, 0.12, (HX + 4.1, HY + 0.82, 2.55), "y")
for i in range(3):
    for j in range(2):
        add(S.box(f"Solar{i}{j}", (0.72, 0.5, 0.05), (HX + 3.5 + i * 0.78, HY - 0.5 + j * 0.62, 3.3 + j * 0.12), (math.radians(-28), 0, 0), M["panel"], bevel=0.008))
        add(S.cyl(f"SolarLeg{i}{j}", 0.02, 0.02, 0.35, (HX + 3.5 + i * 0.78, HY - 0.5 + j * 0.62, 3.15), material=M["iron"], verts=6))

# ---- curtain wall with crenellations
taper_box("Wall", 7.6, 0.75, 1.6, 0.9, (0.3, -2.45, 1.6), M["sand"], bevel=0.04)
for i in range(13):
    box(f"WallMerlon{i}", (0.34, 0.5, 0.34), (-3.0 + i * 0.58, -2.45, 3.4), mat=M["sand"], bevel=0.015)
# flanking buttress towers
for sx in (-3.7, 4.2):
    taper_box(f"WallTower{sx}", 1.15, 1.15, 2.4, 0.78, (sx, -2.45, 1.6), M["sand"], bevel=0.04)
    box(f"WallTowerCap{sx}", (1.05, 1.05, 0.2), (sx, -2.45, 4.1), mat=M["dark"], bevel=0.02)

# ---- windtraps: tall tapering louvred towers
for k, (wx, wy, h) in enumerate([(-4.4, 1.2, 6.2), (-4.0, 2.4, 5.2), (5.4, 2.3, 4.6)]):
    taper_box(f"Windtrap{k}", 0.95, 0.95, h, 0.55, (wx, wy, 0.9), M["dark"], bevel=0.03)
    for side in range(4):
        a = side * math.pi / 2
        for fin in range(int(h * 3)):
            z = 1.3 + fin * 0.34
            if z > 0.9 + h - 0.4:
                break
            s = 1 - 0.45 * (z - 0.9) / h
            ox, oy = math.cos(a) * 0.5 * s, math.sin(a) * 0.5 * s
            box(f"Louver{k}{side}{fin}", (0.52 * s if side % 2 else 0.05, 0.05 if side % 2 else 0.52 * s, 0.12), (wx + ox, wy + oy, z), (0, 0, 0), mat=M["iron"], bevel=0.005)

# ---- comms: dish, lattice mast, water tank, pipes
dx, dy, dz = KX, KY, 8.25
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=10, radius=0.85)
for v in list(bm.verts):
    if v.co.z > -0.05 * 0.85:
        bm.verts.remove(v)
dish = S.mesh("Dish", bm, M["steel"], loc=(dx + 0.9, dy - 0.3, dz + 0.55))
dish.rotation_euler = (math.radians(40), 0, math.radians(30))
S.modifier(dish, "SOLIDIFY", thickness=0.02, offset=1.0)
add(dish)
add(S.cyl("DishFeed", 0.015, 0.015, 0.7, (dx + 0.9, dy - 0.3, dz + 0.95), material=M["iron"], verts=8))
for k, (ox, oy) in enumerate([(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]):
    pass
for z0 in range(5):
    add(S.tube(f"MastLeg{z0}", [(dx - 0.5, dy + 0.1, dz + z0 * 0.7), (dx - 0.5, dy + 0.1, dz + z0 * 0.7 + 0.7)], 0.025, M["iron"]))
for lx, ly in ((-0.12, -0.12), (0.12, -0.12), (0.12, 0.12), (-0.12, 0.12)):
    add(S.tube(f"Mast{lx}{ly}", [(dx - 0.5 + lx, dy + 0.1 + ly, dz), (dx - 0.5 + lx * 0.4, dy + 0.1 + ly * 0.4, dz + 3.6)], 0.02, M["iron"], smooth_curve=False))
for z0 in range(7):
    s = 1 - z0 * 0.09
    add(S.tube(f"MastBrace{z0}", [(dx - 0.5 - 0.12 * s, dy + 0.1 - 0.12 * s, dz + z0 * 0.5), (dx - 0.5 + 0.12 * s, dy + 0.1 + 0.12 * s, dz + z0 * 0.5 + 0.5)], 0.012, M["iron"], smooth_curve=False))
beacon_m = glow("Beacon", "#ff2a1a", 9.0)
add(S.sphere("Beacon", 0.08, (dx - 0.5, dy + 0.1, dz + 3.75), material=beacon_m, seg=12, rings=8))
tank = S.cyl("Tank", 0.85, 0.85, 1.3, (HX - 0.6, HY - 0.2, 4.45), material=M["steel"], verts=32, bevel=0.03)
add(tank)
for z in (-0.4, 0.0, 0.4):
    add(S.torus(f"TankBand{z}", 0.87, 0.025, (HX - 0.6, HY - 0.2, 4.45 + z), material=M["iron"], major=32, minor=6))
add(S.cyl("TankCap", 0.85, 0.0, 0.3, (HX - 0.6, HY - 0.2, 5.25), material=M["steel"], verts=32))
for k in range(4):
    a = k * math.pi / 2 + 0.4
    add(S.cyl(f"TankLeg{k}", 0.05, 0.05, 0.9, (HX - 0.6 + math.cos(a) * 0.6, HY - 0.2 + math.sin(a) * 0.6, 3.95), material=M["iron"], verts=8))
add(S.tube("PipeMain", [(HX - 0.6, HY - 0.2, 3.9), (HX - 0.6, HY + 1.0, 3.5), (HX - 0.2, HY + 1.4, 2.4), (HX - 0.2, HY + 1.5, 1.7)], 0.07, M["iron"]))
add(S.tube("PipeSide", [(HX + 2.6, HY + 1.38, 3.4), (HX + 2.6, HY + 1.38, 1.7)], 0.055, M["iron"]))

# ---- banners
for bx, col in ((HX - 1.3, "banner"), (HX + 3.4, "banner")):
    add(S.cyl(f"Pole{bx}", 0.03, 0.03, 2.2, (bx, HY + 1.4, 2.95), material=M["iron"], verts=8))
    bm = bmesh.new()
    vs = {(i, j): bm.verts.new((bx + 0.0, HY + 1.4 + 0.06 * math.sin(i * 0.9) * (i / 7), 3.9 - j * 0.5 / 4 * 4 * 0.5 - 0.02 - i * 0.0)) for i in range(2) for j in range(5)}
    vs = {}
    for i in range(8):
        for j in range(5):
            vs[(i, j)] = bm.verts.new((bx + 0.05 + i * 0.1, HY + 1.4 + 0.07 * math.sin(i * 0.9 + 0.5) * (i / 7), 3.9 - j * 0.28 - i * 0.015))
    for i in range(7):
        for j in range(4):
            bm.faces.new((vs[(i, j)], vs[(i + 1, j)], vs[(i + 1, j + 1)], vs[(i, j + 1)]))
    o = S.mesh(f"Banner{bx}", bm, M["banner"])
    o.data.materials[0].use_backface_culling = False
    add(o)

# ---- rubble + boulders that tie the plinth into the terrain
def rock(name, loc, size, seed):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    rnd = random.Random(seed)
    for v in bm.verts:
        n = (math.sin(v.co.x * 3.1 + seed) + math.sin(v.co.y * 2.7 + seed * 2) + math.sin(v.co.z * 3.7 + seed * 3)) / 3
        v.co *= 1 + 0.28 * n + rnd.uniform(-0.04, 0.04)
        v.co.z *= 0.65
        if v.co.z < -0.2:
            v.co.z = -0.2
    o = S.mesh(name, bm, M["rock"], loc=loc, smooth=True)
    o.scale = size
    o.rotation_euler = (0, 0, seed)
    return add(o)


for i, (rx, ry, rs) in enumerate([(-4.6, -1.8, 1.0), (-4.9, -0.2, 0.8), (4.6, -2.6, 0.9), (5.2, 0.2, 0.7), (-3.0, 3.1, 0.7), (1.5, 3.5, 0.6), (3.8, 3.2, 0.8), (-0.2, -3.6, 0.9), (2.6, -3.5, 0.7), (-2.4, -3.3, 0.8)]):
    rock(f"Rock{i}", (rx, ry, 0.1), (rs * 1.1, rs * 0.9, rs * 0.8), i + 3)

# ---- drifted sand banked against walls + fallen masonry
def drift(name, loc, size, seed):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    for v in bm.verts:
        n = math.sin(v.co.x * 2.3 + seed) * 0.5 + math.sin(v.co.y * 3.1 + seed * 1.7) * 0.5
        v.co *= 1 + 0.12 * n
        v.co.z = max(v.co.z, -0.05) * 0.3
    o = S.mesh(name, bm, M["drift"], loc=loc, smooth=True)
    o.scale = size
    o.rotation_euler = (0, 0, seed)
    return add(o)


for i, (dx_, dy_, sx_, sy_) in enumerate([(-2.0, 3.0, 2.6, 1.0), (2.6, 3.4, 2.2, 0.9), (0.4, -3.0, 3.4, 0.9), (-3.6, -2.7, 1.8, 1.0), (4.4, -1.4, 1.4, 1.5), (-4.1, 1.4, 1.2, 1.6), (4.6, 1.8, 1.1, 1.3)]):
    drift(f"Drift{i}", (dx_, dy_, 0.5), (sx_ * 0.75, sy_ * 0.75, 0.9), i + 1)
for i in range(14):
    a_ = random.uniform(0, math.tau)
    r_ = random.uniform(3.6, 4.6)
    box(f"Fallen{i}", (random.uniform(0.22, 0.5), random.uniform(0.2, 0.4), random.uniform(0.15, 0.3)), (math.cos(a_) * r_ * 1.1, math.sin(a_) * r_ * 0.85, 0.12), (random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3), random.uniform(0, 3)), mat=M["sand"], bevel=0.03)

# ================================================================= bake + export
body = lib.join(static, "Outpost_Body")
body.parent = S.root
print("BODY polys:", len(body.data.polygons), "slots:", len(body.material_slots))
if not FAST:
    lib.unwrap(body, margin=0.002)
    lib.bake_atlas(body, size=4096, ao=True, ao_strength=0.48, emissive=True, name="outpost", samples=16)
if OUT_BLEND:
    lib.save_blend(OUT_BLEND)
lib.export_glb(OUT_GLB, morph=False)
