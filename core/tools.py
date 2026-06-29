"""RenderKit's capability layer for Blender — shared by the MCP server and the
standalone agent. Handlers turn requests into `bpy` code and run it over the
bridge. run_blender_code is the escape hatch: arbitrary bpy for anything the
named tools don't cover.
"""
from __future__ import annotations

import json
import os
import tempfile
import urllib.request

from core.bridge import BlenderBridge, BridgeError

_SHOT_PATH = os.path.join(tempfile.gettempdir(), "renderkit_view.png")


def get_scene_info(bridge: BlenderBridge) -> str:
    try:
        return json.dumps(bridge.get_scene_info(), indent=2)
    except BridgeError as e:
        return str(e)


def get_object_info(bridge: BlenderBridge, name: str) -> str:
    try:
        return json.dumps(bridge.get_object_info(name), indent=2)
    except BridgeError as e:
        return str(e)


def run_blender_code(bridge: BlenderBridge, code: str) -> str:
    try:
        bridge.run_code(code if "import bpy" in code else "import bpy\n" + code)
        return "Executed."
    except BridgeError as e:
        return str(e)


def _run(bridge: BlenderBridge, body: str) -> str:
    try:
        bridge.run_code("import bpy\n" + body)
        return "Done."
    except BridgeError as e:
        return str(e)


def add_primitive(bridge: BlenderBridge, kind: str, name: str,
                  location=(0, 0, 0), scale=(1, 1, 1)) -> str:
    op = {"cube": "primitive_cube_add", "uv_sphere": "primitive_uv_sphere_add",
          "cylinder": "primitive_cylinder_add", "cone": "primitive_cone_add",
          "plane": "primitive_plane_add", "torus": "primitive_torus_add",
          "monkey": "primitive_monkey_add"}.get(kind)
    if not op:
        return f"Unknown primitive {kind!r}."
    lines = [f"bpy.ops.mesh.{op}(location={tuple(location)})",
             "o = bpy.context.active_object", f"o.name = {name!r}",
             f"o.scale = {tuple(scale)}"]
    if kind in ("uv_sphere", "cone", "torus", "monkey"):
        lines.append("bpy.ops.object.shade_smooth()")
    return _run(bridge, "\n".join(lines)).replace("Done.", f"Added {kind} '{name}'.")


def add_material(bridge: BlenderBridge, obj: str, color=(0.8, 0.1, 0.1),
                 metallic: float = 0.0, roughness: float = 0.5) -> str:
    r, g, b = color
    body = (f"m = bpy.data.materials.new({obj + '_mat'!r}); m.use_nodes = True\n"
            f"bsdf = m.node_tree.nodes['Principled BSDF']\n"
            f"bsdf.inputs['Base Color'].default_value = ({r},{g},{b},1)\n"
            f"bsdf.inputs['Metallic'].default_value = {metallic}\n"
            f"bsdf.inputs['Roughness'].default_value = {roughness}\n"
            f"ob = bpy.data.objects[{obj!r}]; ob.data.materials.clear(); ob.data.materials.append(m)")
    return _run(bridge, body).replace("Done.", f"Material applied to '{obj}'.")


def three_point_lighting(bridge: BlenderBridge, target=(0, 0, 0),
                         power: float = 1000.0) -> str:
    tx, ty, tz = target
    body = f"""
def _l(n,k,loc,e):
    d=bpy.data.lights.new(n,type=k); d.energy=e
    o=bpy.data.objects.new(n,d); bpy.context.collection.objects.link(o); o.location=loc
    c=bpy.data.objects.new(n+'_aim',None); bpy.context.collection.objects.link(c); c.location=({tx},{ty},{tz})
    t=o.constraints.new('TRACK_TO'); t.target=c
_l('Key','AREA',({tx+4},{ty-4},{tz+5}),{power})
_l('Fill','AREA',({tx-5},{ty-2},{tz+3}),{power*0.4})
_l('Rim','AREA',({tx},{ty+6},{tz+4}),{power*0.8})
""".strip()
    return _run(bridge, body).replace("Done.", "Three-point lighting added.")


