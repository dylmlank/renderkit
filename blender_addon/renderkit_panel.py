"""RenderKit — in-Blender Claude panel.

Adds a "RenderKit" tab to the 3D-viewport sidebar (press N) with a prompt box and a
Generate button. Type what you want ("a low-poly tree on a plane, soft studio
lighting, then a slow push-in camera") and Claude builds it directly in this Blender
session, calling RenderKit's tools (which run bpy in-process).

Install: Edit > Preferences > Add-ons > (this file is in scripts/addons) > enable
"RenderKit Panel". Then open Add-on Preferences and paste your Anthropic API key.

No key yet? The panel still loads — it just tells you to add one. Get a key at
https://console.anthropic.com . The key is stored in Blender's add-on preferences.
"""
from __future__ import annotations

import base64
import os
import sys

import bpy

bl_info = {
    "name": "RenderKit Panel",
    "author": "RenderKit",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar (N) > RenderKit",
    "description": "Prompt Claude to model, light, and animate directly in Blender.",
    "category": "3D View",
}

DEFAULT_RENDERKIT_DIR = r"E:\renderkit"
API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM = (
    "You are RenderKit, working inside the user's live Blender session. Build what "
    "they ask using the tools: primitives, modifiers, materials/presets, PolyHaven "
    "HDRIs and PBR textures, three-point lighting, cameras, keyframes and cinematic "
    "camera moves. Use get_scene_info to see what's there, and screenshot to check "
    "your work and iterate on composition/lighting. Prefer the named tools; use "
    "run_blender_code for anything they don't cover. Keep replies short; act with "
    "the tools."
)


# --- RenderKit tool layer, run in-process against this bpy session -------------

class InProcessBridge:
    """Mimics RenderKit's socket bridge but executes bpy here in Blender."""

    def run_code(self, code):
        exec(compile(code, "<renderkit>", "exec"), {"__name__": "__renderkit__"})

    def get_scene_info(self):
        sc = bpy.context.scene
        return {
            "name": sc.name,
            "frame_range": [sc.frame_start, sc.frame_end],
            "objects": [{"name": o.name, "type": o.type,
                         "location": [round(c, 3) for c in o.location]} for o in sc.objects],
            "materials": [m.name for m in bpy.data.materials],
        }

    def get_object_info(self, name):
        o = bpy.data.objects.get(name)
        if not o:
            return {"error": f"no object named {name!r}"}
        mats = [m.name for m in o.data.materials] if getattr(o.data, "materials", None) else []
        return {"name": o.name, "type": o.type,
                "location": [round(c, 3) for c in o.location],
                "rotation_deg": [round(c * 57.2958, 1) for c in o.rotation_euler],
                "scale": [round(c, 3) for c in o.scale], "materials": mats}


def _load_tools(renderkit_dir):
    """Import RenderKit's TOOLS + dispatch from its repo (added to sys.path)."""
    rk = renderkit_dir or DEFAULT_RENDERKIT_DIR
    if rk not in sys.path:
        sys.path.insert(0, rk)
    import core.tools as T  # noqa: E402  (renderkit's capability layer)
    return T


# --- Claude REST client (uses Blender's bundled requests) ---------------------

