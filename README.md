# RenderKit

Claude-powered **Blender** — model and create cinematics by talking to Claude.
Same two-front-end design as your other kits:

- **MCP server** (`mcp_server.py`) — chat in **Claude Desktop**.
- **Standalone agent** (`agent.py`) — terminal agent via the Anthropic API.

Both drive your running Blender through the **blender-mcp** addon socket (9876),
so there's no second plugin to install.

## What Claude can do

Inspect the scene, then **model** (primitives, materials, and arbitrary `bpy` via
`run_blender_code` for meshes/modifiers/nodes) and build **cinematics** (three-point
lighting, a tracking camera, a 360° turntable orbit, render setup, and render).
The `run_blender_code` tool is the escape hatch — it can do anything Blender's
Python API can, so *"model a low-poly spaceship and orbit a camera around it"*
becomes a sequence of tool calls.

**Vision feedback loop:** the `screenshot` tool OpenGL-renders the current view and
hands the image back to Claude, so it can **see** the scene and iterate — *"make the
lighting more dramatic"* → screenshot → adjust → screenshot again.

**Asset import (new):** `search_hdris` + `set_hdri` pull free PolyHaven HDRIs for
real image-based lighting and reflections (the jump from gray blobs to a believable
scene), and `import_model_url` brings in any `.glb/.gltf/.obj/.fbx` from a direct
URL. Downloads happen on the Blender side — no extra addon features required.

## Setup

**1. Enable the blender-mcp addon (once)** — install `addon.py` from
[blender-mcp](https://github.com/ahujasid/blender-mcp), enable **Interface: Blender
MCP**, press **N** in the 3D view → **BlenderMCP** tab → **Connect** (starts the
socket on 9876). *(If you set up the Claude Desktop blender connector earlier,
this is already done.)*

**2. Install deps** — `pip install -r requirements.txt` (or run via `uv` below).

**3a. Claude Desktop (MCP)** — add to `%APPDATA%\Claude\claude_desktop_config.json`:
```json
"renderkit": {
  "command": "C:\\Users\\dylan\\.local\\bin\\uv.exe",
  "args": ["run", "--python", "3.12", "--with", "mcp",
           "python", "E:\\renderkit\\mcp_server.py"]
}
```

**3b. Terminal agent**
```bash
set ANTHROPIC_API_KEY=sk-ant-...
uv run --python 3.12 --with anthropic python agent.py "build a lit turntable of a red monkey and render it to output/turntable.mp4"
```

> **One client at a time:** the addon serves a single connection — if Claude
> Desktop's blender connector is attached, disconnect it before using RenderKit's
> agent, and reconnect afterwards.

> **Scope:** great for scene setup, modeling, materials, lighting, and camera
> moves. Animation/cinematics are Blender's harder area — expect Claude to set up
> and script shots; you do final polish/render passes in Blender.

## Layout

| Path | What it is |
| --- | --- |
| `core/bridge.py` | socket client to the blender-mcp addon |
| `core/tools.py` | capability layer (modeling + cinematics + run_blender_code) |
| `mcp_server.py` | FastMCP server for Claude Desktop |
| `agent.py` | standalone Anthropic-API agent |
| `config.py` | host/port + model |

Supersedes the earlier `blendkit` experiment (same socket protocol, now with the
Claude tool layer).