def add_camera(bridge: BlenderBridge, location=(7, -7, 5), target=(0, 0, 0),
               lens: float = 50.0) -> str:
    tx, ty, tz = target
    body = f"""
cd=bpy.data.cameras.new('Camera'); cd.lens={lens}
cam=bpy.data.objects.new('Camera',cd); bpy.context.collection.objects.link(cam); cam.location={tuple(location)}
tgt=bpy.data.objects.new('CamTarget',None); bpy.context.collection.objects.link(tgt); tgt.location=({tx},{ty},{tz})
cam.constraints.new('TRACK_TO').target=tgt
bpy.context.scene.camera=cam
""".strip()
    return _run(bridge, body).replace("Done.", "Camera added and set active.")


def turntable(bridge: BlenderBridge, target=(0, 0, 0), radius: float = 8.0,
              height: float = 3.0, frames: int = 120) -> str:
    tx, ty, tz = target
    body = f"""
import math as _m
sc=bpy.context.scene; sc.frame_start=1; sc.frame_end={frames}
cam=sc.camera
if cam is None: raise RuntimeError('Add a camera first (add_camera).')
for f in range(1,{frames}+1):
    a=(f-1)/{frames}*2*_m.pi
    cam.location=({tx}+{radius}*_m.cos(a),{ty}+{radius}*_m.sin(a),{tz}+{height})
    cam.keyframe_insert('location',frame=f)
for fc in cam.animation_data.action.fcurves:
    for kp in fc.keyframe_points: kp.interpolation='LINEAR'
""".strip()
    return _run(bridge, body).replace("Done.", f"Turntable keyframed ({frames} frames).")


def setup_render(bridge: BlenderBridge, output_path: str, engine: str = "EEVEE",
                 animation: bool = True, resolution=(1920, 1080),
                 fps: int = 30, samples: int = 64) -> str:
    w, h = resolution
    out = output_path.replace("\\", "\\\\")
    body = f"""
sc=bpy.context.scene
ids={{e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items}}
if {engine!r}=='CYCLES':
    sc.render.engine='CYCLES'; sc.cycles.samples={samples}
else:
    sc.render.engine=next((i for i in ('BLENDER_EEVEE_NEXT','BLENDER_EEVEE') if i in ids), sc.render.engine)
sc.render.resolution_x={w}; sc.render.resolution_y={h}; sc.render.fps={fps}
sc.render.filepath={out!r}
sc.render.image_settings.file_format='FFMPEG' if {animation} else 'PNG'
if {animation}:
    sc.render.ffmpeg.format='MPEG4'; sc.render.ffmpeg.codec='H264'
""".strip()
    return _run(bridge, body).replace("Done.", f"Render configured -> {output_path}.")


def render(bridge: BlenderBridge, animation: bool = True) -> str:
    call = "bpy.ops.render.render(animation=True)" if animation else \
           "bpy.ops.render.render(write_still=True)"
    return _run(bridge, call).replace("Done.", "Render finished.")


def screenshot(bridge: BlenderBridge, max_size: int = 800):
    """OpenGL-render the current view to a PNG and return the bytes so Claude can
    SEE the scene and iterate. Returns bytes on success, an error string on failure."""
    w = int(max_size)
    h = int(max_size * 9 / 16)
    path = _SHOT_PATH.replace("\\", "\\\\")
    code = f"""
import bpy
sc = bpy.context.scene
ox, oy = sc.render.resolution_x, sc.render.resolution_y
of = sc.render.image_settings.file_format
sc.render.resolution_x = {w}; sc.render.resolution_y = {h}
sc.render.image_settings.file_format = 'PNG'
try:
    bpy.ops.render.opengl(write_still=False)
    bpy.data.images['Render Result'].save_render(filepath=r"{path}")
finally:
    sc.render.resolution_x = ox; sc.render.resolution_y = oy
    sc.render.image_settings.file_format = of
"""
    try:
        bridge.run_code("import bpy\n" + code)
    except BridgeError as e:
        return str(e)
    if not os.path.exists(_SHOT_PATH):
        return "Screenshot failed (no image written). The scene may have no camera/view."
    with open(_SHOT_PATH, "rb") as f:
        return f.read()


# --- Asset import (real environments + models) -------------------------------

def search_hdris(bridge: BlenderBridge, category: str = "", limit: int = 15) -> str:
    """Search PolyHaven for HDRI environment slugs (free). Pick one for set_hdri.
    Categories include: studio, outdoor, indoor, sunrise-sunset, night, nature."""
    url = "https://api.polyhaven.com/assets?type=hdris"
    if category:
        url += f"&categories={category}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "renderkit/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        return f"PolyHaven search failed: {e}"
    slugs = list(data.keys())[:int(limit)]
    return ("HDRIs (use a slug with set_hdri): " + ", ".join(slugs)) if slugs \
        else "No HDRIs found for that category."


