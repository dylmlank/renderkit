"""RenderKit MCP server — Blender modeling + cinematics as MCP tools for Claude
Desktop. Each tool wraps a core.tools handler (shared with agent.py).

claude_desktop_config.json:

    "renderkit": {
      "command": "C:\\\\Users\\\\dylan\\\\.local\\\\bin\\\\uv.exe",
      "args": ["run", "--python", "3.12", "--with", "mcp",
               "python", "E:\\\\renderkit\\\\mcp_server.py"]
    }
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from core import BlenderBridge
import core.tools as T

mcp = FastMCP("renderkit")
bridge = BlenderBridge()


def _kw(**kw):
    return {k: v for k, v in kw.items() if v is not None}


@mcp.tool()
def get_scene_info() -> str:
    """Get the current Blender scene (objects, materials, etc.)."""
    return T.get_scene_info(bridge)


@mcp.tool()
def get_object_info(name: str) -> str:
    """Inspect one object by name."""
    return T.get_object_info(bridge, name)


@mcp.tool()
def run_blender_code(code: str) -> str:
    """Run arbitrary Blender Python (bpy) — modeling, modifiers, nodes, animation."""
    return T.run_blender_code(bridge, code)


@mcp.tool()
def add_primitive(kind: str, name: str, location: list | None = None,
                  scale: list | None = None) -> str:
    """Add a primitive: cube|uv_sphere|cylinder|cone|plane|torus|monkey."""
    return T.add_primitive(bridge, kind, name, **_kw(location=location, scale=scale))


@mcp.tool()
def add_material(obj: str, color: list | None = None, metallic: float | None = None,
                 roughness: float | None = None) -> str:
    """Create a Principled BSDF material and assign it to an object."""
    return T.add_material(bridge, obj, **_kw(color=color, metallic=metallic, roughness=roughness))


@mcp.tool()
def three_point_lighting(target: list | None = None, power: float | None = None) -> str:
    """Add key/fill/rim lights aimed at a target point."""
    return T.three_point_lighting(bridge, **_kw(target=target, power=power))


@mcp.tool()
def add_camera(location: list | None = None, target: list | None = None,
               lens: float | None = None) -> str:
    """Add a camera that tracks a target and make it active."""
    return T.add_camera(bridge, **_kw(location=location, target=target, lens=lens))


@mcp.tool()
def turntable(target: list | None = None, radius: float | None = None,
              height: float | None = None, frames: int | None = None) -> str:
    """Keyframe the active camera in a 360-degree orbit around a target."""
    return T.turntable(bridge, **_kw(target=target, radius=radius, height=height, frames=frames))


@mcp.tool()
def setup_render(output_path: str, engine: str = "EEVEE", animation: bool = True) -> str:
    """Configure resolution/fps/engine (EEVEE or CYCLES) and output path."""
    return T.setup_render(bridge, output_path, engine=engine, animation=animation)


@mcp.tool()
def render(animation: bool = True) -> str:
    """Render the scene (animation=True for the frame range, else a still)."""
    return T.render(bridge, animation)


if __name__ == "__main__":
    mcp.run()
