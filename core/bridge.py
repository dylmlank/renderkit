"""Socket bridge to the blender-mcp addon (JSON over TCP on 127.0.0.1:9876).

Sends {"type": <command>, "params": {...}} and reads back
{"status": "success"|"error", "result"|"message": ...}. One connection per call,
so RenderKit doesn't hog the socket. The addon serves one client at a time — if
Claude Desktop's blender connector is attached, disconnect it first, or vice-versa.
"""
from __future__ import annotations

import json
import socket

from config import BLENDER_HOST, BLENDER_PORT, TIMEOUT


class BridgeError(RuntimeError):
    """Blender unreachable or returned an error."""


class BlenderBridge:
    def __init__(self, host: str = BLENDER_HOST, port: int = BLENDER_PORT,
                 timeout: float = TIMEOUT):
        self.host, self.port, self.timeout = host, port, timeout

    def _send(self, command: str, params: dict | None = None) -> dict:
        payload = json.dumps({"type": command, "params": params or {}}).encode()
        try:
            with socket.create_connection((self.host, self.port), self.timeout) as s:
                s.settimeout(self.timeout)
                s.sendall(payload)
                resp = self._recv_json(s)
        except (ConnectionRefusedError, OSError) as e:
            raise BridgeError(
                f"Could not reach Blender on {self.host}:{self.port} ({e}). Open "
                "Blender, press N in the 3D view, open the BlenderMCP tab and click "
                "Connect (that starts the socket)."
            ) from e
        if resp is None:
            raise BridgeError(f"No/unparseable response for '{command}'.")
        if resp.get("status") == "error":
            raise BridgeError(resp.get("message", f"Blender error for '{command}'."))
        return resp.get("result", {})

    def _recv_json(self, s: socket.socket) -> dict | None:
        chunks: list[bytes] = []
        while True:
            try:
                data = s.recv(8192)
            except socket.timeout:
                break
            if not data:
                break
            chunks.append(data)
            try:
                return json.loads(b"".join(chunks).decode())
            except json.JSONDecodeError:
                continue
        return None

    def run_code(self, code: str) -> dict:
        return self._send("execute_code", {"code": code})

    def get_scene_info(self) -> dict:
        return self._send("get_scene_info")

    def get_object_info(self, name: str) -> dict:
        return self._send("get_object_info", {"name": name})
