"""Blender MCP preflight check.

Reads host configuration from the environment and verifies, read-only:

1.  A Blender executable is configured and the file exists.
2.  Its file version is >= 5.1.0 (required by the vendored MCP Add-on).
3.  The Blender MCP bridge socket (default localhost:9876) is reachable.

This check never starts Blender, never installs the Add-on, and never changes a
.blend file. A socket handshake is not a full MCP tool call; workflows that
need a real ``execute_blender_code`` result must do that handshake separately.
"""

from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path

import preflight_common as pc

MIN_BLENDER = (5, 1, 0)


def _blender_exe_from_env() -> str:
    configured = os.environ.get("AINATIVE_PREFLIGHT_BLENDER_EXECUTABLE", "")
    return configured


def _version_tuple(path: Path) -> tuple[int, int, int] | None:
    try:
        completed = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
    except Exception:  # noqa: BLE001 - read-only probe
        return None
    text = (completed.stdout or completed.stderr or "").strip()
    # Blender prints e.g. "Blender 5.2.1" or "Blender 5.2.1 LTS".
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("Blender "):
            continue
        token = line[len("Blender "):].split()[0]
        parts = token.split(".")
        try:
            nums = tuple(int(part) for part in parts[:3])
        except ValueError:
            return None
        while len(nums) < 3:
            nums = nums + (0,)
        return nums  # type: ignore[return-value]


def _socket_reachable(host: str, port: int, timeout: float) -> bool:
    """Return True when the Blender MCP bridge accepts a TCP connection."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check(env: dict[str, str]) -> pc.CheckOutcome:
    exe = env.get("AINATIVE_PREFLIGHT_BLENDER_EXECUTABLE", "") or _blender_exe_from_env()
    if not exe:
        return pc.CheckOutcome(check_id="blender_mcp", ok=False, reason="no Blender executable configured")
    path = Path(exe)
    if not path.is_file():
        return pc.CheckOutcome(check_id="blender_mcp", ok=False, reason=f"Blender executable not found: {exe}")
    version = _version_tuple(path)
    if version is None:
        return pc.CheckOutcome(check_id="blender_mcp", ok=False, reason=f"could not read Blender version from {exe}")
    if version < MIN_BLENDER:
        return pc.CheckOutcome(
            check_id="blender_mcp",
            ok=False,
            reason=f"Blender {'.'.join(str(p) for p in version)} is below the >=5.1.0 MCP baseline",
        )
    host = env.get("AINATIVE_PREFLIGHT_BLENDER_MCP_HOST", "127.0.0.1")
    port = int(env.get("AINATIVE_PREFLIGHT_BLENDER_MCP_PORT", "9876"))
    if not _socket_reachable(host, port, timeout=float(env.get("AINATIVE_PREFLIGHT_TIMEOUT_SEC", "10"))):
        return pc.CheckOutcome(
            check_id="blender_mcp",
            ok=False,
            reason=f"Blender MCP bridge is not reachable at {host}:{port} (is Blender running with the Add-on enabled?)",
        )
    return pc.CheckOutcome(
        check_id="blender_mcp",
        ok=True,
        found=f"Blender {'.'.join(str(p) for p in version)}; bridge {host}:{port} reachable",
    )