def set_hdri(bridge: BlenderBridge, slug: str, res: str = "2k", strength: float = 1.0) -> str:
    """Download a PolyHaven HDRI and set it as the world environment — real
    image-based lighting and reflections. res = 1k|2k|4k."""
    url = f"https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/{res}/{slug}_{res}.hdr"
    code = f"""
import bpy, os, tempfile, urllib.request
path = os.path.join(tempfile.gettempdir(), "{slug}_{res}.hdr")
if not os.path.exists(path):
    _req = urllib.request.Request("{url}", headers={{"User-Agent": "renderkit/1.0"}})
    with urllib.request.urlopen(_req) as _r, open(path, "wb") as _f:
        _f.write(_r.read())
w = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = w
w.use_nodes = True
nt = w.node_tree
nt.nodes.clear()
bg = nt.nodes.new("ShaderNodeBackground"); bg.inputs["Strength"].default_value = {strength}
env = nt.nodes.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(path)
out = nt.nodes.new("ShaderNodeOutputWorld")
nt.links.new(env.outputs["Color"], bg.inputs["Color"])
nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
"""
    try:
        bridge.run_code("import bpy\n" + code)
    except BridgeError as e:
        return str(e)
    return f"World HDRI set to '{slug}' ({res})."


def import_model_url(bridge: BlenderBridge, url: str) -> str:
    """Download and import a 3D model from a direct URL (.glb/.gltf/.obj/.fbx)."""
    ext = url.lower().split("?")[0].rsplit(".", 1)[-1]
    importer = {"glb": "bpy.ops.import_scene.gltf(filepath=p)",
                "gltf": "bpy.ops.import_scene.gltf(filepath=p)",
                "obj": "bpy.ops.wm.obj_import(filepath=p)",
                "fbx": "bpy.ops.import_scene.fbx(filepath=p)"}.get(ext)
    if not importer:
        return f"Unsupported model type '.{ext}' (use glb/gltf/obj/fbx)."
    code = f"""
import bpy, os, tempfile, urllib.request
p = os.path.join(tempfile.gettempdir(), "rk_model.{ext}")
_req = urllib.request.Request("{url}", headers={{"User-Agent": "renderkit/1.0"}})
with urllib.request.urlopen(_req) as _r, open(p, "wb") as _f:
    _f.write(_r.read())
{importer}
"""
    try:
        bridge.run_code("import bpy\n" + code)
    except BridgeError as e:
        return str(e)
    return f"Imported model from {url}."


# --- Animation (keyframes + cinematic camera moves) --------------------------

def keyframe(bridge: BlenderBridge, obj: str, frame: int, location=None,
             rotation=None, scale=None) -> str:
    """Insert keyframes on an object's transform at a frame. rotation is degrees
    (XYZ). Call repeatedly at different frames to animate; the scene end extends
    to cover the frame. Set the engine/output with setup_render, then render."""
    import math as _m
    lines = [f"o=bpy.data.objects[{obj!r}]", f"f={int(frame)}",
             "sc=bpy.context.scene; sc.frame_end=max(sc.frame_end,f)"]
    if location is not None:
        lines += [f"o.location={tuple(location)}", "o.keyframe_insert('location',frame=f)"]
    if rotation is not None:
        rad = tuple(_m.radians(a) for a in rotation)
        lines += [f"o.rotation_euler={rad}", "o.keyframe_insert('rotation_euler',frame=f)"]
    if scale is not None:
        lines += [f"o.scale={tuple(scale)}", "o.keyframe_insert('scale',frame=f)"]
    if len(lines) == 3:
        return "Nothing to keyframe — pass location, rotation, and/or scale."
    return _run(bridge, "\n".join(lines)).replace("Done.", f"Keyframed '{obj}' at frame {frame}.")


