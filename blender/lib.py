"""
Shared Blender pipeline for the Avinya assets.

  * geometry helpers (bmesh primitives, bevelled tubes, boxes)
  * node-based procedural materials
  * atlas baking: base colour, AO, roughness/metal (ORM), tangent normal, emission
  * glTF export (textures embedded as JPEG) and a re-import preview render, so what we
    inspect is the real exported asset.

Blender conventions: 1 unit = 1 m, +Z up, +Y = forward (becomes glTF -Z).
"""
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector


# --------------------------------------------------------------- scene setup
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return [x for x in a if not x.startswith("--")]


# ------------------------------------------------------------------- colours
def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hexcol(h, a=1.0):
    h = h.lstrip("#")
    return (lin(int(h[0:2], 16) / 255), lin(int(h[2:4], 16) / 255), lin(int(h[4:6], 16) / 255), a)


# ------------------------------------------------------------- node material
class Mat:
    """Tiny wrapper to build Principled node graphs without boilerplate."""

    def __init__(self, name):
        self.m = bpy.data.materials.new(name)
        self.m.use_nodes = True
        self.nt = self.m.node_tree
        self.nt.nodes.clear()
        self.out = self.nt.nodes.new("ShaderNodeOutputMaterial")
        self.bsdf = self.nt.nodes.new("ShaderNodeBsdfPrincipled")
        self.nt.links.new(self.bsdf.outputs["BSDF"], self.out.inputs["Surface"])
        self.coord = self.nt.nodes.new("ShaderNodeTexCoord")

    def node(self, kind, **props):
        n = self.nt.nodes.new(kind)
        for k, v in props.items():
            if k == "inputs":
                for name, val in v.items():
                    n.inputs[name].default_value = val
            else:
                setattr(n, k, v)
        return n

    def link(self, a, b):
        self.nt.links.new(a, b)

    def mapping(self, scale=(1, 1, 1), loc=(0, 0, 0), rot=(0, 0, 0), source="Object"):
        n = self.node("ShaderNodeMapping")
        n.inputs["Scale"].default_value = scale
        n.inputs["Location"].default_value = loc
        n.inputs["Rotation"].default_value = rot
        self.link(self.coord.outputs[source], n.inputs["Vector"])
        return n

    def ramp(self, fac, stops, color=True):
        n = self.node("ShaderNodeValToRGB")
        el = n.color_ramp.elements
        while len(el) > len(stops):
            el.remove(el[-1])
        while len(el) < len(stops):
            el.new(0.5)
        for e, (pos, col) in zip(el, stops):
            e.position = pos
            e.color = hexcol(col) if isinstance(col, str) else col
        self.link(fac, n.inputs["Fac"])
        return n

    def math(self, op, a=None, b=None, clamp=False):
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                self.link(v, n.inputs[i])
        return n.outputs[0]

    def mix(self, fac, a, b):
        n = self.node("ShaderNodeMix", data_type="RGBA")
        for idx, v in ((0, fac), (6, a), (7, b)):
            if isinstance(v, (int, float)):
                n.inputs[idx].default_value = v
            elif isinstance(v, (tuple, list)):
                n.inputs[idx].default_value = v
            else:
                self.link(v, n.inputs[idx])
        return n.outputs[2]

    def noise(self, vec, scale, detail=4.0, rough=0.55, distortion=0.0):
        n = self.node("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        n.inputs["Distortion"].default_value = distortion
        self.link(vec, n.inputs["Vector"])
        return n.outputs["Fac"]

    def set(self, **kw):
        for k, v in kw.items():
            sock = self.bsdf.inputs[k]
            if isinstance(v, (int, float)):
                sock.default_value = v
            elif isinstance(v, str):
                sock.default_value = hexcol(v)
            elif isinstance(v, (tuple, list)):
                sock.default_value = v
            else:
                self.link(v, sock)
        return self


# ---------------------------------------------------------- geometry helpers
class Scene:
    def __init__(self, root_name="Root"):
        self.sc = bpy.context.scene
        self.root = bpy.data.objects.new(root_name, None)
        self.sc.collection.objects.link(self.root)

    def link(self, o, parent=None):
        self.sc.collection.objects.link(o)
        o.parent = parent if parent is not None else self.root
        return o

    def mesh(self, name, bm, material=None, parent=None, loc=(0, 0, 0), smooth=True):
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        if smooth:
            for p in me.polygons:
                p.use_smooth = True
        o = bpy.data.objects.new(name, me)
        o.location = loc
        if material is not None:
            me.materials.append(material.m if isinstance(material, Mat) else material)
        return self.link(o, parent)

    def modifier(self, o, kind, **kw):
        m = o.modifiers.new(kind.title(), kind)
        for k, v in kw.items():
            setattr(m, k, v)
        return m

    def cyl(self, name, r1, r2, depth, loc, rot=(0, 0, 0), material=None, parent=None, verts=20, bevel=0.0, caps=True):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=caps, segments=verts, radius1=r1, radius2=r2, depth=depth)
        o = self.mesh(name, bm, material, parent, loc)
        o.rotation_euler = rot
        if bevel:
            self.modifier(o, "BEVEL", width=bevel, segments=2, limit_method="ANGLE")
        return o

    def box(self, name, size, loc, rot=(0, 0, 0), material=None, parent=None, bevel=0.015, seg=3):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
        o = self.mesh(name, bm, material, parent, loc, smooth=False)
        o.rotation_euler = rot
        if bevel:
            self.modifier(o, "BEVEL", width=bevel, segments=seg, limit_method="ANGLE", angle_limit=math.radians(30))
        return o

    def sphere(self, name, r, loc, scale=(1, 1, 1), material=None, parent=None, seg=18, rings=12):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
        for v in bm.verts:
            v.co.x *= scale[0]; v.co.y *= scale[1]; v.co.z *= scale[2]
        return self.mesh(name, bm, material, parent, loc)

    def torus(self, name, R, r, loc, rot=(0, 0, 0), material=None, parent=None, major=40, minor=8):
        bm = bmesh.new()
        rings = []
        for i in range(major):
            a = i / major * math.tau
            c = Vector((math.cos(a) * R, math.sin(a) * R, 0))
            n = Vector((math.cos(a), math.sin(a), 0))
            rings.append([bm.verts.new(c + n * (math.cos(j / minor * math.tau) * r) + Vector((0, 0, math.sin(j / minor * math.tau) * r))) for j in range(minor)])
        for i in range(major):
            for j in range(minor):
                bm.faces.new((rings[i][j], rings[i][(j + 1) % minor], rings[(i + 1) % major][(j + 1) % minor], rings[(i + 1) % major][j]))
        o = self.mesh(name, bm, material, parent, loc)
        o.rotation_euler = rot
        return o

    def tube(self, name, pts, r, material, parent=None, res=6, smooth_curve=True):
        """Bevelled curve → real mesh (ropes, rails, wires)."""
        cu = bpy.data.curves.new(name, "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = r
        cu.bevel_resolution = 2
        cu.resolution_u = res
        if len(pts) == 2 or not smooth_curve:
            sp = cu.splines.new("POLY")
        else:
            sp = cu.splines.new("NURBS")
            sp.order_u = min(4, len(pts))
            sp.use_endpoint_u = True
        sp.points.add(len(pts) - 1)
        for p, c in zip(sp.points, pts):
            p.co = (c[0], c[1], c[2], 1)
        cu.materials.append(material.m if isinstance(material, Mat) else material)
        o = bpy.data.objects.new(name, cu)
        self.link(o, parent)
        bpy.context.view_layer.objects.active = o
        o.select_set(True)
        bpy.ops.object.convert(target="MESH")
        o.select_set(False)
        return o

    def limb(self, name, p0, p1, r0, r1, material, parent=None, seg=12):
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=False, segments=seg, radius1=r0, radius2=r1, depth=d.length)
        for r, z in ((r0, -d.length / 2), (r1, d.length / 2)):
            res = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=8, radius=r)
            bmesh.ops.translate(bm, verts=res["verts"], vec=(0, 0, z))
        q = Vector((0, 0, 1)).rotation_difference(d.normalized())
        bmesh.ops.rotate(bm, verts=bm.verts, matrix=q.to_matrix())
        return self.mesh(name, bm, material, parent, tuple((p0 + p1) / 2))

    def empty(self, name, loc=(0, 0, 0), parent=None):
        e = bpy.data.objects.new(name, None)
        self.link(e, parent)
        e.location = loc
        return e


