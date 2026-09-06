"""Unit tests for preflight check plugins (no live Blender/UE5 required).

Tests cover version parsing helpers and the socket/http branches using local
fake listeners so CI stays deterministic.
"""

from __future__ import annotations

import http.server
import importlib.util
import json
import socket
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PREFLIGHT = ROOT / "scripts" / "preflight"
COMMON = PREFLIGHT / "preflight_common.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


common = _load("preflight_common", COMMON)
blender = _load("blender_mcp", PREFLIGHT / "checks" / "blender_mcp.py")
ue5 = _load("ue5_mcp", PREFLIGHT / "checks" / "ue5_mcp.py")


class _FakeMCPHandler(http.server.BaseHTTPRequestHandler):
    session_seen = None
    last_method = None

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        body = json.loads(raw)
        _FakeMCPHandler.last_method = body.get("method")
        _FakeMCPHandler.session_seen = self.headers.get("Mcp-Session-Id", "")
        if body.get("method") == "initialize":
            self.send_response(200)
            self.send_header("Mcp-Session-Id", "session-abc")
        else:
            self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        result = {"jsonrpc": "2.0", "id": body.get("id"), "result": {}}
        if body.get("method") == "tools/list":
            result["result"]["tools"] = [{"name": "list_toolsets"}]
        self.wfile.write(json.dumps(result).encode("utf-8"))

    def log_message(self, *args):
        pass


def test_blender_version_tuple_real_executable_or_skip():
    exe = Path(r"E:\blender\blender.exe")
    if not exe.is_file():
        return
    version = blender._version_tuple(exe)
    assert version is not None
    assert version >= (5, 1, 0)


def test_blender_check_passes_when_bridge_reachable(monkeypatch):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    if not Path(r"E:\blender\blender.exe").is_file():
        srv.close()
        return

    def accept() -> None:
        try:
            conn, _ = srv.accept()
            conn.close()
        except OSError:
            pass

    threading.Thread(target=accept, daemon=True).start()
    try:
        outcome = blender.check(
            {
                "AINATIVE_PREFLIGHT_BLENDER_EXECUTABLE": r"E:\blender\blender.exe",
                "AINATIVE_PREFLIGHT_BLENDER_MCP_HOST": "127.0.0.1",
                "AINATIVE_PREFLIGHT_BLENDER_MCP_PORT": str(port),
                "AINATIVE_PREFLIGHT_TIMEOUT_SEC": "5",
            }
        )
    finally:
        srv.close()
    assert outcome.ok is True

def test_ue5_check_passes_and_echoes_session(monkeypatch):
    srv = http.server.HTTPServer(("127.0.0.1", 0), _FakeMCPHandler)
    port = srv.server_address[1]
    _FakeMCPHandler.session_seen = None
    _FakeMCPHandler.last_method = None
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        outcome = ue5.check(
            {
                "AINATIVE_PREFLIGHT_UE5_MCP_URL": f"http://127.0.0.1:{port}/mcp",
                "AINATIVE_PREFLIGHT_TIMEOUT_SEC": "5",
            }
        )
    finally:
        srv.shutdown()
        thread.join(timeout=2)
    assert outcome.ok is True
    assert "1 tools" in outcome.found
    assert _FakeMCPHandler.session_seen == "session-abc"