def camera_move(bridge: BlenderBridge, kind: str, target=(0, 0, 0),
                start_frame: int = 1, end_frame: int = 120, amount: float | None = None) -> str:
    """Keyframe a cinematic move on the active camera between two frames.
    kind: push_in | pull_out | orbit | crane_up | crane_down | dolly.
    amount: push/pull = fraction (0.4 = 40% closer/farther), orbit = degrees,
    crane = metres, dolly = metres sideways. Camera keeps facing the target."""
    defaults = {"push_in": 0.4, "pull_out": 0.5, "orbit": 90.0,
                "crane_up": 3.0, "crane_down": 3.0, "dolly": 4.0}
    amt = defaults.get(kind, 1.0) if amount is None else float(amount)
    tx, ty, tz = target
    header = (f"KIND={kind!r}\nSTART={int(start_frame)}\nEND={int(end_frame)}\n"
              f"AMT={amt}\nTGT=({tx},{ty},{tz})\n")
    body = r'''
import bpy, math
from mathutils import Vector
sc=bpy.context.scene
cam=sc.camera
if cam is None: raise RuntimeError("Add a camera first (add_camera).")
sc.frame_start=START; sc.frame_end=max(sc.frame_end,END)
tgt=Vector(TGT)
p0=cam.location.copy(); off=p0-tgt
if KIND=="push_in":
    ps=p0; pe=tgt+off*(1.0-AMT)
elif KIND=="pull_out":
    ps=p0; pe=tgt+off*(1.0+AMT)
elif KIND=="orbit":
    a=math.radians(AMT); c=math.cos(a); s=math.sin(a)
    ps=p0; pe=tgt+Vector((off.x*c-off.y*s, off.x*s+off.y*c, off.z))
elif KIND=="crane_up":
    ps=p0; pe=p0+Vector((0,0,AMT))
elif KIND=="crane_down":
    ps=p0; pe=p0-Vector((0,0,AMT))
elif KIND=="dolly":
    flat=Vector((off.x,off.y,0)); perp=Vector((-flat.y,flat.x,0))
    if perp.length>0: perp.normalize()
    ps=p0; pe=p0+perp*AMT
else:
    raise RuntimeError("unknown kind: "+KIND)
cam.location=ps; cam.keyframe_insert("location",frame=START)
cam.location=pe; cam.keyframe_insert("location",frame=END)
if not any(c.type=="TRACK_TO" for c in cam.constraints):
    t=bpy.data.objects.get("CamTarget")
    if t is None:
        t=bpy.data.objects.new("CamTarget",None); bpy.context.collection.objects.link(t)
    t.location=tgt
    cam.constraints.new("TRACK_TO").target=t
'''
    try:
        bridge.run_code("import bpy\n" + header + body)
    except BridgeError as e:
        return str(e)
    return f"Camera '{kind}' keyframed (frames {start_frame}-{end_frame})."


# --- Modifiers + material presets + PBR textures -----------------------------

def add_modifier(bridge: BlenderBridge, obj: str, kind: str, levels: int = 2,
                 width: float = 0.1, segments: int = 3, count: int = 3,
                 offset=(1.5, 0, 0), thickness: float = 0.1, axis: str = "X",
                 operation: str = "DIFFERENCE", other: str = "") -> str:
    """Add a modifier: subsurf | bevel | array | solidify | mirror | wireframe |
    boolean. boolean needs `other` (the cutter object) and `operation`
    (DIFFERENCE|UNION|INTERSECT)."""
    k = kind.lower()
    body = [f"o=bpy.data.objects[{obj!r}]"]
    if k in ("subsurf", "subdivision"):
        body += [f"m=o.modifiers.new('Subsurf','SUBSURF'); m.levels={int(levels)}; m.render_levels={int(levels)}",
                 "for _p in o.data.polygons: _p.use_smooth=True"]
    elif k == "bevel":
        body += [f"m=o.modifiers.new('Bevel','BEVEL'); m.width={width}; m.segments={int(segments)}"]
    elif k == "array":
        body += [f"m=o.modifiers.new('Array','ARRAY'); m.count={int(count)}; m.relative_offset_displace={tuple(offset)}"]
    elif k == "solidify":
        body += [f"m=o.modifiers.new('Solidify','SOLIDIFY'); m.thickness={thickness}"]
    elif k == "mirror":
        ax = {"X": 0, "Y": 1, "Z": 2}.get(axis.upper(), 0)
        body += ["m=o.modifiers.new('Mirror','MIRROR')", "m.use_axis=(False,False,False)",
                 f"m.use_axis[{ax}]=True"]
    elif k == "wireframe":
        body += [f"m=o.modifiers.new('Wireframe','WIREFRAME'); m.thickness={thickness}"]
    elif k == "boolean":
        if not other:
            return "boolean needs `other` (the cutter object name)."
        body += [f"oc=bpy.data.objects.get({other!r})",
                 f"assert oc is not None, 'no such object: {other}'",
                 f"m=o.modifiers.new('Boolean','BOOLEAN'); m.operation={operation.upper()!r}; m.object=oc"]
    else:
        return f"Unknown modifier {kind!r} (subsurf|bevel|array|solidify|mirror|wireframe|boolean)."
    return _run(bridge, "\n".join(body)).replace("Done.", f"Added {k} modifier to '{obj}'.")


