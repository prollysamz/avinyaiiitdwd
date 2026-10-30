"""
Avinya — hero sailboat.

Run headless:
  blender --background --python blender/build_boat.py -- <out.glb> [<out.blend>] [<preview.png>]

Conventions (so the glTF lands right in three.js):
  1 unit = 1 m, Blender +Y = bow (becomes glTF -Z), +Z = up, waterline at z = 0.
Named nodes the web app animates:  Sail_Main, Sail_Jib, Flag (morph targets),
  Rudder, Tiller, Lantern, Helm_Torso, Helm_Head, Helm_Arm, Hull_Mask.
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT_GLB = argv[0] if len(argv) > 0 else "boat.glb"
OUT_BLEND = argv[1] if len(argv) > 1 else ""
OUT_PNG = argv[2] if len(argv) > 2 else ""

L, B = 4.6, 0.78
DRAFT = 0.34  # the whole boat is lowered by this much so the waterline sits at z = 0
random.seed(7)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


# ------------------------------------------------------------------ helpers
def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hexcol(h, a=1.0):
    h = h.lstrip("#")
    return (lin(int(h[0:2], 16) / 255), lin(int(h[2:4], 16) / 255), lin(int(h[4:6], 16) / 255), a)


MATS = {}


def mat(name, color, rough=0.6, metal=0.0, emit=None, emit_strength=0.0, alpha=1.0, coat=0.0):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = hexcol(color)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if coat and "Coat Weight" in b.inputs:
        b.inputs["Coat Weight"].default_value = coat
    if emit:
        b.inputs["Emission Color"].default_value = hexcol(emit)
        b.inputs["Emission Strength"].default_value = emit_strength
    if alpha < 1.0:
        b.inputs["Alpha"].default_value = alpha
    MATS[name] = m
    return m


# ----- materials (names are used by the web app to attach its PBR textures)
M_HULL_TOP = mat("Wood_Hull", "#7d4a28", 0.42, coat=0.3)
M_HULL_RAIL = mat("Paint_Rail", "#e8d7b0", 0.5)
M_HULL_BOOT = mat("Paint_Boot", "#efe2c4", 0.5)
M_HULL_BOTTOM = mat("Paint_Bottom", "#6e1f17", 0.55)
M_DECK = mat("Wood_Deck", "#c79a68", 0.7)
M_WOOD_DARK = mat("Wood_Dark", "#5a3a24", 0.6)
M_MAST = mat("Wood_Mast", "#c4a67a", 0.5)
M_SAIL_MAIN = mat("Sail_Main", "#f1e3c4", 0.92)
M_SAIL_JIB = mat("Sail_Jib", "#c4503a", 0.92)
M_ROPE = mat("Rope", "#2a1d14", 0.9)
M_ROPE_LIGHT = mat("Rope_Light", "#a38a5a", 0.95)
M_BRASS = mat("Brass", "#c9a24a", 0.28, metal=1.0)
M_IRON = mat("Iron", "#26231f", 0.45, metal=0.85)
M_SKIN = mat("Skin", "#b97d52", 0.7)
M_SHIRT = mat("Cloth_Red", "#b23a2a", 0.85)
M_TROUSERS = mat("Cloth_Blue", "#2b4a63", 0.9)
M_HAT = mat("Cloth_Straw", "#d7c08a", 0.9)
M_FLAG = mat("Flag", "#d6442a", 0.8)
M_GLASS = mat("Glass_Lit", "#1b2a33", 0.1, metal=0.4, emit="#ffb35a", emit_strength=1.4)
M_LANTERN = mat("Lantern_Glow", "#ffd48a", 0.3, emit="#ff9a2e", emit_strength=6.0)
M_RING_W = mat("Lifering_White", "#e8e2d2", 0.6)
M_RING_R = mat("Lifering_Red", "#c0322a", 0.6)
M_BARREL = mat("Wood_Barrel", "#6f4a2c", 0.7)
M_PLATE = mat("Nameplate", "#4a2a18", 0.5)

ROOT = bpy.data.objects.new("Boat", None)
scene.collection.objects.link(ROOT)
ROOT.location = (0, 0, -DRAFT)


def link(obj, parent=None):
    scene.collection.objects.link(obj)
    obj.parent = parent or ROOT
    return obj


def mesh_obj(name, bm, material=None, parent=None, loc=(0, 0, 0), smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    o.location = loc
    if material:
        me.materials.append(material)
    return link(o, parent)


def modifier(o, kind, **kw):
    m = o.modifiers.new(kind.title(), kind)
    for k, v in kw.items():
        setattr(m, k, v)
    return m


def prim_cyl(name, r1, r2, depth, loc, rot=(0, 0, 0), mat_=None, parent=None, verts=20, bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r1, radius2=r2, depth=depth)
    o = mesh_obj(name, bm, mat_, parent, loc)
    o.rotation_euler = rot
    if bevel:
        modifier(o, "BEVEL", width=bevel, segments=2, limit_method="ANGLE")
    return o


def prim_box(name, size, loc, rot=(0, 0, 0), mat_=None, parent=None, bevel=0.015):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
    o = mesh_obj(name, bm, mat_, parent, loc, smooth=False)
    o.rotation_euler = rot
    if bevel:
        modifier(o, "BEVEL", width=bevel, segments=3, limit_method="ANGLE", angle_limit=math.radians(30))
    return o


def prim_sphere(name, r, loc, scale=(1, 1, 1), mat_=None, parent=None, seg=18, rings=12):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    for v in bm.verts:
        v.co.x *= scale[0]; v.co.y *= scale[1]; v.co.z *= scale[2]
    return mesh_obj(name, bm, mat_, parent, loc)


def prim_torus(name, R, r, loc, rot=(0, 0, 0), mat_=None, parent=None, major=40, minor=8):
    bm = bmesh.new()
    verts = []
    for i in range(major):
        a = i / major * math.tau
        c = Vector((math.cos(a) * R, math.sin(a) * R, 0))
        n = Vector((math.cos(a), math.sin(a), 0))
        ring = []
        for j in range(minor):
            b = j / minor * math.tau
            ring.append(bm.verts.new(c + n * (math.cos(b) * r) + Vector((0, 0, math.sin(b) * r))))
        verts.append(ring)
    for i in range(major):
        for j in range(minor):
            bm.faces.new((verts[i][j], verts[i][(j + 1) % minor], verts[(i + 1) % major][(j + 1) % minor], verts[(i + 1) % major][j]))
    o = mesh_obj(name, bm, mat_, parent, loc)
    o.rotation_euler = rot
    return o


def tube(name, pts, r, mat_, parent=None, res=6, taper=None):
    """Bevelled-curve rope/spar, converted to a real mesh."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = r
    cu.bevel_resolution = 2
    cu.resolution_u = res
    sp = cu.splines.new("POLY" if len(pts) == 2 else "NURBS")
    sp.points.add(len(pts) - 1)
    for p, c in zip(sp.points, pts):
        p.co = (c[0], c[1], c[2], 1)
    if len(pts) > 2:
        sp.order_u = min(4, len(pts))
        sp.use_endpoint_u = True
    cu.materials.append(mat_)
    o = bpy.data.objects.new(name, cu)
    link(o, parent)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.convert(target="MESH")
    o.select_set(False)
    return o


