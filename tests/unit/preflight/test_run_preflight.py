"""Unit tests for the unified preflight orchestrator.

The tests exercise requirements interpretation and subprocess plugin plumbing
without requiring Blender, UE5, or a live MCP endpoint. They import the
orchestrator as a plain script via importlib so the tests do not depend on the
runtime package or on ``scripts`` being on ``sys.path``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PREFLIGHT = ROOT / "scripts" / "preflight"
COMMON = PREFLIGHT / "preflight_common.py"
RUNNER = PREFLIGHT / "run_preflight.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


common = _load_module("preflight_common", COMMON)
runner = _load_module("run_preflight", RUNNER)


def test_requirements_summary_detects_blender_and_ue5_groups(tmp_path: Path):
    root = tmp_path / "workflow"
    root.mkdir()
    (root / "requirements.yaml").write_text(
        "requires:\n"
        "  host:\n"
        '    blender_version: ">=5.1.0"\n'
        "    blender_mcp_addon: mcp\n"
        '    unreal_engine: ">=5.8.0"\n'
        "    ue5_mcp_plugin: ModelContextProtocol\n",
        encoding="utf-8",
    )
    payload = runner.load_requirements(root)
    groups, warnings = runner.requirements_summary(payload)
    assert groups == ["ue5_mcp", "blender_mcp"]
    assert warnings == []


def test_requirements_summary_skips_host_checks_when_no_host_requirements(tmp_path: Path):
    root = tmp_path / "workflow"
    root.mkdir()
    (root / "requirements.yaml").write_text(
        "requires:\n"
        "  mcp:\n"
        "    - server_id: blender\n"
        "      tool_name: execute_blender_code\n",
        encoding="utf-8",
    )
    payload = runner.load_requirements(root)
    groups, warnings = runner.requirements_summary(payload)
    assert groups == []
    assert warnings == []


def test_build_host_config_uses_defaults_when_config_empty():
    config = runner.build_host_config({})
    assert config.blender_mcp_host == "127.0.0.1"
    assert config.blender_mcp_port == 9876
    assert config.mcp_http_url == ""
    assert config.timeout_sec == 10


def test_build_host_config_reads_explicit_values():
    config = runner.build_host_config(
        {
            "blender": {"executable": "E:/blender/blender.exe"},
            "ue5": {"executable": "D:/ue/UnrealEditor.exe", "project": "D:/proj/Game.uproject"},
            "blender_mcp": {"host": "localhost", "port": 9876},
            "ue5_mcp": {"url": "http://127.0.0.1:8000/mcp"},
            "timeout_sec": 5,
        }
    )
    assert config.blender_executable == "E:/blender/blender.exe"
    assert config.ue5_executable == "D:/ue/UnrealEditor.exe"
    assert config.ue5_project == "D:/proj/Game.uproject"
    assert config.blender_mcp_host == "localhost"
    assert config.mcp_http_url == "http://127.0.0.1:8000/mcp"
    assert config.timeout_sec == 5


def test_run_check_plugin_reports_timeout_when_plugin_hangs(monkeypatch):
    import subprocess

    class _Timeout:
        def __init__(self, *args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="plugin", timeout=1)

    monkeypatch.setattr(runner, "PYTHON", sys.executable)
    monkeypatch.setattr(subprocess, "run", _Timeout)
    outcome = runner.run_check_plugin(
        RUNNER.parent / "checks" / "blender_mcp.py",
        "wf",
        {"AINATIVE_PREFLIGHT_TIMEOUT_SEC": "1"},
    )
    assert outcome.ok is False
    assert "timed out" in outcome.reason