def material_preset(bridge: BlenderBridge, obj: str, preset: str, color=None) -> str:
    """Apply a realistic material preset: gold | silver | chrome | copper | glass |
    emission | plastic | rubber. `color` (RGB 0..1) tints plastic/rubber/emission."""
    p = preset.lower()
    metals = {"gold": (1.0, 0.766, 0.336, 0.12), "silver": (0.95, 0.95, 0.95, 0.06),
              "chrome": (0.8, 0.8, 0.85, 0.04), "copper": (0.95, 0.64, 0.54, 0.2)}
    body = [f"ob=bpy.data.objects[{obj!r}]",
            f"m=bpy.data.materials.new({obj + '_' + p!r}); m.use_nodes=True",
            "b=m.node_tree.nodes['Principled BSDF']",
            "def _set(n,v):\n    if n in b.inputs: b.inputs[n].default_value=v"]
    if p in metals:
        r, g, bl, rough = metals[p]
        body += [f"_set('Base Color',({r},{g},{bl},1))", "_set('Metallic',1.0)",
                 f"_set('Roughness',{rough})"]
    elif p == "glass":
        body += ["_set('Transmission Weight',1.0)", "_set('Transmission',1.0)",
                 "_set('Roughness',0.0)", "_set('IOR',1.45)"]
    elif p == "emission":
        c = color or (1.0, 0.9, 0.6)
        body += [f"_set('Emission Color',({c[0]},{c[1]},{c[2]},1))",
                 f"_set('Emission',({c[0]},{c[1]},{c[2]},1))", "_set('Emission Strength',5.0)"]
    elif p == "plastic":
        c = color or (0.1, 0.4, 0.9)
        body += [f"_set('Base Color',({c[0]},{c[1]},{c[2]},1))", "_set('Metallic',0.0)",
                 "_set('Roughness',0.35)"]
    elif p == "rubber":
        c = color or (0.04, 0.04, 0.04)
        body += [f"_set('Base Color',({c[0]},{c[1]},{c[2]},1))", "_set('Roughness',0.9)"]
    else:
        return f"Unknown preset {preset!r} (gold|silver|chrome|copper|glass|emission|plastic|rubber)."
    body += ["ob.data.materials.clear(); ob.data.materials.append(m)"]
    return _run(bridge, "\n".join(body)).replace("Done.", f"Applied '{p}' preset to '{obj}'.")


def search_textures(bridge: BlenderBridge, category: str = "", limit: int = 15) -> str:
    """Search PolyHaven for free PBR texture slugs (categories: wood, metal, brick,
    concrete, fabric, stone, ground, ...). Pick one for apply_texture."""
    url = "https://api.polyhaven.com/assets?type=textures"
    if category:
        url += f"&categories={category}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "renderkit/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        return f"PolyHaven search failed: {e}"
    slugs = list(data.keys())[:int(limit)]
    return ("Textures (use a slug with apply_texture): " + ", ".join(slugs)) if slugs \
        else "No textures found for that category."


