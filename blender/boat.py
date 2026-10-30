"""
Hero sailboat, v3: unlettered, salt-weathered mahogany sloop.

  blender --background --python blender/boat.py -- public/models/boat.glb blender/boat.blend

Classic wooden sloop: varnished mahogany clinker hull, teak deck, cabin trunk with portholes,
cockpit with coamings, spruce spars, standing rigging with turnbuckles, tan main + cream jib.
All static parts are joined and baked into ONE PBR atlas (colour / ORM / normal / emission).
Moving parts stay separate: Sail_Main, Sail_Jib (morph targets), Flag, Rudder, Tiller, Lantern.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bmesh  # noqa: E402
import bpy  # noqa: E402
import lib  # noqa: E402
from lib import Mat, Scene, hexcol  # noqa: E402
from mathutils import Vector  # noqa: E402

A = lib.args()
OUT_GLB = A[0] if A else "boat.glb"
OUT_BLEND = A[1] if len(A) > 1 else ""
FAST = "--fast" in sys.argv  # skip baking (quick look at geometry/materials)

lib.reset()
S = Scene("Boat")

L, B = 4.6, 0.78
DRAFT = 0.34
S.root.location = (0, 0, -DRAFT)
MAST_Y = -0.15


def plan_x(u):
    if u < 0.58:
        return B * (0.66 + 0.34 * math.sin(u / 0.58 * math.pi * 0.5))
    return B * max(0.0, math.cos(min((u - 0.58) / 0.42, 1) * math.pi * 0.5)) ** 0.78


def sheer(u):
    return 0.62 + 0.42 * u * u + 0.16 * (1 - u) ** 3


def depth(u):
    return 0.78 * (1 - u ** 3 * 0.88) * (0.72 + 0.28 * math.sin(math.pi * min(u + 0.12, 1)))


def uy(y):
    return y / L + 0.5


def zdeck(x, y):
    u = min(max(uy(y), 0.0), 1.0)
    return sheer(u) - 0.045 + 0.05 * (1 - (x / max(plan_x(u), 1e-3)) ** 2)


def hull_pt(u, s, strake=0.0):
    b = plan_x(u)
    top, d = sheer(u), depth(u)
    flare = 1 + 0.09 * (1 - abs(s)) * (1 - u * 0.5)
    return Vector((b * s * flare * (1 + strake), L * (u - 0.5), top - d * (1 - abs(s) ** 2.3)))


# ================================================================ materials
def wood_mat(name, ramp, scale, rough, bump=0.15, varnish=False, island_var=0.0):
    m = Mat(name)
    mp = m.mapping(scale=scale)
    n_big = m.noise(mp.outputs[0], 3.0, 3, 0.6, 1.2)
    n_fine = m.noise(mp.outputs[0], 9.0, 3, 0.65, 0.25)
    # grain rings: stretched noise with a ramp, plus very fine streaks
    grain = m.math("ADD", m.math("MULTIPLY", n_big, 0.7), m.math("MULTIPLY", n_fine, 0.55))
    if island_var:
        geo = m.node("ShaderNodeNewGeometry")
        grain = m.math("ADD", grain, m.math("MULTIPLY", m.math("SUBTRACT", geo.outputs["Random Per Island"], 0.5), island_var))
    col = m.ramp(grain, [(0.15, ramp[0]), (0.5, ramp[1]), (0.85, ramp[2])])
    m.set(**{"Base Color": col.outputs["Color"]})
    rv = m.ramp(n_fine, [(0.0, (rough - 0.08,) * 3 + (1,)), (1.0, (rough + 0.1,) * 3 + (1,))])
    m.link(rv.outputs["Color"], m.bsdf.inputs["Roughness"])
    bp = m.node("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    bp.inputs["Distance"].default_value = 0.01
    m.link(n_fine, bp.inputs["Height"])
    m.link(bp.outputs["Normal"], m.bsdf.inputs["Normal"])
    if varnish:
        m.set(**{"Coat Weight": 0.32, "Coat Roughness": 0.22})
    return m


def hull_mat():
    """Mahogany topsides, antifoul bottom, boot stripe and rubbing strake, masked by smooth per-vertex bands."""
    m = Mat("HullPaint")
    mp = m.mapping(scale=(7, 0.45, 7))
    n_big = m.noise(mp.outputs[0], 3.0, 3, 0.6, 1.2)
    n_fine = m.noise(mp.outputs[0], 12.0, 4, 0.6, 0.2)
    grain = m.math("ADD", m.math("MULTIPLY", n_big, 0.7), m.math("MULTIPLY", n_fine, 0.55))
    wood = m.ramp(grain, [(0.15, "#35251c"), (0.5, "#714c31"), (0.85, "#a47b4e")]).outputs["Color"]
    mott = m.noise(m.mapping(scale=(9, 9, 9)).outputs[0], 6.0, 6, 0.6, 0.3)
    anti = m.mix(m.math("MULTIPLY", mott, 0.9), hexcol("#5a1c15"), hexcol("#2e0d09"))
    cream = m.mix(m.math("MULTIPLY", mott, 0.25), hexcol("#ece2c6"), hexcol("#a79672"))
    attr = m.node("ShaderNodeAttribute", attribute_name="band", attribute_type="GEOMETRY")
    sep = m.node("ShaderNodeSeparateColor")
    m.link(attr.outputs["Color"], sep.inputs["Color"])
    d, h = sep.outputs["Red"], sep.outputs["Green"]
    bottom = m.math("LESS_THAN", h, 0.93)
    boot = m.math("MULTIPLY", m.math("GREATER_THAN", h, 0.96), m.math("LESS_THAN", h, 0.995))
    rail = m.math("MULTIPLY", m.math("GREATER_THAN", d, 1.025), m.math("LESS_THAN", d, 1.065))
    col = m.mix(bottom, wood, anti)
    col = m.mix(boot, col, cream)
    # The gunwale is a real timber rubbing rail, rather than a painted mask.
    m.set(**{"Base Color": col})
    r = m.mix(bottom, (0.29, 0.29, 0.29, 1), (0.7, 0.7, 0.7, 1))
    r = m.mix(m.math("MAXIMUM", boot, rail), r, (0.5, 0.5, 0.5, 1))
    m.link(r, m.bsdf.inputs["Roughness"])
    bp = m.node("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.16; bp.inputs["Distance"].default_value = 0.003
    m.link(n_fine, bp.inputs["Height"]); m.link(bp.outputs["Normal"], m.bsdf.inputs["Normal"])
    return m


def paint_mat(name, color, rough, dirt="#7b6a4f", wear=0.25):
    m = Mat(name)
    mp = m.mapping(scale=(9, 9, 9))
    mottle = m.noise(mp.outputs[0], 6.0, 6, 0.6, 0.3)
    brush = m.noise(m.mapping(scale=(60, 4, 60)).outputs[0], 18.0, 3, 0.5)
    c = m.mix(m.math("MULTIPLY", mottle, wear), hexcol(color), hexcol(dirt))
    c = m.mix(m.math("MULTIPLY", brush, 0.08), c, hexcol(dirt))
    m.set(**{"Base Color": c})
    r = m.ramp(mottle, [(0.0, (rough - 0.08,) * 3 + (1,)), (1.0, (rough + 0.12,) * 3 + (1,))])
    m.link(r.outputs["Color"], m.bsdf.inputs["Roughness"])
    bp = m.node("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.12; bp.inputs["Distance"].default_value = 0.005
    m.link(brush, bp.inputs["Height"]); m.link(bp.outputs["Normal"], m.bsdf.inputs["Normal"])
    return m


def metal_mat(name, color, rough, tarnish="#4b3a1c"):
    m = Mat(name)
    mp = m.mapping(scale=(14, 14, 14))
    n = m.noise(mp.outputs[0], 7.0, 5, 0.6, 0.5)
    c = m.mix(m.math("MULTIPLY", n, 0.9), hexcol(color), hexcol(tarnish))
    m.set(**{"Base Color": c, "Metallic": 1.0})
    r = m.ramp(n, [(0.0, (rough - 0.1,) * 3 + (1,)), (1.0, (rough + 0.22,) * 3 + (1,))])
    m.link(r.outputs["Color"], m.bsdf.inputs["Roughness"])
    return m


def rope_mat(name, color):
    m = Mat(name)
    mp = m.mapping(scale=(60, 60, 60))
    n = m.noise(mp.outputs[0], 30.0, 4, 0.6)
    w = m.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="DIAGONAL")
    w.inputs["Scale"].default_value = 220; w.inputs["Distortion"].default_value = 2.0
    m.link(mp.outputs[0], w.inputs["Vector"])
    shade = m.math("ADD", m.math("MULTIPLY", n, 0.5), m.math("MULTIPLY", w.outputs["Fac"], 0.5))
    col = m.ramp(shade, [(0.2, "#8a7048"), (0.8, color)])
    m.set(**{"Base Color": col.outputs["Color"], "Roughness": 0.95})
    bp = m.node("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.5; bp.inputs["Distance"].default_value = 0.004
    m.link(w.outputs["Fac"], bp.inputs["Height"]); m.link(bp.outputs["Normal"], m.bsdf.inputs["Normal"])
    return m


def glass_mat(name, glow, strength):
    m = Mat(name)
    m.set(**{"Base Color": "#18222a", "Roughness": 0.06, "Emission Color": glow, "Emission Strength": strength})
    return m


M = {
    "hull": hull_mat(),
    "white": paint_mat("PaintWhite", "#e8e0cd", 0.5, wear=0.2),
    "teak": wood_mat("Teak", ["#7d7057", "#a89979", "#c4b898"], (12, 0.6, 12), 0.64, 0.18, island_var=0.3),
    "subdeck": paint_mat("Caulk", "#1b130d", 0.9, dirt="#0b0805", wear=0.2),
    "spar": wood_mat("Spruce", ["#b99a68", "#d2b583", "#e3cb9d"], (22, 1.2, 22), 0.5, 0.18),
    "trim": wood_mat("TrimMahogany", ["#3e291d", "#775238", "#a47a4d"], (10, 0.65, 10), 0.27, 0.12, varnish=True),
    "brass": metal_mat("Brass", "#e0b860", 0.3),
    "iron": metal_mat("Iron", "#2d2a27", 0.5, tarnish="#171614"),
    "rope": rope_mat("Rope", "#c3a46e"),
    "rope_dark": rope_mat("RopeTarred", "#3a2a1a"),
    "porthole": glass_mat("Porthole", "#d5a56c", 0.28),
    "fender": paint_mat("Fender", "#ece7da", 0.55, wear=0.35),
    "red": glass_mat("NavRed", "#ff2a1a", 6.0),
    "green": glass_mat("NavGreen", "#1aff5a", 6.0),
    "cushion": paint_mat("Canvas", "#2b4a63", 0.9, dirt="#1b2e40", wear=0.5),
}
def flat(name, color, rough=0.5, metal=0.0):
    m = Mat(name); m.set(**{"Base Color": color, "Roughness": rough, "Metallic": metal}); return m


# moving parts keep simple PBR materials (they are not part of the baked atlas)
F_WOOD, F_BRASS, F_IRON = flat("RudderWood", "#4a2414", 0.35), flat("BrassFlat", "#d0a850", 0.3, 1.0), flat("IronFlat", "#2d2a27", 0.5, 0.85)
static = []


def add(o):
    static.append(o)
    return o


# ================================================================ hull
def build_hull():
    N, M_ = 128, 64
    bm = bmesh.new()
    grid = []
    for i in range(N + 1):
        u = i / N
        grid.append([bm.verts.new(hull_pt(u, j / M_ * 2 - 1, strake=0.003 * ((j // 4) % 2))) for j in range(M_ + 1)])
    for i in range(N):
        for j in range(M_):
            f = bm.faces.new((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]))
            f.smooth = True
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    try:
        bm.faces.new([grid[0][j] for j in range(M_ + 1)])
    except ValueError:
        pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    band = bm.loops.layers.float_color.new("band")
    for f in bm.faces:
        for loop in f.loops:
            v = loop.vert.co
            loop[band] = (1.0 + (sheer(uy(v.y)) - v.z), 1.0 + (v.z - DRAFT), 0.0, 1.0)
    slots = [M["hull"]]
    me = bpy.data.meshes.new("Hull")
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    for s in slots:
        me.materials.append(s.m)
    o = bpy.data.objects.new("Hull", me)
    S.link(o)
    S.modifier(o, "SOLIDIFY", thickness=0.05, offset=-1.0)
    S.modifier(o, "SUBSURF", levels=1, render_levels=1)
    return add(o)


def build_deck():
    """Teak planking laid board by board, with the cabin and cockpit cut out."""
    bm = bmesh.new()
    N, bw, gap = 64, 0.115, 0.006
    nb = int(B / bw) + 2

    def excluded(x, y):
        return (abs(x) < 0.47 and -0.83 < y < 0.43) or (abs(x) < 0.42 and -2.12 < y < -1.12)

    for k in range(-nb, nb):
        x0, x1 = k * bw + gap / 2, (k + 1) * bw - gap / 2
        prev = None
        for i in range(N + 1):
            u = 0.01 + 0.98 * i / N
            lim = plan_x(u) * 0.975
            a, b_ = max(min(x0, lim), -lim), max(min(x1, lim), -lim)
            y = L * (u - 0.5)
            if b_ - a < 0.004 or excluded((a + b_) / 2, y):
                prev = None
                continue
            pair = (bm.verts.new((a, y, zdeck(a, y))), bm.verts.new((b_, y, zdeck(b_, y))))
            if prev:
                bm.faces.new((prev[0], prev[1], pair[1], pair[0]))
            prev = pair
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = S.mesh("Deck", bm, M["teak"], smooth=False)
    S.modifier(o, "SOLIDIFY", thickness=0.025, offset=-1.0)
    add(o)

    # dark sub-deck so gaps read as caulked seams
    bm = bmesh.new()
    prevrow = None
    for i in range(0, 41):
        u = 0.01 + 0.98 * i / 40
        lim = plan_x(u) * 0.98
        y = L * (u - 0.5)
        row = [bm.verts.new((lim * (j / 12 * 2 - 1), y, zdeck(lim * (j / 12 * 2 - 1), y) - 0.02)) for j in range(13)]
        if prevrow:
            for j in range(12):
                bm.faces.new((prevrow[j], prevrow[j + 1], row[j + 1], row[j]))
        prevrow = row
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    add(S.mesh("SubDeck", bm, M["subdeck"], smooth=False))


def build_cabin():
    """Cabin trunk lofted along y: vertical sides, crowned roof, raked and rounded front."""
    ys = [-0.8 + i * 0.05 for i in range(25)]  # -0.8 … 0.4
    bm = bmesh.new()
    rings = []
    for y in ys:
        t = (y + 0.8) / 1.2
        rake = max(0.0, (t - 0.72) / 0.28)
        hs = 0.3 * (1 - 0.55 * rake ** 1.5)
        c = 0.07 * (1 - 0.6 * rake)
        w = 0.45 * (1 - 0.22 * rake)
        prof = [(-w, 0.0), (-w, hs * 0.55), (-w * 0.97, hs), (-w * 0.62, hs + c * 0.72), (0, hs + c), (w * 0.62, hs + c * 0.72), (w * 0.97, hs), (w, hs * 0.55), (w, 0.0)]
        rings.append([bm.verts.new((x, y, zdeck(x, y) + z)) for x, z in prof])
    for i in range(len(rings) - 1):
        for j in range(len(rings[0]) - 1):
            bm.faces.new((rings[i][j], rings[i][j + 1], rings[i + 1][j + 1], rings[i + 1][j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = S.mesh("CabinTrunk", bm, M["white"])
    S.modifier(o, "SUBSURF", levels=1, render_levels=1)
    add(o)
    # varnished coach-roof rail and companionway
    add(S.tube("CabinRailP", [(-0.465, y, zdeck(-0.465, y) + 0.3 * (1 - 0.55 * max(0, ((y + 0.8) / 1.2 - 0.72) / 0.28) ** 1.5) + 0.01) for y in ys[:19]], 0.02, M["trim"]))
    add(S.tube("CabinRailS", [(0.465, y, zdeck(0.465, y) + 0.3 * (1 - 0.55 * max(0, ((y + 0.8) / 1.2 - 0.72) / 0.28) ** 1.5) + 0.01) for y in ys[:19]], 0.02, M["trim"]))
    # portholes: brass ring + lit glass, three per side
    for sgn in (-1, 1):
        for y in (-0.5, -0.12, 0.26):
            x = sgn * 0.452
            z = zdeck(x, y) + 0.165
            add(S.torus(f"PortRing{sgn}{y}", 0.062, 0.012, (x, y, z), rot=(0, math.radians(90), 0), material=M["brass"], major=24, minor=6))
            g = S.cyl(f"PortGlass{sgn}{y}", 0.056, 0.056, 0.012, (x + sgn * 0.002, y, z), rot=(0, math.radians(90), 0), material=M["porthole"], verts=20)
            add(g)
    # companionway: dark opening framed in mahogany, brass handle, sliding hatch above
    zc = zdeck(0, -0.8)
    add(S.box("CompanionFrame", (0.46, 0.04, 0.26), (0, -0.815, zc + 0.15), material=M["trim"], bevel=0.012))
    add(S.box("CompanionDark", (0.38, 0.03, 0.2), (0, -0.825, zc + 0.15), material=M["iron"], bevel=0.005))
    add(S.box("Hatch", (0.5, 0.42, 0.035), (0, -0.62, zc + 0.37), material=M["trim"], bevel=0.012))
    add(S.box("HatchRunnerP", (0.03, 0.55, 0.03), (-0.26, -0.58, zc + 0.355), material=M["trim"], bevel=0.008))
    add(S.box("HatchRunnerS", (0.03, 0.55, 0.03), (0.26, -0.58, zc + 0.355), material=M["trim"], bevel=0.008))
    add(S.cyl("HatchHandle", 0.012, 0.012, 0.16, (0, -0.46, zc + 0.395), rot=(0, math.radians(90), 0), material=M["brass"], verts=8))
    # skylight forward
    add(S.box("Skylight", (0.34, 0.3, 0.06), (0, 0.18, zdeck(0, 0.18) + 0.37), material=M["trim"], bevel=0.012))
    add(S.box("SkylightGlass", (0.26, 0.22, 0.012), (0, 0.18, zdeck(0, 0.18) + 0.405), material=M["porthole"], bevel=0))
    # mast partners on the roof
    add(S.cyl("MastCollar", 0.12, 0.12, 0.05, (0, MAST_Y, zdeck(0, MAST_Y) + 0.4), material=M["brass"], verts=24, bevel=0.01))


def build_cockpit():
    y0, y1, hw = -2.12, -1.12, 0.42
    zf = zdeck(0, -1.6) - 0.3
    add(S.box("CockpitFloor", (hw * 2, y1 - y0, 0.03), (0, (y0 + y1) / 2, zf), material=M["teak"], bevel=0.005))
    for sgn in (-1, 1):
        add(S.box(f"Coaming{sgn}", (0.05, y1 - y0 + 0.1, 0.3), (sgn * (hw + 0.025), (y0 + y1) / 2, zf + 0.19), material=M["trim"], bevel=0.012))
        add(S.box(f"Bench{sgn}", (0.28, y1 - y0 - 0.15, 0.04), (sgn * 0.26, (y0 + y1) / 2 - 0.02, zf + 0.18), material=M["teak"], bevel=0.008))
        add(S.box(f"Cushion{sgn}", (0.26, 0.82, 0.045), (sgn * 0.26, -1.55, zf + 0.215), material=M["cushion"], bevel=0.02))
        add(S.cyl(f"Winch{sgn}", 0.045, 0.045, 0.07, (sgn * (hw + 0.02), -1.35, zf + 0.37), material=M["brass"], verts=20, bevel=0.01))
        add(S.cyl(f"WinchTop{sgn}", 0.03, 0.03, 0.025, (sgn * (hw + 0.02), -1.35, zf + 0.42), material=M["iron"], verts=16))
    add(S.box("CockpitBulkhead", (hw * 2 + 0.1, 0.05, 0.3), (0, y1 + 0.02, zf + 0.17), material=M["trim"], bevel=0.012))
    add(S.box("Lazarette", (0.7, 0.5, 0.05), (0, -2.0, zf + 0.12), material=M["teak"], bevel=0.01))
    add(S.torus("HatchRing", 0.05, 0.01, (0, -2.0, zf + 0.15), material=M["brass"], major=18, minor=6))


def build_rails():
    for sgn in (-1, 1):
        n = "P" if sgn < 0 else "S"
        add(S.tube(f"Rail{n}", [(sgn * plan_x(i / 28), L * (i / 28 - 0.5), sheer(i / 28) + 0.025) for i in range(29)], 0.038, M["trim"]))
        for i in range(2, 28, 5):
            u = i / 28
            if -0.9 < L * (u - 0.5) < 0.45:
                pass
            add(S.cyl(f"Stan{n}{i}", 0.018, 0.014, 0.26, (sgn * plan_x(u), L * (u - 0.5), sheer(u) + 0.15), material=M["brass"], verts=8))
        for h in (0.17, 0.3):
            add(S.tube(f"Life{n}{h}", [(sgn * plan_x(i / 28), L * (i / 28 - 0.5), sheer(i / 28) + h + 0.02) for i in range(2, 28, 5)], 0.004, M["iron"]))
        # fenders hung over the side
        for y in (-0.55, 0.55):
            x = sgn * (plan_x(uy(y)) + 0.1)
            add(S.cyl(f"Fender{n}{y}", 0.05, 0.05, 0.3, (x, y, sheer(uy(y)) - 0.12), material=M["fender"], verts=16, bevel=0.03))
            add(S.tube(f"FenderLine{n}{y}", [(sgn * plan_x(uy(y)), y, sheer(uy(y)) + 0.03), (x, y, sheer(uy(y)) + 0.02), (x, y, sheer(uy(y)) + 0.09)], 0.006, M["rope"]))
    # bow pulpit, anchor roller, bow fitting
    zb = sheer(1.0)
    pul = [(-plan_x(0.9), L * 0.4, sheer(0.9) + 0.3), (-plan_x(0.96), L * 0.46, zb + 0.3), (0, L / 2 + 0.08, zb + 0.32), (plan_x(0.96), L * 0.46, zb + 0.3), (plan_x(0.9), L * 0.4, sheer(0.9) + 0.3)]
    add(S.tube("Pulpit", pul, 0.014, M["brass"]))
    for x, y, z in pul[::2]:
        add(S.cyl(f"PulpitLeg{x:.2f}", 0.014, 0.014, 0.3, (x, y, z - 0.15), material=M["brass"], verts=8))
    add(S.box("Roller", (0.12, 0.2, 0.06), (0, L / 2 + 0.05, zb + 0.06), material=M["iron"], bevel=0.01))
    add(S.cyl("RollerWheel", 0.03, 0.03, 0.1, (0, L / 2 + 0.12, zb + 0.1), rot=(0, math.radians(90), 0), material=M["brass"], verts=16))
    add(S.tube("Stem", [(0, L / 2 - 0.04, zb + 0.4), (0, L / 2 + 0.1, zb + 0.18), (0, L / 2 + 0.12, zb - 0.2), (0, L / 2, zb - depth(1) + 0.02)], 0.048, M["trim"]))
    # cleats
    for k, (x, y) in enumerate([(-0.58, 1.5), (0.58, 1.5), (-0.6, -0.3), (0.6, -0.3), (-0.5, -2.0), (0.5, -2.0)]):
        add(S.box(f"Cleat{k}", (0.16, 0.05, 0.045), (x, y, zdeck(x, y) + 0.03), material=M["brass"], bevel=0.012))
    # nav lights
    for sgn, key in ((-1, "red"), (1, "green")):
        add(S.sphere(f"Nav{key}", 0.028, (sgn * 0.42, 0.2, zdeck(sgn * 0.42, 0.2) + 0.33), material=M[key], seg=12, rings=8))
    # The transom is intentionally unlettered.
    add(S.sphere("SternLight", 0.03, (0, -L / 2 + 0.05, sheer(0) + 0.34), material=M["white"], seg=12, rings=8))


def build_spars_and_rigging():
    zr = zdeck(0, MAST_Y) + 0.42
    add(S.cyl("Mast", 0.075, 0.04, 4.75 - zr, (0, MAST_Y, (4.75 + zr) / 2), material=M["spar"], verts=24))
    for z in (1.6, 2.6, 3.6):
        add(S.torus(f"MastBand{z}", 0.082 - (z - 1.0) * 0.008, 0.012, (0, MAST_Y, z), material=M["brass"], major=24, minor=6))
    add(S.sphere("MastCap", 0.06, (0, MAST_Y, 4.77), material=M["brass"]))
    add(S.cyl("MastLight", 0.014, 0.014, 0.12, (0, MAST_Y, 4.86), material=M["iron"], verts=8))
    zb = 1.42
    add(S.cyl("Boom", 0.042, 0.032, 2.05, (0, MAST_Y - 1.02, zb), rot=(math.radians(90), 0, 0), material=M["spar"]))
    add(S.box("Gooseneck", (0.1, 0.1, 0.09), (0, MAST_Y, zb), material=M["brass"], bevel=0.02))
    add(S.cyl("BoomEnd", 0.036, 0.036, 0.04, (0, MAST_Y - 2.06, zb), rot=(math.radians(90), 0, 0), material=M["brass"], verts=14))
    # spreaders + shrouds with turnbuckles
    zs = 3.0
    for sgn in (-1, 1):
        n = "P" if sgn < 0 else "S"
        add(S.cyl(f"Spreader{n}", 0.014, 0.01, 0.62, (sgn * 0.31, MAST_Y, zs), rot=(0, math.radians(90), 0), material=M["spar"], verts=10))
        for dy, nm in ((0.34, "F"), (-0.4, "A")):
            cp = (sgn * (plan_x(uy(MAST_Y + dy)) - 0.01), MAST_Y + dy, zdeck(sgn * 0.7, MAST_Y + dy) + 0.03)
            add(S.tube(f"Shroud{n}{nm}", [(0, MAST_Y, 4.5), (sgn * 0.62, MAST_Y + dy * 0.1, zs + 0.0), cp], 0.0065, M["iron"], smooth_curve=False))
            d = Vector(cp) - Vector((sgn * 0.62, MAST_Y + dy * 0.1, zs))
            mid = Vector(cp) - d.normalized() * 0.3
            tb = S.cyl(f"Turnbuckle{n}{nm}", 0.012, 0.012, 0.14, tuple(mid), material=M["brass"], verts=8)
            tb.rotation_euler = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_euler()
            add(tb)
            add(S.box(f"Chainplate{n}{nm}", (0.035, 0.06, 0.05), cp, material=M["brass"], bevel=0.008))
        for z in (1.9,):
            cp = (sgn * (plan_x(uy(MAST_Y)) - 0.01), MAST_Y, zdeck(sgn * 0.7, MAST_Y) + 0.03)
            add(S.tube(f"Lower{n}", [(0, MAST_Y, z + 0.9), cp], 0.0055, M["iron"]))
    zbow = sheer(1.0) + 0.2
    add(S.tube("Forestay", [(0, MAST_Y, 4.5), (0, 1.3, 2.9), (0, L / 2 + 0.12, zbow)], 0.0075, M["iron"], smooth_curve=False))
    add(S.tube("Backstay", [(0, MAST_Y, 4.5), (0, -1.5, 2.6), (0, -L / 2 + 0.06, sheer(0) + 0.15)], 0.0065, M["iron"], smooth_curve=False))
    # mainsheet from boom end through a block to the cockpit
    add(S.tube("Mainsheet", [(0, MAST_Y - 1.9, zb), (0.05, -2.0, 1.0), (0.1, -1.7, zdeck(0.1, -1.7) + 0.3)], 0.007, M["rope"], smooth_curve=False))
    add(S.box("Block", (0.04, 0.06, 0.07), (0, MAST_Y - 1.9, zb - 0.05), material=M["brass"], bevel=0.01))
    # coiled halyards on the mast + rope coil on the cabin roof
    add(S.torus("Coil", 0.12, 0.022, (0.1, 0.0, zdeck(0.1, 0.0) + 0.37), material=M["rope"], major=24, minor=6))


def build_working_fittings():
    # Spiral halyards, grooved winches and fastened deck hardware add scale cues
    # that survive the close approach to each island.
    for side in (-1, 1):
        for k in range(4):
            pts = []
            for j in range(65):
                a = j / 64 * math.tau
                r = 0.055 + k * 0.013 + j / 64 * 0.012
                pts.append((side * 0.54 + math.cos(a) * r, 0.84 + math.sin(a) * r,
                            zdeck(side * 0.54, 0.84) + 0.018 + k * 0.001))
            add(S.tube(f"HalyardCoil{side}_{k}", pts, 0.006, M["rope"], res=2, smooth_curve=False))
        for y in (-0.3, 1.45):
            x = side * min(0.54, plan_x(uy(y)) - 0.1)
            zd = zdeck(x, y)
            add(S.box(f"CleatFoot{side}_{y}", (0.14, 0.075, 0.012), (x, y, zd + 0.012), material=M["brass"], bevel=0.008))
            for offset in (-0.045, 0.045):
                add(S.cyl("CountersunkFastener", 0.007, 0.007, 0.003, (x + offset, y, zd + 0.02), material=M["iron"], verts=10))
        zf = zdeck(0, -1.6) - 0.3
        for step in range(3):
            add(S.torus(f"WinchGroove{side}_{step}", 0.046, 0.004,
                (side * 0.44, -1.35, zf + 0.35 + step * 0.018), material=M["iron"], major=24, minor=5))
    # Stowed anchor, a stock and two flukes, secured on the foredeck.
    anchor_z = zdeck(0.18, 1.5) + 0.035
    add(S.tube("AnchorShank", [(0.16, 1.34, anchor_z), (0.16, 1.72, anchor_z)], 0.018, M["iron"]))
    add(S.tube("AnchorCrown", [(-0.01, 1.65, anchor_z), (0.16, 1.75, anchor_z), (0.33, 1.65, anchor_z)], 0.023, M["iron"], smooth_curve=False))
    add(S.torus("AnchorShackle", 0.025, 0.007, (0.16, 1.32, anchor_z), material=M["brass"], major=18, minor=5))
    for side in (-1, 1):
        add(S.box("AnchorFluke", (0.085, 0.095, 0.016), (0.16 + side * 0.15, 1.65, anchor_z), rot=(0, 0, side * 0.38), material=M["iron"], bevel=0.006))


# ================================================================ sails
def sail(name, tack, clew, head, bulge, base_color):
    Nn = 48
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    tack, clew, head = Vector(tack), Vector(clew), Vector(head)
    vs = {}
    for i in range(Nn + 1):
        for j in range(Nn + 1):
            u, v = i / Nn, j / Nn
            vs[(i, j)] = bm.verts.new(tack + (clew - tack) * u * (1 - v) + (head - tack) * v)
    for i in range(Nn):
        for j in range(Nn):
            f = bm.faces.new((vs[(i, j)], vs[(i + 1, j)], vs[(i + 1, j + 1)], vs[(i, j + 1)]))
            for loop, (a, b_) in zip(f.loops, [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]):
                loop[uvl].uv = (a / Nn, b_ / Nn)
    o = S.mesh(name, bm, SAIL, loc=(0, 0, 0))
    me = o.data
    me.materials[0].use_backface_culling = False
    o.shape_key_add(name="Basis")

    def body(idx):
        i, j = divmod(idx, Nn + 1)
        u, w = i / Nn, j / Nn
        return u, w, math.sin(math.pi * u) * max(math.sin(math.pi * min(w * 1.02, 1)), 0) ** 0.7

    for idx in range(len(me.vertices)):
        u, w, b0 = body(idx)
        # Broad camber plus small tension wrinkles near the corners and luff.
        corner = math.exp(-u * 9) + math.exp(-(1 - u) * 9)
        wrinkle = math.sin(w * 55 + u * 12) * corner * math.sin(math.pi * w) * 0.006
        me.shape_keys.key_blocks["Basis"].data[idx].co.x += b0 * bulge * 0.3 + wrinkle

    def key(nm, amount, flutter):
        sk = o.shape_key_add(name=nm)
        for idx in range(len(me.vertices)):
            u, w, b0 = body(idx)
            edge = max(0, (u - 0.55) / 0.45) * max(0, min((w - 0.1) / 0.8, 1))
            fl = (math.sin(u * 9 + w * 4) * 0.045 + math.sin(u * 17 + w * 7) * 0.018) * edge * flutter
            sk.data[idx].co.x += b0 * amount + fl + math.sin(w * 11 + u * 3) * 0.012 * min(u / 0.4, 1)
    key("Billow", bulge, 0.0)
    key("Flutter", bulge * 0.7, 1.0)
    me.update()
    for p in me.polygons:
        p.use_smooth = True
    return o


def canvas_mat(name, tint):
    m = Mat(name)
    uvm = m.mapping(scale=(1, 1, 1), source="UV")
    sep = m.node("ShaderNodeSeparateXYZ")
    m.link(uvm.outputs[0], sep.inputs["Vector"])
    u, v = sep.outputs["X"], sep.outputs["Y"]
    # weave: two perpendicular fine band patterns
    w1 = m.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="X")
    w1.inputs["Scale"].default_value = 145; w1.inputs["Distortion"].default_value = 0.15
    w2 = m.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="Y")
    w2.inputs["Scale"].default_value = 145; w2.inputs["Distortion"].default_value = 0.15
    m.link(uvm.outputs[0], w1.inputs["Vector"]); m.link(uvm.outputs[0], w2.inputs["Vector"])
    weave = m.math("MULTIPLY", m.math("ADD", w1.outputs["Fac"], w2.outputs["Fac"]), 0.5)
    stain = m.noise(uvm.outputs[0], 5.0, 6, 0.6, 0.4)
    # panel seams every 1/10 of the height, with a pair of stitch lines
    f = m.math("FRACT", m.math("MULTIPLY", v, 11.0))
    seam = m.math("LESS_THAN", m.math("ABSOLUTE", m.math("SUBTRACT", f, 0.5)), 0.0)  # placeholder removed below
    d = m.math("MINIMUM", f, m.math("SUBTRACT", 1.0, f))
    seamline = m.math("LESS_THAN", d, 0.018)
    stitch = m.math("MULTIPLY", m.math("LESS_THAN", m.math("ABSOLUTE", m.math("SUBTRACT", d, 0.05)), 0.004), m.math("GREATER_THAN", m.noise(uvm.outputs[0], 400.0, 1), 0.45))
    # bolt-rope border
    edge = m.math("MINIMUM", m.math("MINIMUM", u, m.math("SUBTRACT", 1.0, u)), m.math("MINIMUM", v, m.math("SUBTRACT", 1.0, v)))
    border = m.math("LESS_THAN", edge, 0.012)
    base = m.mix(m.math("MULTIPLY", weave, 0.15), hexcol(tint), hexcol("#c7bfa8"))
    base = m.mix(m.math("MULTIPLY", stain, 0.12), base, hexcol("#a89b80"))
    base = m.mix(m.math("MULTIPLY", seamline, 0.15), base, hexcol("#b6aa90"))
    base = m.mix(m.math("MULTIPLY", stitch, 0.35), base, hexcol("#82765f"))
    base = m.mix(border, base, hexcol("#d1c5a8"))
    m.set(**{"Base Color": base, "Roughness": 0.93})
    h = m.math("ADD", m.math("MULTIPLY", weave, 0.35), m.math("MULTIPLY", seamline, -0.5))
    h = m.math("ADD", h, m.math("MULTIPLY", border, 0.9))
    bp = m.node("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.24; bp.inputs["Distance"].default_value = 0.0015
    m.link(h, bp.inputs["Height"]); m.link(bp.outputs["Normal"], m.bsdf.inputs["Normal"])
    return m


# ================================================================ build
S_MAIN_TINT, S_JIB_TINT = "#ece7d6", "#e6dfca"
SAIL = canvas_mat("CanvasMain", S_MAIN_TINT)
build_hull(); build_deck(); build_cabin(); build_cockpit(); build_rails(); build_spars_and_rigging(); build_working_fittings()

zb = 1.42
sail_main = sail("Sail_Main", (0, MAST_Y - 0.06, zb + 0.05), (0, MAST_Y - 2.0, zb + 0.05), (0, MAST_Y - 0.06, 4.6), 0.5, S_MAIN_TINT)
SAIL = canvas_mat("CanvasJib", S_JIB_TINT)
sail_jib = sail("Sail_Jib", (0, L / 2 + 0.05, sheer(1.0) + 0.25), (0, 0.55, 1.5), (0, MAST_Y + 0.08, 4.35), 0.34, S_JIB_TINT)

# flag
fl = bmesh.new()
fv = {(i, j): fl.verts.new((0, MAST_Y - i / 14 * 0.6, 4.62 + j / 2 * 0.28)) for i in range(15) for j in range(3)}
for i in range(14):
    for j in range(2):
        fl.faces.new((fv[(i, j)], fv[(i + 1, j)], fv[(i + 1, j + 1)], fv[(i, j + 1)]))
flag_mat = Mat("Flag"); flag_mat.set(**{"Base Color": "#d6442a", "Roughness": 0.8})
flag = S.mesh("Flag", fl, flag_mat)
flag.data.materials[0].use_backface_culling = False
flag.shape_key_add(name="Basis")
sk = flag.shape_key_add(name="Wave")
for idx in range(len(flag.data.vertices)):
    x = (idx // 3) / 14
    sk.data[idx].co.x = math.sin(x * 11) * 0.07 * x + math.sin(x * 5) * 0.03 * x

# rudder + tiller (hinged, separate so the web app can swing them)
from mathutils import Matrix  # noqa: E402
rb = bmesh.new()
bmesh.ops.create_cube(rb, size=1.0)
for v in rb.verts:
    v.co.x *= 0.035; v.co.y = v.co.y * 0.26 - 0.13; v.co.z = v.co.z * 0.9 - 0.42
rudder = S.mesh("Rudder", rb, F_WOOD, smooth=False)
S.modifier(rudder, "BEVEL", width=0.012, segments=2, limit_method="ANGLE")
rudder.location = (0, -L / 2 - 0.03, 0.32)
zt = sheer(0.0) + 0.17
tiller = S.cyl("Tiller", 0.026, 0.017, 1.15, (0, 0, 0), material=F_WOOD, verts=12)
tiller.data.transform(Matrix.Rotation(math.radians(-90), 4, "X"))
tiller.data.transform(Matrix.Translation((0, 0.575, 0)))
tiller.location = (0, -L / 2 + 0.02, zt)
S.sphere("TillerKnob", 0.028, (0, 1.15, 0), material=F_BRASS, parent=tiller, seg=12, rings=8)

# lantern on a davit at the bow
lan = S.empty("Lantern", (0, L / 2 - 0.25, sheer(1.0) + 0.78))
lg = S.cyl("LanternGlass", 0.09, 0.075, 0.2, (0, 0, -0.1), material=glass_mat("LanternGlow", "#ffb257", 7.0), parent=lan, verts=16)
S.cyl("LanternCap", 0.115, 0.0, 0.09, (0, 0, 0.055), material=F_IRON, parent=lan, verts=16)
S.cyl("LanternBase", 0.1, 0.1, 0.03, (0, 0, -0.21), material=F_IRON, parent=lan, verts=16)
for k in range(4):
    a = k * math.pi / 2
    S.cyl(f"LanternBar{k}", 0.006, 0.006, 0.24, (math.cos(a) * 0.088, math.sin(a) * 0.088, -0.1), material=F_IRON, parent=lan, verts=6)
S.tube("LanternDavit", [(0, L / 2 - 0.25, sheer(1.0) + 0.02), (0, L / 2 - 0.25, sheer(1.0) + 0.72), (0, L / 2 - 0.25, sheer(1.0) + 0.93), (0, L / 2 - 0.25, sheer(1.0) + 0.97)], 0.015, F_IRON)

# ---- one static mesh, one atlas
body = lib.join(static, "Boat_Body")
bpy.context.view_layer.update()
body.parent = S.root
print("BODY polys:", len(body.data.polygons), "slots:", len(body.material_slots))
if not FAST:
    lib.unwrap(body, margin=0.002)
    lib.bake_atlas(body, size=4096, ao=True, ao_strength=0.48, emissive=True, name="boat", samples=16)
    for nm in ("Sail_Main", "Sail_Jib"):
        o = bpy.data.objects[nm]
        lib.bake_atlas(o, size=2048, ao=False, emissive=False, name=nm.lower(), samples=8)

if OUT_BLEND:
    lib.save_blend(OUT_BLEND)
lib.export_glb(OUT_GLB)