def apply_modifiers(o):
    """Bake an object's modifier stack into its mesh."""
    if not o.modifiers:
        return o
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    old = o.data
    o.modifiers.clear()
    o.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return o


def join(objs, name):
    """Apply modifiers and merge into one mesh object (keeps one material slot per material)."""
    bpy.ops.object.select_all(action="DESELECT")
    objs = [o for o in objs if o.type == "MESH"]
    for o in objs:
        apply_modifiers(o)
    # world-space-free join: everything shares ROOT as parent, so local == root space
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = name
    o.data.name = name
    # the result inherits the first part's transform; bake it so the origin is the parent's origin
    o.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    o.select_set(False)
    return o


# -------------------------------------------------------------------- baking
def unwrap(o, margin=0.003, angle=66):
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    me = o.data
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    me.uv_layers.new(name="UVMap")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, area_weight=0.6, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=margin)
    bpy.ops.object.mode_set(mode="OBJECT")
    o.select_set(False)


def _setup_cycles(samples=24):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    # Use the installed GPU for atlas generation, with a CPU fallback for machines
    # without a compatible device. Baking stays deterministic with fixed seeds.
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        gpu = False
        for device in prefs.devices:
            device.use = device.type == "OPTIX"
            gpu |= device.use
        if gpu:
            sc.cycles.device = "GPU"
    except (TypeError, RuntimeError):
        pass
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False


