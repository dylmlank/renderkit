"""RenderKit standalone agent — describe models or shots and Claude builds them
in Blender through the same tools the MCP server exposes.

    set ANTHROPIC_API_KEY=...
    python agent.py "model a low-poly spaceship, light it, and orbit a camera around it"

Anthropic SDK manual tool-use loop, claude-opus-4-8, adaptive thinking.
"""
from __future__ import annotations

import sys

import anthropic

from config import MODEL
from core import BlenderBridge, TOOLS, dispatch

SYSTEM = (
    "You are RenderKit, a 3D assistant wired into the user's running Blender session. "
    "You can read the scene and build models and cinematics: add primitives and "
    "materials, set up three-point lighting, place a tracking camera, keyframe a "
    "turntable orbit, configure the render, and run arbitrary bpy via run_blender_code "
    "for anything else (meshes, modifiers, node graphs, animation). Inspect the scene "
    "with get_scene_info before assuming what exists. Prefer the named tools; fall back "
    "to run_blender_code for custom geometry. Act with tools; keep prose short."
)


def run(bridge, client, user_text, history):
    history.append({"role": "user", "content": user_text})
    while True:
        resp = client.messages.create(
            model=MODEL, max_tokens=8192, thinking={"type": "adaptive"},
            system=SYSTEM, tools=TOOLS, messages=history,
        )
        history.append({"role": "assistant", "content": resp.content})
        for block in resp.content:
            if block.type == "text" and block.text.strip():
                print(f"\n{block.text.strip()}\n")
        if resp.stop_reason != "tool_use":
            return history
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                out = dispatch(bridge, block.name, block.input)
                preview = out if len(out) < 200 else out[:200] + "..."
                print(f"  · {block.name} -> {preview}")
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
        history.append({"role": "user", "content": results})


def main() -> int:
    bridge = BlenderBridge()
    client = anthropic.Anthropic()
    history: list = []
    if len(sys.argv) > 1:
        run(bridge, client, " ".join(sys.argv[1:]), history)
        return 0
    print("RenderKit agent — describe what to build in Blender (Ctrl+C to quit).")
    try:
        while True:
            text = input("\n> ").strip()
            if text:
                run(bridge, client, text, history)
    except (KeyboardInterrupt, EOFError):
        print("\nbye")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
