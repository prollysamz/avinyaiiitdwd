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
NEON = [flat(f"Neon_{i}", h, 0.4, 0.0, h, 7.0) for i, h in enumerate(HUES)]
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


def build_tower(i, x, y, h, w, d, k):
    mat = WALL[k]
    neon = NEON[k]
    arche = rnd.choice(["slab", "slab", "setback", "cyl", "obelisk", "ziggurat"]) if h > 4.5 else "slab"
    top = 0.0
    if arche == "slab":
        taper(f"T{i}", w, d, h, 1.0, (x, y, 0), mat)
        top = h
        add(S.box(f"Crown{i}", (w * 0.8, d * 0.8, 0.35), (x, y, h + 0.17), material=CROWN, bevel=0.03))
        top += 0.35
    elif arche == "setback":
        h1, h2, h3 = h * 0.55, h * 0.3, h * 0.22
        taper(f"T{i}a", w, d, h1, 1.0, (x, y, 0), mat)
        taper(f"T{i}b", w * 0.74, d * 0.74, h2, 1.0, (x, y, h1), mat)
        taper(f"T{i}c", w * 0.46, d * 0.46, h3, 1.0, (x, y, h1 + h2), mat)
        add(S.box(f"Ring{i}a", (w + 0.1, d + 0.1, 0.1), (x, y, h1), material=neon, bevel=0.01))
        add(S.box(f"Ring{i}b", (w * 0.74 + 0.1, d * 0.74 + 0.1, 0.1), (x, y, h1 + h2), material=neon, bevel=0.01))
        top = h1 + h2 + h3
    elif arche == "cyl":
        taper(f"T{i}", w * 1.15, w * 1.15, h, 0.9, (x, y, 0), mat, sides=18)
        for z in range(1, int(h / 1.4)):
            add(S.torus(f"Band{i}_{z}", w * 0.57 * (1 - 0.1 * z / (h / 1.4)), 0.035, (x, y, z * 1.4), material=CROWN, major=24, minor=5))
        add(S.cyl(f"Dome{i}", w * 0.5, w * 0.2, 0.5, (x, y, h + 0.25), material=CROWN, verts=18))
        top = h + 0.5
        add(S.torus(f"NeonRing{i}", w * 0.58, 0.05, (x, y, h * 0.7), material=neon, major=24, minor=6))
    elif arche == "obelisk":
        taper(f"T{i}", w, d, h, 0.42, (x, y, 0), mat)
        add(S.cyl(f"Spire{i}", w * 0.18, 0.0, 1.6, (x, y, h + 0.8), material=METAL, verts=8))
        top = h + 1.6
    else:  # ziggurat
        tiers = 4
        z = 0.0
        for t in range(tiers):
            th = h / tiers
            s = 1 - t * 0.17
            taper(f"T{i}z{t}", w * s, d * s, th, 0.97, (x, y, z), mat)
            add(S.box(f"Z{i}{t}", (w * s + 0.08, d * s + 0.08, 0.08), (x, y, z + th), material=neon if t % 2 == 0 else CROWN, bevel=0.01))
            z += th
        top = h
    # vertical neon corner strips on some towers
    if rnd.random() < 0.4 and arche in ("slab", "setback"):
        sx = rnd.choice((-1, 1))
        add(S.box(f"Strip{i}", (0.07, 0.07, h * 0.9), (x + sx * w / 2, y + d / 2, h * 0.45), material=neon, bevel=0.01))
    # rooftop plant
    if arche in ("slab", "setback"):
        # Physical curtain-wall mullions and floor spandrels catch the light;
        # windows remain texture-driven to keep the skyline inexpensive.
        facade_top = h if arche == "slab" else h * 0.55
        for side in (-1, 1):
            for q in (-0.25, 0.0, 0.25):
                add(S.box(f"Mullion{i}_{side}_{q}", (0.025, 0.035, facade_top),
                    (x + w * q, y + side * (d / 2 + 0.015), facade_top / 2), material=METAL, bevel=0.005))
            for floor in range(1, int(facade_top / 0.85)):
                add(S.box(f"Spandrel{i}_{side}_{floor}", (w + 0.025, 0.035, 0.055),
                    (x, y + side * (d / 2 + 0.015), floor * 0.85), material=CROWN, bevel=0.005))
    for j in range(rnd.randint(1, 3)):
        add(S.box(f"AC{i}_{j}", (rnd.uniform(0.25, 0.5), rnd.uniform(0.25, 0.5), rnd.uniform(0.2, 0.4)), (x + rnd.uniform(-w, w) * 0.25, y + rnd.uniform(-d, d) * 0.25, top + 0.15), material=METAL, bevel=0.02))
    if rnd.random() < 0.55:
        ah = rnd.uniform(1.4, 3.0)
        add(S.cyl(f"Ant{i}", 0.02, 0.035, ah, (x + w * 0.2, y, top + ah / 2), material=METAL, verts=6))
        add(S.sphere(f"Bcn{i}", 0.045, (x + w * 0.2, y, top + ah + 0.04), material=BEACON, seg=8, rings=6))
    if rnd.random() < 0.3:
        add(S.cyl(f"Tank{i}", 0.28, 0.28, 0.5, (x - w * 0.2, y + d * 0.1, top + 0.35), material=METAL, verts=12))
    return top


towers = []
idx = 0
for gx in range(-4, 5):
    for gz in range(-4, 5):
        x = gx * 2.45 + (rnd.random() - 0.5) * 0.5
        y = gz * 2.45 + (rnd.random() - 0.5) * 0.5
        rad = math.hypot(x, y)
        if rad > 9.4 or (gx == 3 and gz == 3) or rnd.random() < 0.12:
            continue
        core = math.exp(-((rad / 6.3) ** 2))
        h = 2.6 + core * (9 + rnd.random() * 7) + rnd.random() * 2.5
        w, d = 1.2 + rnd.random() * 0.9, 1.2 + rnd.random() * 0.9
        top = build_tower(idx, x, y, h, w, d, idx % 3)
        towers.append((x, y, top, w, d, idx % 3))
        idx += 1

# skybridges between neighbouring tall towers, with a neon underside
bridges = 0
for a in range(len(towers)):
    for b in range(a + 1, len(towers)):
        ta, tb = towers[a], towers[b]
        dist = math.hypot(ta[0] - tb[0], ta[1] - tb[1])
        if dist < 3.1 and min(ta[2], tb[2]) > 6.5 and bridges < 9:
            z = 0.58 * min(ta[2], tb[2])
            mid = ((ta[0] + tb[0]) / 2, (ta[1] + tb[1]) / 2, z)
            ang = math.atan2(tb[1] - ta[1], tb[0] - ta[0])
            o = S.box(f"Bridge{bridges}", (dist - 0.6, 0.42, 0.3), mid, (0, 0, ang), material=WALL[ta[5]], bevel=0.03)
            add(o)
            n = S.box(f"BridgeNeon{bridges}", (dist - 0.62, 0.3, 0.05), (mid[0], mid[1], z - 0.17), (0, 0, ang), material=NEON[tb[5]], bevel=0)
            add(n)
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
