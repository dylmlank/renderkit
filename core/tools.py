"""RenderKit's capability layer for Blender — shared by the MCP server and the
standalone agent. Handlers turn requests into `bpy` code and run it over the
bridge. run_blender_code is the escape hatch: arbitrary bpy for anything the
named tools don't cover.
"""
from __future__ import annotations

import json

from core.bridge import BlenderBridge, BridgeError


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


_HANDLERS = {
    "get_scene_info": get_scene_info, "get_object_info": get_object_info,
    "run_blender_code": run_blender_code, "add_primitive": add_primitive,
    "add_material": add_material, "three_point_lighting": three_point_lighting,
    "add_camera": add_camera, "turntable": turntable, "setup_render": setup_render,
    "render": render,
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
]


def dispatch(bridge: BlenderBridge, name: str, arguments: dict) -> str:
    handler = _HANDLERS.get(name)
    if handler is None:
        return f"Unknown tool: {name}"
    try:
        return handler(bridge, **(arguments or {}))
    except Exception as e:
        return f"Error in {name}: {e}"
