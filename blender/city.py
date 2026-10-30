"""
Pandemonium neon skyline.

  blender --background --python blender/city.py -- public/models/city.glb blender/city.blend

Towers use world-scale UVs (1 UV = 3.4 m) so the web app can tile its lit-window emissive texture on the
Tower_0/1/2 materials (one per neon hue). Neon strips, antennas and beacons are flat emissive materials.
Origin = deck level at the centre of the island (z = 0).
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
OUT_GLB = A[0] if A else "city.glb"
OUT_BLEND = A[1] if len(A) > 1 else ""

lib.reset()
S = Scene("City")
rnd = random.Random(21)


def flat(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0):
    m = Mat(name)
    kw = {"Base Color": color, "Roughness": rough, "Metallic": metal}
    if emit:
        kw.update({"Emission Color": emit, "Emission Strength": strength})
    m.set(**kw)
    return m


HUES = ["#ff2ea6", "#27e6ff", "#9a5bff"]
WALL = [flat(f"Tower_{i}", "#30343e", 0.29, 0.48) for i in range(3)]
# the third cornice family burns warm sodium yellow, a minority accent among the pinks and cyans
NEON = [flat(f"Neon_{i}", h, 0.4, 0.0, h, 7.0) for i, h in enumerate(["#ff2ea6", "#27e6ff", "#ffc93c"])]
METAL = flat("Rooftop", "#626369", 0.57, 0.65)
BEACON = flat("Beacon", "#ff2a1a", 0.4, 0.0, "#ff2a1a", 10.0)
CROWN = flat("Crown", "#16172a", 0.3, 0.9)
parts = []


def add(o):
    parts.append(o)
    return o


def taper(name, w, d, h, top, loc, mat, bevel=0.03, sides=4, rot=0.0):
    """Prism (4 sides → box, more → cylinder) tapering to `top` × footprint."""
    bm = bmesh.new()
    if sides == 4:
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            s = top if v.co.z > 0 else 1.0
            v.co.x *= w * s; v.co.y *= d * s; v.co.z = (v.co.z + 0.5) * h
    else:
        bmesh.ops.create_cone(bm, cap_ends=True, segments=sides, radius1=w / 2, radius2=w / 2 * top, depth=h)
        for v in bm.verts:
            v.co.z += h / 2
    o = S.mesh(name, bm, mat, loc=loc, smooth=(sides != 4))
    o.rotation_euler = (0, 0, rot)
    if bevel:
        S.modifier(o, "BEVEL", width=bevel, segments=2, limit_method="ANGLE", angle_limit=math.radians(35))
    return add(o)


FLOOR = 0.85  # one storey; 4 storeys per window-texture tile (3.4 m), so heights land on whole floors


def cap(i, x, y, w, d, z, neon, plant=True):
    """A tidy roof: neon cornice, dark parapet rim, and one centred plant room. Returns the roof height."""
    add(S.box(f"Cornice{i}_{z:.1f}", (w + 0.07, d + 0.07, 0.07), (x, y, z - 0.12), material=neon, bevel=0.01))
    add(S.box(f"Parapet{i}_{z:.1f}", (w + 0.04, d + 0.04, 0.2), (x, y, z + 0.1), material=CROWN, bevel=0.015))
    if plant:
        add(S.box(f"Plant{i}_{z:.1f}", (w * 0.42, d * 0.42, 0.42), (x, y, z + 0.41), material=METAL, bevel=0.02))
        return z + 0.62
    return z + 0.2


def mast(i, x, y, z, ht):
    add(S.cyl(f"Mast{i}", 0.03, 0.05, ht, (x, y, z + ht / 2), material=METAL, verts=8))
    add(S.sphere(f"Bcn{i}", 0.06, (x, y, z + ht + 0.05), material=BEACON, seg=10, rings=8))
    return z + ht


def build_tower(i, x, y, h, w, d, k, arche):
    mat, neon = WALL[k], NEON[k]
    if arche == "slab":
        taper(f"T{i}", w, d, h, 1.0, (x, y, 0), mat)
        return cap(i, x, y, w, d, h, neon, plant=h > 5)
    if arche == "setback":
        # two or three clean tiers, each stepping in evenly and stopping on a whole floor
        tiers = 3 if h > 10 else 2
        z, s, top = 0.0, 1.0, 0.0
        for t in range(tiers):
            th = max(FLOOR * 2, round(h * (0.56 if t == 0 else 0.44 / (tiers - 1)) / FLOOR) * FLOOR)
            taper(f"T{i}s{t}", w * s, d * s, th, 1.0, (x, y, z), mat)
            z += th
            last = t == tiers - 1
            top = cap(i, x, y, w * s, d * s, z, neon, plant=last)
            s -= 0.22
        return top
    # "cyl": a round tower with a shallow dome and a single neon band at its crown
    taper(f"T{i}", w * 1.1, w * 1.1, h, 1.0, (x, y, 0), mat, sides=24)
    add(S.torus(f"NeonRing{i}", w * 0.56, 0.045, (x, y, h - 0.12), material=neon, major=32, minor=6))
    add(S.cyl(f"Dome{i}", w * 0.55, w * 0.18, 0.45, (x, y, h + 0.22), material=CROWN, verts=24))
    return h + 0.45


def hero(i, x, y, h, w, k):
    """The landmark at the centre: a stepped tower finishing in a slim lit spire."""
    top = build_tower(i, x, y, h, w, w, k, "setback")
    add(S.cyl(f"HeroCrown{i}", w * 0.2, w * 0.12, 1.2, (x, y, top + 0.6), material=CROWN, verts=16))
    add(S.torus(f"HeroHalo{i}", w * 0.21, 0.04, (x, y, top + 1.15), material=NEON[1], major=24, minor=6))
    return mast(i, x, y, top + 1.2, 3.2)


towers = []
idx = 0
SPACING = 2.7
for gx in range(-3, 4):
    for gz in range(-3, 4):
        x, y = gx * SPACING, gz * SPACING
        rad = math.hypot(x, y)
        if rad > 9.0:
            continue
        core = math.exp(-((rad / 5.6) ** 2))
        k = idx % 3
        if gx == 0 and gz == 0:
            h = round(17.0 / FLOOR) * FLOOR
            top = hero(idx, x, y, h, 2.0, k)
        else:
            # a smooth rise toward the centre, snapped to whole floors, with a little variety per block
            h = max(FLOOR * 3, round((2.6 + core * 11.5 + rnd.uniform(-0.8, 1.6)) / FLOOR) * FLOOR)
            w = rnd.choice((1.7, 1.9, 2.05))
            d = rnd.choice((1.7, 1.9, 2.05))
            arche = "slab" if h < 6 else ("setback" if h > 9.5 else rnd.choice(("slab", "slab", "cyl")))
            top = build_tower(idx, x, y, h, w, d, k, arche)
            if h > 11 and rnd.random() < 0.6:
                top = mast(idx, x, y, top, rnd.uniform(1.2, 1.8))
        towers.append((x, y, top, k, gx, gz))
        idx += 1

# a few skybridges, only between axis-aligned neighbours, so they meet facades square-on
bridges = 0
for a in range(len(towers)):
    for b in range(a + 1, len(towers)):
        ta, tb = towers[a], towers[b]
        if abs(ta[4] - tb[4]) + abs(ta[5] - tb[5]) != 1 or min(ta[2], tb[2]) < 9 or bridges >= 4:
            continue
        z = round(0.55 * min(ta[2], tb[2]) / FLOOR) * FLOOR
        mid = ((ta[0] + tb[0]) / 2, (ta[1] + tb[1]) / 2, z)
        ang = 0.0 if ta[5] == tb[5] else math.pi / 2
        add(S.box(f"Bridge{bridges}", (SPACING, 0.5, 0.36), mid, (0, 0, ang), material=CROWN, bevel=0.02))
        add(S.box(f"BridgeNeon{bridges}", (SPACING, 0.52, 0.05), (mid[0], mid[1], z - 0.2), (0, 0, ang), material=NEON[tb[3]], bevel=0))
        bridges += 1

city = lib.join(parts, "City")
city.parent = S.root
# world-scale cube-projected UVs: 1 UV unit = 3.4 m (the app tiles its window emissive map on these)
bpy.ops.object.select_all(action="DESELECT")
bpy.context.view_layer.objects.active = city
city.select_set(True)
me = city.data
while me.uv_layers:
    me.uv_layers.remove(me.uv_layers[0])
me.uv_layers.new(name="UVMap")
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.cube_project(cube_size=3.4, scale_to_bounds=False)
bpy.ops.object.mode_set(mode="OBJECT")
print("CITY polys:", len(me.polygons), "slots:", len(city.material_slots), "towers:", len(towers), "bridges:", bridges)

if OUT_BLEND:
    lib.save_blend(OUT_BLEND)
lib.export_glb(OUT_GLB, morph=False)
