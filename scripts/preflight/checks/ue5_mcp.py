"""UE5 native MCP preflight check.

Reads host configuration from the environment and verifies, read-only:

1.  The UE5 MCP HTTP endpoint is configured and reachable (default
    http://127.0.0.1:8000/mcp).
2.  A minimal MCP ``initialize`` handshake succeeds.
3.  ``tools/list`` returns at least one tool (in Tool Search mode this is the
    three meta-tools: list_toolsets, describe_toolset, call_tool).

When a UE5 executable and project are also configured, the check additionally
verifies the files exist and reports their file versions, but it never starts
UnrealEditor.
"""

from __future__ import annotations

import ctypes
import json
import urllib.error
import urllib.request
from ctypes import Structure, c_uint, c_ushort, wintypes
from pathlib import Path

import preflight_common as pc

MIN_UE5 = (5, 8, 0)
DEFAULT_URL = "http://127.0.0.1:8000/mcp"


class _VS_FIXEDFILEINFO(Structure):
    _fields_ = [
        ("dwSignature", ctypes.c_uint),
        ("dwStrucVersion", c_ushort),
        ("dwStrucVersion2", c_ushort),
        ("dwFileVersionMS", c_uint),
        ("dwFileVersionLS", c_uint),
        ("dwProductVersionMS", c_uint),
        ("dwProductVersionLS", c_uint),
        ("dwFileFlagsMask", c_uint),
        ("dwFileFlags", c_uint),
        ("dwFileOS", c_uint),
        ("dwFileType", c_uint),
        ("dwFileSubtype", c_uint),
        ("dwFileDateMS", c_uint),
        ("dwFileDateLS", c_uint),
    ]


def _version_tuple(path: Path) -> tuple[int, int, int] | None:
    """Read the UnrealEditor.exe file version (fast, read-only)."""
    try:
        size = ctypes.windll.version.GetFileVersionInfoSizeW(str(path), None)
        if size <= 0:
            return None
        buffer = ctypes.create_string_buffer(size)
        if not ctypes.windll.version.GetFileVersionInfoW(str(path), None, size, buffer):
            return None
        value = ctypes.c_void_p()
        length = wintypes.UINT()
        if not ctypes.windll.version.VerQueryValueW(
            buffer, "\\", ctypes.byref(value), ctypes.byref(length)
        ):
            return None
        info = ctypes.cast(value, ctypes.POINTER(_VS_FIXEDFILEINFO)).contents
        ms = info.dwFileVersionMS
        ls = info.dwFileVersionLS
        return (ms >> 16, ms & 0xFFFF, ls >> 16)
    except Exception:  # noqa: BLE001 - read-only probe
        return None


def _post_json(
    url: str, payload: dict[str, object], timeout: float, session_id: str = ""
) -> tuple[dict[str, object], str]:
    """POST one JSON-RPC request and return (parsed_body, session_id).

    The Unreal MCP server returns an ``Mcp-Session-Id`` response header after
    ``initialize``; subsequent requests such as ``tools/list`` must echo it back
    or the server rejects them with HTTP 400.
    """
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
        new_session = response.headers.get("Mcp-Session-Id", "")
    return json.loads(raw), new_session


def check(env: dict[str, str]) -> pc.CheckOutcome:
    url = env.get("AINATIVE_PREFLIGHT_UE5_MCP_URL", "") or DEFAULT_URL
    timeout = float(env.get("AINATIVE_PREFLIGHT_TIMEOUT_SEC", "10"))

    # Optional local file checks (never launch the Editor).
    exe = env.get("AINATIVE_PREFLIGHT_UE5_EXECUTABLE", "")
    project = env.get("AINATIVE_PREFLIGHT_UE5_PROJECT", "")
    if exe:
        path = Path(exe)
        if not path.is_file():
            return pc.CheckOutcome(check_id="ue5_mcp", ok=False, reason=f"UE5 executable not found: {exe}")
        version = _version_tuple(path)
        if version is not None and version < MIN_UE5:
            return pc.CheckOutcome(
                check_id="ue5_mcp",
                ok=False,
                reason=f"UE5 {'.'.join(str(p) for p in version)} is below the >=5.8.0 MCP baseline",
            )
    if project and not Path(project).is_file():
        return pc.CheckOutcome(check_id="ue5_mcp", ok=False, reason=f"UE5 project not found: {project}")

    try:
        initialize, session_id = _post_json(
            url,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "ai-native-preflight", "version": "1.0"},
                },
            },
            timeout,
        )
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError) as exc:
        return pc.CheckOutcome(check_id="ue5_mcp", ok=False, reason=f"MCP endpoint unreachable at {url}: {exc}")
    if "result" not in initialize:
        return pc.CheckOutcome(
            check_id="ue5_mcp",
            ok=False,
            reason=f"MCP initialize failed at {url}: {json.dumps(initialize)[:200]}",
        )

    try:
        tools, _ = _post_json(
            url,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            timeout,
            session_id=session_id,
        )
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError) as exc:
        return pc.CheckOutcome(check_id="ue5_mcp", ok=False, reason=f"MCP tools/list failed at {url}: {exc}")
    tool_list = (tools.get("result") or {}).get("tools")
    if not isinstance(tool_list, list) or not tool_list:
        return pc.CheckOutcome(
            check_id="ue5_mcp", ok=False, reason=f"MCP endpoint returned no tools at {url}"
        )

    details = f"initialize ok; {len(tool_list)} tools at {url}"
    if exe and Path(exe).is_file():
        version = _version_tuple(Path(exe))
        if version is not None:
            details = f"UE5 {'.'.join(str(p) for p in version)}; " + details
    return pc.CheckOutcome(check_id="ue5_mcp", ok=True, found=details)