def apply_texture(bridge: BlenderBridge, obj: str, slug: str, res: str = "2k") -> str:
    """Download a PolyHaven PBR texture set (diffuse/roughness/normal) and build a
    Principled material on the object — real surface detail. res = 1k|2k|4k."""
    header = f"OBJ={obj!r}\nSLUG={slug!r}\nRES={res!r}\n"
    body = r'''
import bpy, os, tempfile, json, urllib.request
def _get(u):
    r=urllib.request.Request(u, headers={"User-Agent":"renderkit/1.0"})
    return urllib.request.urlopen(r, timeout=60)
files=json.loads(_get("https://api.polyhaven.com/files/"+SLUG).read().decode())
def _pick(mapname):
    d=files.get(mapname)
    if not d: return None
    rr=d.get(RES) or next(iter(d.values()))
    for fmt in ("jpg","png","exr"):
        if fmt in rr: return rr[fmt]["url"]
    return next(iter(rr.values()))["url"]
maps={"diffuse":_pick("Diffuse"),"rough":_pick("Rough"),
      "normal":_pick("nor_gl") or _pick("nor_dx"),"disp":_pick("Displacement")}
tmp=tempfile.gettempdir(); loaded={}
for k,u in maps.items():
    if not u: continue
    ext=u.split("?")[0].rsplit(".",1)[-1]
    p=os.path.join(tmp,"rk_"+SLUG+"_"+k+"."+ext)
    if not os.path.exists(p):
        with _get(u) as _r, open(p,"wb") as _f: _f.write(_r.read())
    loaded[k]=p
ob=bpy.data.objects[OBJ]
m=bpy.data.materials.new(OBJ+"_tex"); m.use_nodes=True
nt=m.node_tree; b=nt.nodes["Principled BSDF"]
def _img(p, noncolor=False):
    n=nt.nodes.new("ShaderNodeTexImage"); n.image=bpy.data.images.load(p)
    if noncolor: n.image.colorspace_settings.name="Non-Color"
    return n
if "diffuse" in loaded: nt.links.new(_img(loaded["diffuse"]).outputs["Color"], b.inputs["Base Color"])
if "rough" in loaded: nt.links.new(_img(loaded["rough"],True).outputs["Color"], b.inputs["Roughness"])
if "normal" in loaded:
    nm=nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(_img(loaded["normal"],True).outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
ob.data.materials.clear(); ob.data.materials.append(m)
'''
    try:
        bridge.run_code("import bpy\n" + header + body)
    except BridgeError as e:
        return str(e)
    return f"Applied PolyHaven texture '{slug}' ({res}) to '{obj}'."


_HANDLERS = {
    "get_scene_info": get_scene_info, "get_object_info": get_object_info,
    "run_blender_code": run_blender_code, "add_primitive": add_primitive,
    "add_material": add_material, "three_point_lighting": three_point_lighting,
    "add_camera": add_camera, "turntable": turntable, "setup_render": setup_render,
    "render": render, "screenshot": screenshot,
    "search_hdris": search_hdris, "set_hdri": set_hdri, "import_model_url": import_model_url,
    "keyframe": keyframe, "camera_move": camera_move, "add_modifier": add_modifier,
    "material_preset": material_preset, "search_textures": search_textures,
    "apply_texture": apply_texture,
}

_VEC3 = {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}

