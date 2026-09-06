"""Run the complete Agent/Skill/Workflow round-trip in the visible UE5 Editor.

This is intentionally separate from the headless smoke runner.  It launches
the ordinary ``UnrealEditor.exe`` (not ``UnrealEditor-Cmd.exe``), does not pass
``-unattended`` or ``-nullrhi``, observes the native Slate window, and records
that observation next to each UE5 operation result.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
E2E_ROOT = ROOT / "scripts" / "e2e"
if str(E2E_ROOT) not in sys.path:
    sys.path.insert(0, str(E2E_ROOT))

from support.plan_fixtures import asset_roundtrip_plan, execute_agent_plan

from ainative.orchestration import RuntimeContext
from ainative.orchestration.contracts import (
    BlenderCallSurface,
    TaskContract,
    TaskRoute,
    TransferBackendKind,
)
from ainative.toolsets.blender_editor.execution import (
    BlenderCliSurface,
    BlenderExecutor,
)
from ainative.toolsets.transfer_assetsbridge import (
    AssetsBridgeBackend,
    AssetsBridgeJsonProtocol,
    ExternalBlenderAssetsBridgeConnector,
)
from ainative.toolsets.ue5_editor.execution import UnrealEditorPythonExecutor
from ainative.toolsets.validation_workflow import AssetsBridgeValidator

DEFAULT_UE5_EDITOR = Path(
    r"D:\UnrealEngine\ue5.7.1\UnrealEngine\Engine\Binaries\Win64\UnrealEditor.exe"
)
DEFAULT_BLENDER = Path(r"E:\blender\blender.exe")
DEFAULT_PROJECT = ROOT / "projects" / "fixtures" / "ue5" / "assetsbridge-smoke" / "AssetsBridgeSmoke.uproject"
DEFAULT_ADDON = ROOT / "vendor" / "assetsbridge" / "blender-addon" / "AssetsBridgeAddon"


def _window_for_pid(pid: int) -> dict[str, object] | None:
    """Return the first visible top-level window owned by ``pid`` on Windows."""

    if os.name != "nt":
        return None

    user32 = ctypes.windll.user32
    found: dict[str, object] | None = None

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd: int, _lparam: int) -> bool:
        nonlocal found
        if not user32.IsWindowVisible(hwnd):
            return True
        owner_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner_pid))
        if owner_pid.value != pid:
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(max(length + 1, 1))
        user32.GetWindowTextW(hwnd, buffer, len(buffer))
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        found = {
            "handle": int(hwnd),
            "title": buffer.value,
            "rect": [rect.left, rect.top, rect.right, rect.bottom],
        }
        return False

    user32.EnumWindows(callback, 0)
    return found


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    """Stop a UE5 Editor tree after its structured result is durable."""

    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _visible_editor_runner(args: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    """Process runner that records proof that a real Editor window appeared."""

    env = dict(kwargs.get("env") or os.environ)
    timeout = int(kwargs.get("timeout") or 180)
    encoding = kwargs.get("encoding") or "utf-8"
    errors = kwargs.get("errors") or "replace"
    result_path = Path(env["AINATIVE_UE5_RESULT_FILE"])
    evidence_path = result_path.with_name("editor-ui-evidence.json")
    evidence: dict[str, object] = {
        "launch_mode": "editor",
        "executable": str(args[0]),
        "command": args,
        "process_started": False,
        "window_seen": False,
        "window": None,
        "result_file_seen": False,
        "cleanup_after_result": False,
        "termination_reason": None,
    }
    started = time.monotonic()
    process: subprocess.Popen[str] | None = None
    stdout = ""
    stderr = ""
    returncode = 1
    try:
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=encoding,
            errors=errors,
            env=env,
        )
        evidence.update({"process_started": True, "pid": process.pid})

        # UE5 startup can spend several seconds loading the Asset Registry.
        # The structured result is the operation proof; once it is durable and
        # the native window has appeared, terminate the editor tree explicitly.
        # Some UE5.7 editor/plugin combinations keep child processes alive even
        # after quit_editor(), which otherwise makes communicate() wait forever.
        deadline = started + timeout
        while process.poll() is None and time.monotonic() < deadline:
            if not evidence["window_seen"]:
                window = _window_for_pid(process.pid)
                if window:
                    evidence.update(
                        {
                            "window_seen": True,
                            "window": window,
                            "window_seen_after_seconds": round(time.monotonic() - started, 3),
                        }
                    )
            if result_path.is_file():
                evidence["result_file_seen"] = True
            if evidence["window_seen"] and evidence["result_file_seen"]:
                break
            time.sleep(0.25)

        if evidence["window_seen"] and evidence["result_file_seen"] and process.poll() is None:
            evidence["cleanup_after_result"] = True
            evidence["termination_reason"] = "harness_cleanup_after_result"
            _terminate_process_tree(process)

        remaining = max(1.0, min(10.0, deadline - time.monotonic()))
        try:
            stdout, stderr = process.communicate(timeout=remaining)
        except subprocess.TimeoutExpired:
            _terminate_process_tree(process)
            stdout, stderr = process.communicate(timeout=10)
            evidence["process_timeout"] = True
        returncode = process.returncode
        if evidence["termination_reason"] == "harness_cleanup_after_result":
            evidence["returncode_expected_nonzero"] = True
    except Exception as exc:  # noqa: BLE001 - convert any native process/window failure into evidence
        evidence.update({"runner_error_type": type(exc).__name__, "runner_error": str(exc)})
        if process is not None and process.poll() is None:
            _terminate_process_tree(process)
            stdout, stderr = process.communicate(timeout=10)
    finally:
        evidence["duration_seconds"] = round(time.monotonic() - started, 3)
        evidence["returncode"] = returncode
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")

    return subprocess.CompletedProcess(args, returncode, stdout, stderr)


def _build_task(out: Path):
    bridge = out / "bridge"
    edit_file = bridge / "edit.blend"
    modified_file = bridge / "modified.blend"
    export_file = bridge / "Engine" / "BasicShapes" / "Cube.glb"
    return TaskContract(
        task_id="visible-ue5-assetsbridge-roundtrip",
        objective="Edit the UE5 Static Mesh in Blender and return it to the original asset.",
        route=TaskRoute.ASSET_TRANSFER,
        profile="default",
        asset_type="static_mesh",
        direction="ue5_to_blender_to_ue5",
        preserve_relations=frozenset({"asset_identity", "material_slots", "transform"}),
        preferred_backend=TransferBackendKind.ASSETSBRIDGE,
        preferred_call_surface=BlenderCallSurface.CLI_PYTHON,
        source_context={"app": "ue5", "asset_id": "/Engine/BasicShapes/Cube.Cube"},
        target_context={"app": "ue5"},
        metadata={
            "edit_app": "blender",
            "ue5_asset_path": "/Engine/BasicShapes/Cube.Cube",
            "export_file": str(export_file),
            "blender_edit_file": str(edit_file),
            "modified_blend_file": str(modified_file),
            "result_dir": str(out),
            "blender_operation": "translate-active",
            "delta": [1, 0, 0],
            "file_format": "glb",
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ue5-editor", type=Path, default=DEFAULT_UE5_EDITOR)
    parser.add_argument("--uproject", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--blender", type=Path, default=DEFAULT_BLENDER)
    parser.add_argument("--addon-root", type=Path, default=DEFAULT_ADDON)
    parser.add_argument(
        "--editor-arg",
        action="append",
        default=[],
        help="Additional argument passed to the visible UnrealEditor.exe launch.",
    )
    parser.add_argument(
        "--ue5-timeout",
        type=int,
        default=600,
        help="Maximum seconds allowed for each visible UE5 Editor operation.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "artifacts" / "scratch" / "visible-ue5-assetsbridge-e2e",
    )
    args = parser.parse_args()
    # Always pass absolute paths to UnrealEditor.  The Project Browser and the
    # editor executable may choose a different working directory, and a
    # relative .uproject path then produces the misleading "Failed to open
    # descriptor file" dialog.
    args.ue5_editor = args.ue5_editor.resolve()
    args.uproject = args.uproject.resolve()
    args.blender = args.blender.resolve()
    args.addon_root = args.addon_root.resolve()

    required = (
        args.ue5_editor,
        args.uproject,
        args.blender,
        args.addon_root / "__init__.py",
        ROOT / "src" / "ainative" / "toolsets" / "ue5_editor" / "execution" / "bridge_entry.py",
    )
    missing = [str(path) for path in required if not (path.is_file() or path.is_dir())]
    if missing:
        print(json.dumps({"status": "blocked", "missing": missing}, ensure_ascii=False, indent=2))
        return 2

    out = args.out.resolve()
    bridge = out / "bridge"
    out.mkdir(parents=True, exist_ok=True)
    bridge.mkdir(parents=True, exist_ok=True)
    task = _build_task(out)
    blender_executor = BlenderExecutor({BlenderCallSurface.CLI_PYTHON: BlenderCliSurface(args.blender)})
    ue5_executor = UnrealEditorPythonExecutor(
        args.ue5_editor,
        args.uproject,
        ROOT / "src" / "ainative" / "toolsets" / "ue5_editor" / "execution" / "bridge_entry.py",
        bridge_dir=bridge,
        runner=_visible_editor_runner,
        timeout=args.ue5_timeout,
        launch_mode="editor",
        extra_args=tuple(args.editor_arg),
    )
    blender_connector = ExternalBlenderAssetsBridgeConnector(args.blender, args.addon_root, bridge, out, timeout=120)
    backend = AssetsBridgeBackend(ue5_executor, blender_connector)
    protocol = AssetsBridgeJsonProtocol(bridge)
    runtime = RuntimeContext(
        executors={"blender": blender_executor, "ue5": ue5_executor},
        transfer_backends={TransferBackendKind.ASSETSBRIDGE: backend},
        validator=AssetsBridgeValidator(protocol),
    )

    plan = asset_roundtrip_plan(task, "assetsbridge")
    run = execute_agent_plan(task, plan, runtime)
    evidence = {}
    for operation in ("export_asset", "import_asset"):
        path = out / "ue5" / operation / "editor-ui-evidence.json"
        if path.is_file():
            evidence[operation] = json.loads(path.read_text(encoding="utf-8"))
    result = {
        "status": run.status.value,
        "agent_plan": {
            "skill_id": "ai-native-workflow-orchestration",
            "workflow_plan": plan.to_dict(),
            "route": run.route,
            "profile": run.profile,
            "authority_id": run.authority_id,
            "backend": run.backend,
            "call_surface": run.call_surface,
            "modification_method": run.modification_method,
        },
        "ue5_launch": {
            "executable": str(args.ue5_editor.resolve()),
            "launch_mode": ue5_executor.launch_mode,
            "extra_args": list(ue5_executor.extra_args),
            "window_evidence": evidence,
            "all_operations_saw_editor_window": bool(evidence)
            and all(item.get("window_seen") is True for item in evidence.values()),
        },
        "stages_completed": list(run.stages_completed),
        "preserved_relations": sorted(run.preserved_relations),
        "lost_relations": sorted(run.lost_relations),
        "warnings": list(run.warnings),
        "errors": list(run.errors),
        "resume_pointer": run.resume_pointer,
        "artifacts": [artifact.uri for artifact in run.artifacts],
        "files": {
            name: path.is_file()
            for name, path in {
                "from_unreal": bridge / "from-unreal.json",
                "from_blender": bridge / "from-blender.json",
                "export_glb": bridge / "Engine" / "BasicShapes" / "Cube.glb",
                "edit_blend": bridge / "edit.blend",
                "modified_blend": bridge / "modified.blend",
                "result": out / "result.json",
            }.items()
        },
        "output_dir": str(out),
    }
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if run.status.value == "succeeded" and result["ue5_launch"]["all_operations_saw_editor_window"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