# ------------------------------------------------------------- hull geometry
def plan_x(u):
    if u < 0.58:
        return B * (0.66 + 0.34 * math.sin(u / 0.58 * math.pi * 0.5))
    return B * max(0.0, math.cos(min((u - 0.58) / 0.42, 1) * math.pi * 0.5)) ** 0.78


def sheer(u):
    return 0.62 + 0.42 * u * u + 0.16 * (1 - u) ** 3


def depth(u):
    return 0.78 * (1 - u ** 3 * 0.88) * (0.72 + 0.28 * math.sin(math.pi * min(u + 0.12, 1)))


def hull_pt(u, s, strake=0.0, k=1.0):
    b = plan_x(u) * k
    top, d = sheer(u), depth(u)
    flare = 1 + 0.09 * (1 - abs(s)) * (1 - u * 0.5)
    return Vector((b * s * flare * (1 + strake), L * (u - 0.5), top - d * (1 - abs(s) ** 2.3)))


def build_hull():
    N, M = 130, 64  # stations x rows (every 2nd pair of rows steps out = clinker strakes)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    grid = []
    for i in range(N + 1):
        u = i / N
        row = []
        for j in range(M + 1):
            s = j / M * 2 - 1
            # overlapping planks: each strake steps out 1.4cm
            row.append(bm.verts.new(hull_pt(u, s, strake=0.010 * ((j // 3) % 2))))
        grid.append(row)
    faces = []
    for i in range(N):
        for j in range(M):
            f = bm.faces.new((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]))
            f.smooth = True
            for loop, (uu, vv) in zip(f.loops, [(i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j)]):
                loop[uv].uv = (uu / N * 3.0, vv / M)
            faces.append(f)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    # flat transom closing the stern
    stern = [grid[0][j] for j in range(M + 1)]
    try:
        bm.faces.new(stern)
    except ValueError:
        pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # paint bands by face height: anti-fouling, boot stripe, topsides, rubbing strake
    me_mats = [M_HULL_TOP, M_HULL_BOTTOM, M_HULL_BOOT, M_HULL_RAIL]
    # remember each quad's row so the rubbing strake follows the sheer line exactly
    rows = {}
    for i in range(N):
        for j in range(M):
            pass
    for f in bm.faces:
        c = f.calc_center_median()
        wl = DRAFT + math.sin(c.y * 2.4) * 0.02
        # |s| of the face centre recovered from the sheer-relative height
        top = sheer((c.y / L) + 0.5)
        near_top = (top - c.z) < 0.115 and (top - c.z) > 0.03
        if c.z < wl - 0.07:
            f.material_index = 1
        elif c.z < wl + 0.04:
            f.material_index = 2
        elif near_top:
            f.material_index = 3
        else:
            f.material_index = 0
    me = bpy.data.meshes.new("Hull")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    for m_ in me_mats:
        me.materials.append(m_)
    o = bpy.data.objects.new("Hull", me)
    link(o)
    modifier(o, "SOLIDIFY", thickness=0.05, offset=-1.0)
    modifier(o, "SUBSURF", levels=1, render_levels=1)
    return o


def build_hull_mask():
    """Closed volume of the hull below the deck. On the web it writes depth only, so the ocean is never drawn inside the boat."""
    N, M = 30, 14
    bm = bmesh.new()
    g = []
    for i in range(N + 1):
        u = 0.02 + 0.96 * i / N
        row = []
        for j in range(M + 1):
            p = hull_pt(u, j / M * 2 - 1, 0.0, 0.93)
            p.z = min(p.z, sheer(u) - 0.1)
            row.append(bm.verts.new(p))
        g.append(row)
    for i in range(N):
        for j in range(M):
            bm.faces.new((g[i][j], g[i][j + 1], g[i + 1][j + 1], g[i + 1][j]))
        bm.faces.new((g[i][0], g[i + 1][0], g[i + 1][M], g[i][M]))  # lid
    bm.faces.new([g[0][j] for j in range(M + 1)])
    bm.faces.new([g[N][j] for j in reversed(range(M + 1))])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj("Hull_Mask", bm, mat("Mask", "#000000"), smooth=False)


def build_deck():
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    N = 56
    bw = 0.115  # board width
    gap = 0.006
    nb = int(B / bw) + 2
    for k in range(-nb, nb):
        x0, x1 = k * bw + gap / 2, (k + 1) * bw - gap / 2
        prev = None
        for i in range(N + 1):
            u = 0.01 + 0.98 * i / N
            lim = plan_x(u) * 0.975
            a, b_ = max(min(x0, lim), -lim), max(min(x1, lim), -lim)
            if b_ - a < 0.004:
                prev = None
                continue
            y = L * (u - 0.5)
            zc = lambda x: sheer(u) - 0.045 + 0.05 * (1 - (x / max(plan_x(u), 1e-3)) ** 2)
            pair = (bm.verts.new((a, y, zc(a))), bm.verts.new((b_, y, zc(b_))))
            if prev:
                f = bm.faces.new((prev[0], prev[1], pair[1], pair[0]))
                for loop in f.loops:
                    loop[uvl].uv = (loop.vert.co.y * 0.4 + ((k * 7919) % 13) / 13 * 5, loop.vert.co.x / (bw * 6))
            prev = pair
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = mesh_obj("Deck", bm, M_DECK, smooth=False)
    modifier(o, "SOLIDIFY", thickness=0.025, offset=-1.0)
    return o


# ------------------------------------------------------------------- build
hull = build_hull()
build_hull_mask()
build_deck()

# gunwale / toe rail (both sides) + bulwark stanchions
for sgn in (-1, 1):
    pts = [(sgn * plan_x(i / 28), L * (i / 28 - 0.5), sheer(i / 28) + 0.025) for i in range(29)]
    tube(f"Rail_{'P' if sgn < 0 else 'S'}", pts, 0.036, M_HULL_RAIL)
    for i in range(1, 28, 2):
        u = i / 28
        prim_cyl(f"Stanchion_{sgn}_{i}", 0.02, 0.016, 0.22, (sgn * plan_x(u), L * (u - 0.5), sheer(u) + 0.13), mat_=M_BRASS, verts=8)

    tube(f"Lifeline_{sgn}", [(sgn * plan_x(i / 28), L * (i / 28 - 0.5), sheer(i / 28) + 0.22) for i in range(1, 28, 2)], 0.005, M_ROPE_LIGHT)

# stem post and bowsprit
tube("Stem", [(0, L / 2 - 0.04, sheer(1) + 0.4), (0, L / 2 + 0.1, sheer(1) + 0.18), (0, L / 2 + 0.12, sheer(1) - 0.2), (0, L / 2, sheer(1) - depth(1) + 0.02)], 0.048, M_WOOD_DARK)
prim_cyl("Bowsprit", 0.04, 0.026, 1.35, (0, L / 2 + 0.35, sheer(1) + 0.38), rot=(math.radians(-90 + 10), 0, 0), mat_=M_WOOD_DARK)

# transom nameplate (a slightly proud panel on the stern)
prim_box("Nameplate", (0.9, 0.03, 0.26), (0, -L / 2 - 0.022, 0.4), mat_=M_PLATE, bevel=0.01)

# mast, boom, gaff
MAST_Y = -0.15
mast = prim_cyl("Mast", 0.085, 0.045, 4.6, (0, MAST_Y, 2.3), mat_=M_MAST, verts=24)
for z in (0.9, 1.7, 2.6):
    prim_torus(f"MastBand_{z}", 0.095 - z * 0.01, 0.014, (0, MAST_Y, z), mat_=M_BRASS, major=24, minor=6)
prim_sphere("MastCap", 0.07, (0, MAST_Y, 4.72), mat_=M_BRASS)
prim_cyl("Boom", 0.045, 0.036, 2.0, (0, MAST_Y - 1.0, 0.98), rot=(math.radians(90), 0, 0), mat_=M_MAST)
prim_box("Gooseneck", (0.12, 0.12, 0.1), (0, MAST_Y, 0.98), mat_=M_BRASS, bevel=0.02)


def sail_obj(name, mat_, foot, height, taper, y0, direction, bulge, base_bulge=0.3):
    """Cloth grid with three shape keys: calm shape, full billow, and fluttering."""
    N = 34
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    vs = {}
    for i in range(N + 1):
        for j in range(N + 1):
            u, v = i / N, j / N
            vs[(i, j)] = bm.verts.new((0, y0 + direction * u * foot * (1 - v * taper), v * height))
    for i in range(N):
        for j in range(N):
            f = bm.faces.new((vs[(i, j)], vs[(i + 1, j)], vs[(i + 1, j + 1)], vs[(i, j + 1)]))
            for loop in f.loops:
                idx = [k for k, vv in vs.items() if vv == loop.vert][0]
                loop[uvl].uv = (idx[0] / N, idx[1] / N)
    o = mesh_obj(name, bm, mat_, loc=(0, 0, 0))
    me = o.data
    me.materials[0].use_backface_culling = False
    o.shape_key_add(name="Basis")

    def shape(key, amount, flutter):
        sk = o.shape_key_add(name=key)
        for idx, v in enumerate(me.vertices):
            i, j = divmod(idx, N + 1)
            u, w = i / N, j / N
            body = math.sin(math.pi * u) * max(math.sin(math.pi * min(w * 1.02, 1)), 0) ** 0.7
            edge = max(0, (u - 0.55) / 0.45) * max(0, min((w - 0.1) / 0.8, 1))
            flut = (math.sin(u * 9 + w * 4) * 0.045 + math.sin(u * 17 + w * 7) * 0.018) * edge * flutter
            rip = math.sin(w * 11 + u * 3) * 0.012 * min(u / 0.4, 1)
            sk.data[idx].co.x = body * amount + flut + rip
    # Basis already holds the calm shape
    for idx, v in enumerate(me.vertices):
        i, j = divmod(idx, N + 1)
        u, w = i / N, j / N
        body = math.sin(math.pi * u) * max(math.sin(math.pi * min(w * 1.02, 1)), 0) ** 0.7
        me.shape_keys.key_blocks["Basis"].data[idx].co.x = body * bulge * base_bulge
    shape("Billow", bulge * 1.0, 0.0)
    shape("Flutter", bulge * 0.7, 1.0)
    me.update()
    for p in me.polygons:
        p.use_smooth = True
    return o


sail_main = sail_obj("Sail_Main", M_SAIL_MAIN, foot=2.0, height=4.0, taper=0.8, y0=MAST_Y - 0.04, direction=-1, bulge=0.55)
sail_main.location = (0, 0, 1.04)
sail_jib = sail_obj("Sail_Jib", M_SAIL_JIB, foot=2.0, height=3.3, taper=0.9, y0=0.55, direction=1, bulge=0.36)
sail_jib.location = (0, 0, 0.98)

# flag with a wave shape key
fl = bmesh.new()
fv = {}
for i in range(15):
    for j in range(3):
        fv[(i, j)] = fl.verts.new((0, MAST_Y - i / 14 * 0.62, 4.5 + j / 2 * 0.3))
for i in range(14):
    for j in range(2):
        fl.faces.new((fv[(i, j)], fv[(i + 1, j)], fv[(i + 1, j + 1)], fv[(i, j + 1)]))
flag = mesh_obj("Flag", fl, M_FLAG)
flag.data.materials[0].use_backface_culling = False
flag.shape_key_add(name="Basis")
sk = flag.shape_key_add(name="Wave")
for idx in range(len(flag.data.vertices)):
    i = idx // 3
    x = i / 14
    sk.data[idx].co.x = math.sin(x * 11) * 0.07 * x + math.sin(x * 5) * 0.03 * x
# standing + running rigging
top = (0, MAST_Y, 4.55)
tube("Forestay", [top, (0, 1.1, 2.9), (0, L / 2 + 0.7, sheer(1) + 0.5)], 0.009, M_ROPE)
tube("Backstay", [top, (0, -1.9, 2.5), (0, -L / 2 + 0.05, sheer(0) + 0.1)], 0.009, M_ROPE)
for sgn in (-1, 1):
    for dy in (0.35, -0.45):
        tube(f"Shroud_{sgn}_{dy}", [(0, MAST_Y, 4.3), (sgn * 0.3, MAST_Y + dy * 0.6, 2.2), (sgn * (plan_x(0.55) + 0.02), MAST_Y + dy, sheer(0.55) + 0.02)], 0.007, M_ROPE)
    for k in range(1, 7):
        f = k / 7
        z = 0.8 + (1 - f) * 2.9
        tube(f"Ratline_{sgn}_{k}", [(sgn * (0.1 + f * 0.55), MAST_Y + 0.3 - f * 0.1, z), (sgn * (0.12 + f * 0.57), MAST_Y - 0.5 + f * 0.1, z)], 0.005, M_ROPE_LIGHT)
tube("Mainsheet", [(0, MAST_Y - 2.0, 0.98), (0.15, MAST_Y - 2.4, 0.5), (0.35, MAST_Y - 2.2, sheer(0.2) + 0.02)], 0.008, M_ROPE_LIGHT)

# deckhouse with window cut-outs (boolean) and lit glass
DH_Y = -0.62
house = prim_box("Deckhouse", (0.95, 0.8, 0.4), (0, DH_Y, sheer(0.12) + 0.2), mat_=M_WOOD_DARK, bevel=0.02)
cut = []
for sgn in (-1, 1):
    cut.append(prim_box(f"cut{sgn}", (0.2, 0.5, 0.2), (sgn * 0.48, DH_Y, sheer(0.12) + 0.24), bevel=0))
cut.append(prim_box("cutA", (0.4, 0.2, 0.22), (0, DH_Y - 0.4, sheer(0.12) + 0.24), bevel=0))
for c in cut:
    m_ = house.modifiers.new("Win", "BOOLEAN")
    m_.operation = "DIFFERENCE"; m_.object = c; m_.solver = "EXACT"
    c.hide_render = True; c.display_type = "WIRE"
bpy.context.view_layer.update()
prim_box("HouseRoof", (1.1, 0.95, 0.07), (0, DH_Y, sheer(0.12) + 0.43), mat_=M_WOOD_DARK, bevel=0.02)
for sgn in (-1, 1):
    prim_box(f"Glass{sgn}", (0.02, 0.5, 0.2), (sgn * 0.45, DH_Y, sheer(0.12) + 0.24), mat_=M_GLASS, bevel=0)
prim_box("GlassA", (0.4, 0.02, 0.22), (0, DH_Y - 0.37, sheer(0.12) + 0.24), mat_=M_GLASS, bevel=0)
prim_torus("LifeRingW", 0.14, 0.04, (0.5, DH_Y + 0.3, sheer(0.12) + 0.24), rot=(0, math.radians(90), 0), mat_=M_RING_W, major=28, minor=8)
for k in range(4):
    a = k * math.pi / 2
    prim_box(f"LifeRingR{k}", (0.05, 0.06, 0.06), (0.53, DH_Y + 0.3 + math.cos(a) * 0.14, sheer(0.12) + 0.24 + math.sin(a) * 0.14), mat_=M_RING_R, bevel=0.005)

# deck gear: barrels with iron hoops, crates, coiled line, cleats, anchor
for k, (x, y) in enumerate([(-0.38, -0.05), (0.38, 0.25)]):
    prim_cyl(f"Barrel{k}", 0.19, 0.19, 0.42, (x, y, sheer(0.5) + 0.2), mat_=M_BARREL, verts=24, bevel=0.012)
    for dz in (-0.12, 0.12):
        prim_torus(f"Hoop{k}{dz}", 0.205, 0.012, (x, y, sheer(0.5) + 0.2 + dz), mat_=M_IRON, major=28, minor=6)
prim_box("Crate", (0.34, 0.34, 0.28), (-0.35, 0.95, sheer(0.7) + 0.14), rot=(0, 0, 0.4), mat_=M_WOOD_DARK, bevel=0.02)
prim_torus("RopeCoil", 0.15, 0.04, (0.3, 1.1, sheer(0.74) + 0.05), mat_=M_ROPE_LIGHT, major=28, minor=8)
for k, (x, y) in enumerate([(-0.58, 1.5), (0.58, 1.5), (-0.6, -0.4), (0.6, -0.4), (-0.5, -1.9), (0.5, -1.9)]):
    prim_box(f"Cleat{k}", (0.16, 0.06, 0.05), (x, y, sheer(y / L + 0.5) + 0.03), mat_=M_BRASS, bevel=0.012)
anchor = tube("Anchor", [(0.34, L / 2 - 0.55, sheer(0.9) + 0.25), (0.34, L / 2 - 0.55, sheer(0.9) - 0.1)], 0.014, M_IRON)
prim_torus("AnchorRing", 0.07, 0.012, (0.34, L / 2 - 0.55, sheer(0.9) + 0.3), rot=(math.radians(90), 0, 0), mat_=M_IRON, major=18, minor=5)

# rudder + tiller hinged at the stern (origins sit on the hinge so the web app just rotates them)
from mathutils import Matrix
rud_bm = bmesh.new()
bmesh.ops.create_cube(rud_bm, size=1.0)
for v in rud_bm.verts:
    v.co.x *= 0.035; v.co.y = v.co.y * 0.26 - 0.13; v.co.z = v.co.z * 0.9 - 0.42
rudder = mesh_obj("Rudder", rud_bm, M_WOOD_DARK, smooth=False)
modifier(rudder, "BEVEL", width=0.012, segments=2, limit_method="ANGLE")
rudder.location = (0, -L / 2 - 0.03, 0.32)
HEAD_Z = sheer(0.0) + 0.12
tiller = prim_cyl("Tiller", 0.03, 0.02, 1.0, (0, 0, 0), mat_=M_WOOD_DARK, verts=10)
tiller.data.transform(Matrix.Rotation(math.radians(-90), 4, "X"))
tiller.data.transform(Matrix.Translation((0, 0.5, 0)))
tiller.location = (-0.04, -L / 2 + 0.02, HEAD_Z + 0.2)
prim_sphere("TillerKnob", 0.03, (0, 1.0, 0), mat_=M_BRASS, parent=tiller, seg=10, rings=8)
prim_box("RudderHead", (0.07, 0.12, 0.14), (0, -L / 2 + 0.03, HEAD_Z + 0.06), mat_=M_BRASS, bevel=0.012)
for k in (0.0, -0.35):
    prim_cyl(f"Pintle{k}", 0.014, 0.014, 0.1, (0, -L / 2 - 0.02, 0.34 + k), mat_=M_IRON, verts=8)

# lantern on a hook: glass + cage, hinged from its hanger
lan = bpy.data.objects.new("Lantern", None)
link(lan)
lan.location = (0, L / 2 - 0.25, sheer(1) + 0.74)
prim_cyl("LanternGlass", 0.1, 0.08, 0.22, (0, 0, -0.1), mat_=M_LANTERN, parent=lan, verts=16)
prim_cyl("LanternCap", 0.0, 0.12, 0.1, (0, 0, 0.06), mat_=M_IRON, parent=lan, verts=16)
prim_cyl("LanternBase", 0.11, 0.11, 0.03, (0, 0, -0.23), mat_=M_IRON, parent=lan, verts=16)
for k in range(4):
    a = k * math.pi / 2
    prim_cyl(f"LanternBar{k}", 0.006, 0.006, 0.26, (math.cos(a) * 0.095, math.sin(a) * 0.095, -0.1), mat_=M_IRON, parent=lan, verts=6)
tube("LanternDavit", [(0, L / 2 - 0.25, sheer(1) + 0.02), (0, L / 2 - 0.25, sheer(1) + 0.75), (0, L / 2 - 0.25, sheer(1) + 0.95), (0, L / 2 - 0.25 + 0.0, sheer(1) + 0.98)], 0.016, M_IRON)
tube("LanternChain", [(0, L / 2 - 0.25, sheer(1) + 0.98), (0, L / 2 - 0.25, sheer(1) + 0.86)], 0.006, M_IRON)

# helmsman: rigid parts parented to joints so the web app can lean, turn and steer
def limb(name, p0, p1, r0, r1, mat_, parent, seg=12):
    """Tapered capsule between two points (local to parent)."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=seg, radius1=r0, radius2=r1, depth=d.length)
    for sph, r, z in ((0, r0, -d.length / 2), (1, r1, d.length / 2)):
        res = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=8, radius=r)
        bmesh.ops.translate(bm, verts=res["verts"], vec=(0, 0, z))
    q = Vector((0, 0, 1)).rotation_difference(d.normalized())
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=q.to_matrix())
    return mesh_obj(name, bm, mat_, parent, tuple((p0 + p1) / 2))


HX, HY = -0.27, -L / 2 + 0.62
seat = bpy.data.objects.new("Helm_Torso", None); link(seat); seat.location = (HX, HY, sheer(0.15) + 0.14)
limb("HelmPelvis", (0, -0.02, 0.05), (0, 0.0, 0.2), 0.16, 0.15, M_TROUSERS, seat)
limb("HelmTorso", (0, 0, 0.2), (0, 0.02, 0.62), 0.15, 0.17, M_SHIRT, seat)
limb("HelmNeck", (0, 0.02, 0.66), (0, 0.03, 0.74), 0.05, 0.045, M_SKIN, seat, seg=8)
limb("HelmShoulders", (-0.19, 0.02, 0.62), (0.19, 0.02, 0.62), 0.07, 0.07, M_SHIRT, seat, seg=10)
prim_torus("HelmScarf", 0.085, 0.032, (0, 0.03, 0.7), mat_=M_HAT, parent=seat, major=18, minor=6)
for sgn in (-1, 1):
    limb(f"HelmThigh{sgn}", (sgn * 0.09, 0.0, 0.08), (sgn * 0.1, 0.4, 0.16), 0.075, 0.06, M_TROUSERS, seat)
    limb(f"HelmShin{sgn}", (sgn * 0.1, 0.4, 0.16), (sgn * 0.11, 0.46, -0.2), 0.055, 0.045, M_TROUSERS, seat)
    prim_box(f"HelmBoot{sgn}", (0.09, 0.2, 0.08), (sgn * 0.11, 0.5, -0.24), mat_=M_WOOD_DARK, parent=seat, bevel=0.02)
limb("HelmArmL_up", (-0.2, 0.02, 0.6), (-0.27, 0.12, 0.42), 0.05, 0.045, M_SHIRT, seat, seg=10)
limb("HelmArmL_lo", (-0.27, 0.12, 0.42), (-0.17, 0.3, 0.38), 0.045, 0.036, M_SKIN, seat, seg=10)
prim_sphere("HelmHandL", 0.04, (-0.17, 0.31, 0.38), mat_=M_SKIN, parent=seat, seg=10, rings=8)
head = bpy.data.objects.new("Helm_Head", None); link(head, seat); head.location = (0, 0.03, 0.86)
prim_sphere("HelmFace", 0.105, (0, 0, 0), scale=(0.92, 1, 1.08), mat_=M_SKIN, parent=head)
prim_sphere("HelmNose", 0.022, (0, 0.1, -0.01), mat_=M_SKIN, parent=head, seg=8, rings=6)
prim_sphere("HelmHair", 0.108, (0, -0.02, 0.02), scale=(0.95, 1, 0.9), mat_=M_WOOD_DARK, parent=head)
prim_cyl("HelmHat", 0.1, 0.115, 0.085, (0, 0, 0.1), mat_=M_HAT, parent=head, verts=20)
prim_cyl("HelmBrim", 0.2, 0.2, 0.012, (0, 0, 0.06), mat_=M_HAT, parent=head, verts=28)
prim_torus("HelmHatBand", 0.115, 0.01, (0, 0, 0.075), mat_=M_SHIRT, parent=head, major=20, minor=5)
# steering arm pivots at the right shoulder and reaches the tiller knob
arm = bpy.data.objects.new("Helm_Arm", None); link(arm, seat); arm.location = (0.2, 0.02, 0.6)
limb("HelmArmR_up", (0, 0, 0), (0.1, 0.16, -0.15), 0.05, 0.045, M_SHIRT, arm, seg=10)
limb("HelmArmR_lo", (0.1, 0.16, -0.15), (0.2, 0.34, -0.06), 0.045, 0.036, M_SKIN, arm, seg=10)
prim_sphere("HelmHandR", 0.04, (0.2, 0.35, -0.06), mat_=M_SKIN, parent=arm, seg=10, rings=8)

# ------------------------------------------------------------------ export
for o in bpy.data.objects:
    o.select_set(False)

glb_dir = os.path.dirname(os.path.abspath(OUT_GLB))
os.makedirs(glb_dir, exist_ok=True)
bpy.ops.export_scene.gltf(
    filepath=OUT_GLB,
    export_format="GLB",
    export_apply=True,
    export_yup=True,
    export_morph=True,
    export_cameras=False,
    export_lights=False,
    export_materials="EXPORT",
)
print("EXPORTED", OUT_GLB, os.path.getsize(OUT_GLB) // 1024, "KB")

if OUT_BLEND:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(OUT_BLEND))

# ------------------------------------------------------------------ preview
if OUT_PNG:
    for o in bpy.data.objects:
        if o.name in ("Hull_Mask",) or o.name.startswith("cut"):
            o.hide_render = True
    world = bpy.data.worlds.new("W")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    sky = nt.nodes.new("ShaderNodeTexSky")
    try:
        sky.sky_type = "NISHITA"; sky.sun_elevation = math.radians(22); sky.sun_rotation = math.radians(215)
    except Exception:
        pass
    nt.links.new(sky.outputs[0], nt.nodes["Background"].inputs[0])
    nt.nodes["Background"].inputs[1].default_value = 1.0
    # water plane for context
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=2, y_segments=2, size=40)
    sea = mesh_obj("Sea", bm, mat("Sea", "#0e4650", 0.12, coat=0.0), parent=ROOT)
    sea.location = (0, 0, 0)
    cam_d = bpy.data.cameras.new("Cam"); cam_d.lens = 38
    cam = bpy.data.objects.new("Cam", cam_d); scene.collection.objects.link(cam)
    scene.camera = cam
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 28
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = -1.0
    nt.nodes["Background"].inputs[1].default_value = 0.8
    base, ext = os.path.splitext(os.path.abspath(OUT_PNG))
    views = {"stern": ((-6.2, -8.6, 3.0), (0, 0.2, 1.7)), "bow": ((5.5, 8.2, 2.4), (0, 0.0, 1.4)), "deck": ((-2.2, -4.2, 2.6), (0, -1.0, 0.7)), "water": ((-7.5, 1.0, 0.7), (0, 0.0, 1.6))}
    for vname, (cloc, target) in views.items():
        cam.location = cloc
        cam.rotation_euler = (Vector(target) - Vector(cloc)).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = f"{base}_{vname}{ext}"
        bpy.ops.render.render(write_still=True)
        print("RENDERED", scene.render.filepath)
