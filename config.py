"""Shared settings for RenderKit."""
from __future__ import annotations

import os

# The blender-mcp addon's socket (Blender 3D view -> BlenderMCP tab -> Connect).
BLENDER_HOST = os.environ.get("RENDERKIT_HOST", "127.0.0.1")
BLENDER_PORT = int(os.environ.get("RENDERKIT_PORT", "9876"))
TIMEOUT = float(os.environ.get("RENDERKIT_TIMEOUT", "60"))

MODEL = os.environ.get("RENDERKIT_MODEL", "claude-opus-4-8")