def _prep_slots(o, image):
    for slot in o.material_slots:
        nt = slot.material.node_tree
        for n in [n for n in nt.nodes if n.name.startswith("BAKE_TARGET")]:
            nt.nodes.remove(n)
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.name = "BAKE_TARGET"
        tex.image = image
        nt.nodes.active = tex
        for n in nt.nodes:
            n.select = False
        tex.select = True


def _new_image(name, size, srgb, color=(0, 0, 0, 1)):
    img = bpy.data.images.new(name, size, size, alpha=False)
    img.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
    img.generated_color = color
    return img


def _bake(o, kind, **kw):
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.bake(type=kind, margin=10, margin_type="EXTEND", use_clear=True, **kw)
    o.select_set(False)


def _pixels(img):
    a = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(img.size[1], img.size[0], 4)


def _set_pixels(img, arr):
    img.pixels.foreach_set(arr.astype(np.float32).reshape(-1))
    img.update()


def _const_channel_bake(o, size, name, getter):
    """Bake a per-material scalar (metallic etc.) by temporarily routing it into an Emission shader."""
    img = _new_image(name, size, False)
    _prep_slots(o, img)
    saved = []
    for slot in o.material_slots:
        nt = slot.material.node_tree
        out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        prev = [l.from_socket for l in nt.links if l.to_socket == out.inputs["Surface"]]
        em = nt.nodes.new("ShaderNodeEmission")
        v = getter(bsdf)
        if v[1] is not None:  # linked → route the producing socket
            nt.links.new(v[1], em.inputs["Color"])
        else:
            em.inputs["Color"].default_value = (v[0], v[0], v[0], 1)
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        saved.append((nt, out, prev, em))
    _bake(o, "EMIT")
    for nt, out, prev, em in saved:
        nt.nodes.remove(em)
        if prev:
            nt.links.new(prev[0], out.inputs["Surface"])
    return img