TOOLS = [
    {"name": "get_scene_info", "description": "Get the current Blender scene: objects, materials, etc.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_object_info", "description": "Inspect one object by name.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "run_blender_code",
     "description": "Run arbitrary Blender Python (bpy). Use for anything the other tools don't cover — modeling, modifiers, node graphs, animation.",
     "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}},
    {"name": "add_primitive", "description": "Add a primitive: cube|uv_sphere|cylinder|cone|plane|torus|monkey.",
     "input_schema": {"type": "object", "properties": {
         "kind": {"type": "string"}, "name": {"type": "string"},
         "location": _VEC3, "scale": _VEC3}, "required": ["kind", "name"]}},
    {"name": "add_material", "description": "Create a Principled BSDF material and assign it to an object.",
     "input_schema": {"type": "object", "properties": {
         "obj": {"type": "string"}, "color": _VEC3,
         "metallic": {"type": "number"}, "roughness": {"type": "number"}}, "required": ["obj"]}},
    {"name": "three_point_lighting", "description": "Add key/fill/rim lights aimed at a target point.",
     "input_schema": {"type": "object", "properties": {"target": _VEC3, "power": {"type": "number"}}, "required": []}},
    {"name": "add_camera", "description": "Add a camera that tracks a target and make it active.",
     "input_schema": {"type": "object", "properties": {
         "location": _VEC3, "target": _VEC3, "lens": {"type": "number"}}, "required": []}},
    {"name": "turntable", "description": "Keyframe the active camera in a 360-degree orbit around a target.",
     "input_schema": {"type": "object", "properties": {
         "target": _VEC3, "radius": {"type": "number"}, "height": {"type": "number"},
         "frames": {"type": "integer"}}, "required": []}},
    {"name": "setup_render", "description": "Configure resolution/fps/engine (EEVEE or CYCLES) and output path.",
     "input_schema": {"type": "object", "properties": {
         "output_path": {"type": "string"}, "engine": {"type": "string"},
         "animation": {"type": "boolean"}}, "required": ["output_path"]}},
    {"name": "render", "description": "Render the scene (animation=True for the full frame range, else a still).",
     "input_schema": {"type": "object", "properties": {"animation": {"type": "boolean"}}, "required": []}},
    {"name": "screenshot",
     "description": "Capture the current Blender view as an image and SEE it. Use this to check your work and iterate on composition, lighting, and materials.",
     "input_schema": {"type": "object", "properties": {"max_size": {"type": "integer", "description": "longest edge in px, default 800"}}, "required": []}},
    {"name": "search_hdris",
     "description": "Search PolyHaven for free HDRI environment slugs (categories: studio, outdoor, indoor, sunrise-sunset, night, nature). Pick one for set_hdri.",
     "input_schema": {"type": "object", "properties": {
         "category": {"type": "string"}, "limit": {"type": "integer"}}, "required": []}},
    {"name": "set_hdri",
     "description": "Set a PolyHaven HDRI as the world environment for real image-based lighting + reflections. res = 1k|2k|4k.",
     "input_schema": {"type": "object", "properties": {
         "slug": {"type": "string"}, "res": {"type": "string"}, "strength": {"type": "number"}},
      "required": ["slug"]}},
    {"name": "import_model_url",
     "description": "Download and import a 3D model from a direct URL (.glb/.gltf/.obj/.fbx).",
     "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "keyframe",
     "description": "Animate an object: insert keyframes for location/rotation(degrees)/scale at a frame. Call at multiple frames to build motion. Then setup_render + render the animation.",
     "input_schema": {"type": "object", "properties": {
         "obj": {"type": "string"}, "frame": {"type": "integer"},
         "location": _VEC3, "rotation": _VEC3, "scale": _VEC3}, "required": ["obj", "frame"]}},
    {"name": "camera_move",
     "description": "Keyframe a cinematic camera move between two frames: push_in|pull_out|orbit|crane_up|crane_down|dolly. amount = fraction for push/pull (0.4=40%), degrees for orbit, metres for crane/dolly. Camera keeps facing target. Needs a camera (add_camera).",
     "input_schema": {"type": "object", "properties": {
         "kind": {"type": "string"}, "target": _VEC3,
         "start_frame": {"type": "integer"}, "end_frame": {"type": "integer"},
         "amount": {"type": "number"}}, "required": ["kind"]}},
    {"name": "add_modifier",
     "description": "Add a modifier to an object: subsurf (smooth, levels), bevel (width/segments), array (count/offset), solidify (thickness), mirror (axis), wireframe, boolean (needs other + operation DIFFERENCE|UNION|INTERSECT). Non-destructive modeling.",
     "input_schema": {"type": "object", "properties": {
         "obj": {"type": "string"}, "kind": {"type": "string"},
         "levels": {"type": "integer"}, "width": {"type": "number"}, "segments": {"type": "integer"},
         "count": {"type": "integer"}, "offset": _VEC3, "thickness": {"type": "number"},
         "axis": {"type": "string"}, "operation": {"type": "string"}, "other": {"type": "string"}},
      "required": ["obj", "kind"]}},
    {"name": "material_preset",
     "description": "Apply a realistic material preset to an object: gold|silver|chrome|copper|glass|emission|plastic|rubber. Pass color (RGB 0..1) to tint plastic/rubber/emission. Faster than wiring nodes by hand.",
     "input_schema": {"type": "object", "properties": {
         "obj": {"type": "string"}, "preset": {"type": "string"}, "color": _VEC3},
      "required": ["obj", "preset"]}},
    {"name": "search_textures",
     "description": "Search PolyHaven for free PBR texture slugs (categories: wood, metal, brick, concrete, fabric, stone, ground). Pick one for apply_texture.",
     "input_schema": {"type": "object", "properties": {
         "category": {"type": "string"}, "limit": {"type": "integer"}}, "required": []}},
    {"name": "apply_texture",
     "description": "Download a PolyHaven PBR texture set (diffuse+roughness+normal) and build a material on the object — real surface detail. res = 1k|2k|4k.",
     "input_schema": {"type": "object", "properties": {
         "obj": {"type": "string"}, "slug": {"type": "string"}, "res": {"type": "string"}},
      "required": ["obj", "slug"]}},
]


def dispatch(bridge: BlenderBridge, name: str, arguments: dict) -> str:
    handler = _HANDLERS.get(name)
    if handler is None:
        return f"Unknown tool: {name}"
    try:
        return handler(bridge, **(arguments or {}))
    except Exception as e:
        return f"Error in {name}: {e}"
