"""Unified read-only preflight for Workflow runtime dependencies.

This script checks the machine against a Workflow requirements file before a
change Stage is allowed to start. It never installs software, never edits a
project, and never starts UE5/Blender. Checks that require an external host or
MCP handshake are delegated to plugin modules under ``scripts/preflight/checks/``
and run in isolated subprocesses so a failing plugin cannot corrupt the
orchestrator.

Exit codes:
    0  all required checks passed
    1  at least one required check failed
    2  the report could not be produced (usage/config/IO error)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from preflight_common import CheckOutcome, PreflightReport

ROOT = Path(__file__).resolve().parents[2]
CHECKS_DIR = ROOT / "scripts" / "preflight" / "checks"
PYTHON = sys.executable


@dataclass(frozen=True, slots=True)
class HostConfig:
    blender_executable: str = ""
    ue5_executable: str = ""
    ue5_project: str = ""
    mcp_http_url: str = ""
    blender_mcp_host: str = "127.0.0.1"
    blender_mcp_port: int = 9876
    timeout_sec: int = 10


def _load_json(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return payload


def _safe_scalar(token: str) -> Any:
    token = token.strip()
    if token.startswith('"') and token.endswith('"') and len(token) >= 2:
        return token[1:-1]
    if token.startswith("'") and token.endswith("'") and len(token) >= 2:
        return token[1:-1]
    if token in {"true", "True"}:
        return True
    if token in {"false", "False"}:
        return False
    if token in {"null", "None"}:
        return None
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    return token


def parse_requirements_yaml(text: str) -> dict[str, Any]:
    """Parse the safe requirements subset into nested plain dicts/lists."""

    if not isinstance(text, str) or not text.strip():
        return {}
    lines = text.splitlines()
    block_lines = [line for line in lines if line.strip() and not line.strip().startswith("#")]
    if not block_lines:
        return {}
    for line in block_lines:
        if any(marker in line for marker in ("<<:", "&anchor", "*alias")):
            raise ValueError("unsupported YAML construct in requirements file")
    parsed: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, parsed)]
    for line in block_lines:
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if stripped.startswith("- "):
            if not stack:
                raise ValueError("list item without a parent")
            parent = stack[-1][1]
            remainder = stripped[2:].strip()
            if ":" not in remainder:
                parent.setdefault("__list_items__", []).append(_safe_scalar(remainder))
                continue
            key, value = remainder.split(":", 1)
            key = key.strip()
            value = value.strip()
            item: dict[str, Any] = {}
            if value:
                item[key] = _safe_scalar(value)
            parent.setdefault("__list_items__", []).append(item)
            stack.append((indent, item))
            continue
        if ":" not in stripped:
            raise ValueError(f"unsupported line in requirements file: {line}")
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if not stack:
            raise ValueError(f"bad indentation in requirements file: {line}")
        current = stack[-1][1]
        current[key] = _safe_scalar(value) if value else {}
        if not value:
            stack.append((indent, current[key]))

    def _flatten(node: Any) -> Any:
        if isinstance(node, dict):
            result: dict[str, Any] = {}
            items: list[Any] = []
            for key, value in node.items():
                if key == "__list_items__":
                    items.extend(value)
                else:
                    result[key] = _flatten(value)
            for item in items:
                if isinstance(item, dict):
                    for item_key, item_value in item.items():
                        result.setdefault(item_key, []).append(item_value)
                else:
                    result.setdefault("values", []).append(item)
            return result
        if isinstance(node, list):
            return [_flatten(item) for item in node]
        return node

    return _flatten(parsed)


def load_requirements(workflow_root: Path) -> dict[str, Any]:
    requirements = workflow_root / "requirements.yaml"
    if not requirements.is_file():
        return {}
    try:
        return parse_requirements_yaml(requirements.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read {requirements}: {exc}") from exc


def build_host_config(raw: dict[str, Any]) -> HostConfig:
    blender = dict(raw.get("blender", {}) or {})
    ue5 = dict(raw.get("ue5", {}) or {})
    blender_mcp = dict(raw.get("blender_mcp", {}) or {})
    ue5_mcp = dict(raw.get("ue5_mcp", {}) or {})
    return HostConfig(
        blender_executable=str(blender.get("executable", "")),
        ue5_executable=str(ue5.get("executable", "")),
        ue5_project=str(ue5.get("project", "")),
        mcp_http_url=str(ue5_mcp.get("url", "")),
        blender_mcp_host=str(blender_mcp.get("host", "127.0.0.1")),
        blender_mcp_port=int(blender_mcp.get("port", 9876)),
        timeout_sec=int(raw.get("timeout_sec", 10)),
    )


def _env_from_config(config: HostConfig) -> dict[str, str]:
    return {
        "AINATIVE_PREFLIGHT_BLENDER_EXECUTABLE": config.blender_executable,
        "AINATIVE_PREFLIGHT_UE5_EXECUTABLE": config.ue5_executable,
        "AINATIVE_PREFLIGHT_UE5_PROJECT": config.ue5_project,
        "AINATIVE_PREFLIGHT_UE5_MCP_URL": config.mcp_http_url,
        "AINATIVE_PREFLIGHT_BLENDER_MCP_HOST": config.blender_mcp_host,
        "AINATIVE_PREFLIGHT_BLENDER_MCP_PORT": str(config.blender_mcp_port),
        "AINATIVE_PREFLIGHT_TIMEOUT_SEC": str(config.timeout_sec),
    }


def run_check_plugin(plugin: Path, workflow_id: str, config_env: dict[str, str]) -> CheckOutcome:
    code = (
        "import importlib.util,json,sys,os;"
        "sys.path.insert(0,sys.argv[1]);"
        "import preflight_common as pc;"
        "spec=importlib.util.spec_from_file_location('plugin',sys.argv[2]);"
        "mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);"
        "result=mod.check(os.environ);"
        "payload={k:getattr(result,k,'') for k in ('check_id','ok','found','reason')};"
        "payload['ok']=bool(payload.get('ok',False));"
        "print(json.dumps(payload,ensure_ascii=False));"
    )
    try:
        completed = subprocess.run(
            [PYTHON, "-c", code, str(Path(__file__).with_name("preflight_common.py").parent), str(plugin)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, **config_env},
            timeout=int(config_env.get("AINATIVE_PREFLIGHT_TIMEOUT_SEC", "10")) + 30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CheckOutcome(check_id=plugin.stem, ok=False, reason=f"plugin timed out ({plugin.name})")
    except OSError as exc:
        return CheckOutcome(check_id=plugin.stem, ok=False, reason=f"plugin could not start: {exc}")
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "plugin failed").strip()
        return CheckOutcome(check_id=plugin.stem, ok=False, reason=detail)
    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError:
        return CheckOutcome(check_id=plugin.stem, ok=False, reason=f"plugin returned invalid JSON ({plugin.name})")
    if not isinstance(payload, dict):
        return CheckOutcome(check_id=plugin.stem, ok=False, reason=f"plugin returned invalid result ({plugin.name})")
    return CheckOutcome(
        check_id=str(payload.get("check_id", plugin.stem)),
        ok=bool(payload.get("ok", False)),
        found=str(payload.get("found", "")),
        reason=str(payload.get("reason", "")),
    )


def requirements_summary(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    groups: list[str] = []
    warnings: list[str] = []
    requires = payload.get("requires") or {}
    if isinstance(requires, dict):
        host = requires.get("host") or {}
        if isinstance(host, dict):
            if host.get("unreal_engine") or host.get("ue5_mcp_plugin"):
                groups.append("ue5_mcp")
            if host.get("blender_version") or host.get("blender_mcp_addon"):
                groups.append("blender_mcp")
    else:
        warnings.append("requirements 'requires' is not an object; host checks skipped")
    return groups, warnings


def build_report(workflow_id: str, groups: list[str], config_env: dict[str, str], warnings: list[str]) -> PreflightReport:
    checks: list[CheckOutcome] = []
    plugins = {
        "blender_mcp": CHECKS_DIR / "blender_mcp.py",
        "ue5_mcp": CHECKS_DIR / "ue5_mcp.py",
    }
    for group in groups:
        plugin = plugins.get(group)
        if plugin is None or not plugin.is_file():
            checks.append(CheckOutcome(check_id=group, ok=False, reason=f"no preflight plugin registered for {group}"))
            continue
        checks.append(run_check_plugin(plugin, workflow_id, config_env))
    ok = all(check.ok for check in checks)
    return PreflightReport(
        workflow_id=workflow_id,
        ok=ok,
        checks=tuple(checks),
        warnings=tuple(warnings),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run_preflight")
    parser.add_argument("--workflow-root", required=True, help="Workflow Definition root containing requirements.yaml")
    parser.add_argument("--config", default="", help="local machine config JSON (host paths/endpoints; optional)")
    parser.add_argument("--json", action="store_true", help="always print JSON report")
    args = parser.parse_args(argv)
    root = Path(args.workflow_root).resolve()
    if not root.is_dir():
        print(json.dumps({"workflow_id": str(root), "ok": False, "checks": [], "warnings": [], "errors": [f"workflow root not found: {root}"]}))
        return 2
    config_raw: dict[str, Any] = {}
    if args.config:
        config_path = Path(args.config)
        if not config_path.is_file():
            print(json.dumps({"workflow_id": root.name, "ok": False, "checks": [], "warnings": [], "errors": [f"config not found: {config_path}"]}))
            return 2
        config_raw = _load_json(config_path)
    requirements = load_requirements(root)
    groups, warnings = requirements_summary(requirements)
    config_env = _env_from_config(build_host_config(config_raw))
    report = build_report(root.name, groups, config_env, warnings)
    payload = report.to_dict()
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())