def bake_atlas(o, size=2048, ao=True, ao_strength=0.85, emissive=False, name="atlas", samples=24):
    """
    Bake o's procedural materials into one PBR atlas and replace its materials with a single
    glTF-friendly material (base colour, ORM, tangent normal, optional emission).
    """
    _setup_cycles(samples)
    sc = bpy.context.scene

    # 1) base colour (no lighting)
    base = _new_image(f"{name}_base", size, True)
    _prep_slots(o, base)
    _bake(o, "DIFFUSE", pass_filter={"COLOR"})

    # 2) emission (lit windows etc.)
    emit_img = None
    if emissive:
        emit_img = _new_image(f"{name}_emit", size, True)
        _prep_slots(o, emit_img)
        _bake(o, "EMIT")

    # 3) roughness + metallic
    rough = _new_image(f"{name}_rough", size, False)
    _prep_slots(o, rough)
    _bake(o, "ROUGHNESS")
    metal = _const_channel_bake(o, size, f"{name}_metal", lambda b: (b.inputs["Metallic"].default_value, b.inputs["Metallic"].links[0].from_socket if b.inputs["Metallic"].links else None))

    # 4) tangent normal (includes bump nodes)
    normal = _new_image(f"{name}_normal", size, False, (0.5, 0.5, 1.0, 1.0))
    _prep_slots(o, normal)
    _bake(o, "NORMAL", normal_space="TANGENT")

    # 5) ambient occlusion
    ao_img = None
    if ao:
        ao_img = _new_image(f"{name}_ao", size, False, (1, 1, 1, 1))
        _prep_slots(o, ao_img)
        sc.cycles.samples = 48
        _bake(o, "AO")

    # ---- compose final images
    b = _pixels(base)
    r = _pixels(rough)[..., 0]
    m = _pixels(metal)[..., 0]
    a = _pixels(ao_img)[..., 0] if ao_img else np.ones_like(r)
    # AO darkens crevices in the albedo (kept gentle) and is also written to ORM.R
    shade = 1.0 - ao_strength * (1.0 - a)
    b2 = b.copy()
    b2[..., :3] = np.clip(b[..., :3] * shade[..., None], 0, 1)
    b2[..., 3] = 1
    final_base = _new_image(f"{name}_color", size, True)
    _set_pixels(final_base, b2)
    orm = _new_image(f"{name}_orm", size, False)
    arr = np.ones((size, size, 4), dtype=np.float32)
    arr[..., 0] = a; arr[..., 1] = r; arr[..., 2] = m
    _set_pixels(orm, arr)

    # ---- replace materials with a single baked Principled
    for slot in list(o.material_slots):
        pass
    final = Mat(f"{name}_mat")
    nt = final.nt
    final.nt.nodes.remove(final.coord)
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = final_base
    nt.links.new(tex.outputs["Color"], final.bsdf.inputs["Base Color"])
    otex = nt.nodes.new("ShaderNodeTexImage"); otex.image = orm
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(otex.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], final.bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], final.bsdf.inputs["Metallic"])
    ntex = nt.nodes.new("ShaderNodeTexImage"); ntex.image = normal
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(ntex.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], final.bsdf.inputs["Normal"])
    if emit_img is not None:
        etex = nt.nodes.new("ShaderNodeTexImage"); etex.image = emit_img
        nt.links.new(etex.outputs["Color"], final.bsdf.inputs["Emission Color"])
        final.bsdf.inputs["Emission Strength"].default_value = 1.0
    o.data.materials.clear()
    o.data.materials.append(final.m)
    for p in o.data.polygons:
        p.material_index = 0
    for im in (base, rough, metal) + ((ao_img,) if ao_img else ()):  # normal/emission stay: the final material uses them
        bpy.data.images.remove(im)
    return final


# --------------------------------------------------------------------- export
def save_blend(path):
    # Generated bake pixels must be packed; otherwise reopening the .blend can
    # regenerate a blank image despite the GLB containing the correct texture.
    for image in bpy.data.images:
        if image.users and image.has_data:
            image.pack()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(path))


def export_glb(path, morph=True):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    for o in bpy.data.objects:
        o.select_set(False)
    kw = dict(filepath=path, export_format="GLB", export_apply=True, export_yup=True, export_morph=morph,
              export_cameras=False, export_lights=False, export_materials="EXPORT", export_image_format="WEBP",
              export_image_quality=92, export_meshopt_compression_enable=True)
    bpy.ops.export_scene.gltf(**kw)
    print("EXPORTED", path, os.path.getsize(path) // 1024, "KB")


# -------------------------------------------------------------------- preview
def preview_glb(glb, out_base, views, size=(1280, 720), samples=40, sun_az=215, sun_el=24, exposure=-2.2, sea=True, sea_size=60):
    """Re-import the exported file into a clean scene and render it (what you see is what ships)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    bpy.ops.import_scene.gltf(filepath=glb)
    world = bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_elevation = math.radians(sun_el)
    sky.sun_rotation = math.radians(sun_az)
    nt.links.new(sky.outputs[0], nt.nodes["Background"].inputs[0])
    nt.nodes["Background"].inputs[1].default_value = 1.0
    if sea:
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=2, y_segments=2, size=sea_size)
        me = bpy.data.meshes.new("Sea"); bm.to_mesh(me); bm.free()
        s = bpy.data.objects.new("Sea", me); sc.collection.objects.link(s)
        sm = Mat("Sea")
        sm.set(**{"Base Color": "#0e4650", "Roughness": 0.08})
        me.materials.append(sm.m)
    cam_d = bpy.data.cameras.new("Cam"); cam_d.lens = 40
    cam = bpy.data.objects.new("Cam", cam_d); sc.collection.objects.link(cam)
    sc.camera = cam
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.exposure = exposure
    base, ext = os.path.splitext(os.path.abspath(out_base))
    for vname, (loc, target) in views.items():
        cam.location = loc
        cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = f"{base}_{vname}{ext}"
        bpy.ops.render.render(write_still=True)
        print("RENDERED", sc.render.filepath)