def _claude(api_key, model, tools, messages):
    import requests
    resp = requests.post(
        API_URL,
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": model, "max_tokens": 4096, "system": SYSTEM,
              "tools": tools, "thinking": {"type": "adaptive"}, "messages": messages},
        timeout=180,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Claude API {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def run_generation(prompt, api_key, model, renderkit_dir, log):
    T = _load_tools(renderkit_dir)
    bridge = InProcessBridge()
    messages = [{"role": "user", "content": prompt}]
    for _ in range(16):
        data = _claude(api_key, model, T.TOOLS, messages)
        messages.append({"role": "assistant", "content": data["content"]})
        for blk in data["content"]:
            if blk.get("type") == "text" and blk.get("text", "").strip():
                log(blk["text"].strip())
        if data.get("stop_reason") != "tool_use":
            return
        results = []
        for blk in data["content"]:
            if blk.get("type") != "tool_use":
                continue
            out = T.dispatch(bridge, blk["name"], blk.get("input") or {})
            log(f"  · {blk['name']}")
            if isinstance(out, (bytes, bytearray)):
                content = [{"type": "image", "source": {"type": "base64",
                            "media_type": "image/png",
                            "data": base64.b64encode(bytes(out)).decode()}}]
            else:
                content = str(out)
            results.append({"type": "tool_result", "tool_use_id": blk["id"], "content": content})
        messages.append({"role": "user", "content": results})
    log("Stopped after the step limit.")


# --- Blender UI ---------------------------------------------------------------

class RenderKitPrefs(bpy.types.AddonPreferences):
    bl_idname = __name__

    api_key: bpy.props.StringProperty(
        name="Anthropic API key", subtype="PASSWORD",
        description="Get one at console.anthropic.com — stored in Blender's preferences")
    model: bpy.props.StringProperty(name="Model", default="claude-opus-4-8")
    renderkit_dir: bpy.props.StringProperty(
        name="RenderKit folder", subtype="DIR_PATH", default=DEFAULT_RENDERKIT_DIR,
        description="Path to the renderkit repo (for its tool library)")

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "api_key")
        if not self.api_key:
            col.label(text="Paste your Anthropic API key above to enable generation.",
                      icon="ERROR")
        col.prop(self, "model")
        col.prop(self, "renderkit_dir")


class RENDERKIT_OT_generate(bpy.types.Operator):
    bl_idname = "renderkit.generate"
    bl_label = "Generate"
    bl_description = "Send the prompt to Claude and build it in this scene"

    def execute(self, context):
        prefs = context.preferences.addons[__name__].preferences
        prompt = context.scene.renderkit_prompt.strip()
        if not prompt:
            self.report({"WARNING"}, "Type a prompt first.")
            return {"CANCELLED"}
        if not prefs.api_key:
            self.report({"ERROR"}, "Add your Anthropic API key in Add-on Preferences.")
            return {"CANCELLED"}

        lines = []

        def log(msg):
            lines.append(msg)
            print("[RenderKit]", msg)

        context.scene.renderkit_status = "Generating..."
        try:
            run_generation(prompt, prefs.api_key, prefs.model, prefs.renderkit_dir, log)
        except Exception as e:  # surface failures in the UI instead of a traceback
            self.report({"ERROR"}, str(e)[:200])
            context.scene.renderkit_status = f"Error: {str(e)[:80]}"
            return {"CANCELLED"}
        context.scene.renderkit_status = (lines[-1][:120] if lines else "Done.")
        self.report({"INFO"}, "RenderKit done.")
        return {"FINISHED"}


class RENDERKIT_PT_panel(bpy.types.Panel):
    bl_label = "RenderKit"
    bl_idname = "RENDERKIT_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RenderKit"

    def draw(self, context):
        layout = self.layout
        prefs = context.preferences.addons[__name__].preferences
        if not prefs.api_key:
            box = layout.box()
            box.label(text="No API key set", icon="ERROR")
            box.label(text="Add it in Add-on Preferences.")
        layout.label(text="Prompt:")
        layout.prop(context.scene, "renderkit_prompt", text="")
        layout.operator("renderkit.generate", icon="PLAY")
        if context.scene.renderkit_status:
            layout.label(text=context.scene.renderkit_status, icon="INFO")


_classes = (RenderKitPrefs, RENDERKIT_OT_generate, RENDERKIT_PT_panel)


def register():
    for c in _classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.renderkit_prompt = bpy.props.StringProperty(
        name="Prompt", description="What should Claude build?",
        default="a low-poly tree on a plane with soft studio lighting")
    bpy.types.Scene.renderkit_status = bpy.props.StringProperty(default="")


def unregister():
    del bpy.types.Scene.renderkit_prompt
    del bpy.types.Scene.renderkit_status
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
