"""Exercise the UE5 Actor host Workflow against a real UE5.7 project.

The fixture is created through the normal visible UnrealEditor.exe once, then
Actor read/mutate/save/read-back Stages run through UnrealEditor-Cmd.exe. The
split proves both call surfaces without confusing a visible-window proof with a
headless commandlet proof.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
E2E_ROOT = ROOT / "scripts" / "e2e"
if str(E2E_ROOT) not in sys.path:
    sys.path.insert(0, str(E2E_ROOT))

from support.plan_fixtures import actor_operation_plan, execute_agent_plan
from transfer.run_visible_ue5_assetsbridge_e2e import _visible_editor_runner

from ainative.orchestration import RuntimeContext
from ainative.orchestration.contracts import TaskContract, TaskRoute
from ainative.toolsets.ports.host_executor import HostOperationRequest
from ainative.toolsets.ue5_editor.execution import UnrealEditorPythonExecutor

DEFAULT_EDITOR = Path(r"D:\UnrealEngine\ue5.7.1\UnrealEngine\Engine\Binaries\Win64\UnrealEditor.exe")
DEFAULT_CMD = Path(r"D:\UnrealEngine\ue5.7.1\UnrealEngine\Engine\Binaries\Win64\UnrealEditor-Cmd.exe")
DEFAULT_OUT = ROOT / "artifacts" / "evidence" / "ue5-host-operation"


def ensure_fixture_project(project: Path) -> None:
    project.parent.mkdir(parents=True, exist_ok=True)
    config = project.parent / "Config"
    config.mkdir(parents=True, exist_ok=True)
    if not project.is_file():
        project.write_text(json.dumps({
            "FileVersion": 3,
            "EngineAssociation": "{1683C69B-4C4C-C3FF-9603-2682BDE8A313}",
            "Category": "",
            "Description": "AI Native Actor capability fixture",
            "Plugins": [
                {"Name": "EditorScriptingUtilities", "Enabled": True},
                {"Name": "PythonScriptPlugin", "Enabled": True},
            ],
        }, indent=2), encoding="utf-8")
    default_engine = config / "DefaultEngine.ini"
    if not default_engine.is_file():
        default_engine.write_text("[/Script/EngineSettings.GameMapsSettings]\nGameDefaultMap=/Engine/Maps/Entry\nEditorStartupMap=/Engine/Maps/Entry\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ue5-editor", type=Path, default=DEFAULT_EDITOR)
    parser.add_argument("--ue5-cmd", type=Path, default=DEFAULT_CMD)
    parser.add_argument("--project", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    args.ue5_editor = args.ue5_editor.resolve()
    args.ue5_cmd = args.ue5_cmd.resolve()
    args.out = args.out.resolve()
    args.project = (args.project or (ROOT / "projects" / "fixtures" / "ue5" / "actor-fixture" / "ActorFixture.uproject")).resolve()
    script = ROOT / "src" / "ainative" / "toolsets" / "ue5_editor" / "execution" / "bridge_entry.py"
    missing = [str(path) for path in (args.ue5_editor, args.ue5_cmd, script) if not path.is_file()]
    if missing:
        print(json.dumps({"status": "blocked", "missing": missing}, ensure_ascii=False, indent=2))
        return 2
    ensure_fixture_project(args.project)
    args.out.mkdir(parents=True, exist_ok=True)

    visible = UnrealEditorPythonExecutor(args.ue5_editor, args.project, script, runner=_visible_editor_runner, timeout=args.timeout, launch_mode="editor")
    visible_operation = "list_actors"
    create = visible.execute(HostOperationRequest(
        task_id="actor-fixture-list",
        operation="list_actors",
        parameters={"result_dir": str(args.out), "level_path": "/Game/AINativeActorE2E"},
    ))
    actor_rows = create.details.get("actors", []) if create.status.value == "succeeded" else []
    existing_actor = next((row for row in actor_rows if row.get("label") == "AINativeActorE2E"), None)
    if existing_actor is None:
        visible_operation = "create_actor"
        create = visible.execute(HostOperationRequest(
            task_id="actor-fixture-create",
            operation="create_actor",
            parameters={"result_dir": str(args.out), "level_path": "/Game/AINativeActorE2E", "label": "AINativeActorE2E"},
        ))
        existing_actor = create.details.get("actor") if create.status.value == "succeeded" else None
    if create.status.value != "succeeded" or existing_actor is None:
        payload = {"status": create.status.value, "create": create.to_dict()}
        (args.out / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    actor_path = existing_actor["path"]

    task = TaskContract(
        task_id="ue5-actor-workflow",
        objective="Move an Actor in a UE5 level",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "ue5"},
        metadata={
            "operation": "set-actor-transform",
            "read_operation": "read_actor_transform",
            "publish_operation": "save_level",
            "level_path": "/Game/AINativeActorE2E",
            "actor_path": actor_path,
            "location": [250, 50, 75],
            "expected_location": [250, 50, 75],
            "result_dir": str(args.out),
        },
    )
    commandlet = UnrealEditorPythonExecutor(args.ue5_cmd, args.project, script, timeout=args.timeout, launch_mode="commandlet")
    plan = actor_operation_plan(task)
    result = execute_agent_plan(task, plan, RuntimeContext(ue5=commandlet))
    ui_evidence = args.out / "ue5" / visible_operation / "editor-ui-evidence.json"
    payload = {
        "status": result.status.value,
        "workflow_id": result.workflow_id,
        "route": result.route,
        "steps_completed": list(result.steps_completed),
        "stages_completed": list(result.stages_completed),
        "stage_results": [stage.to_dict() for stage in result.stage_results],
        "actor_path": actor_path,
        "visible_editor_evidence": json.loads(ui_evidence.read_text(encoding="utf-8")) if ui_evidence.is_file() else None,
        "files": {"fixture_project": args.project.is_file(), "fixture_level": (args.project.parent / "Content" / "AINativeActorE2E.umap").is_file()},
        "warnings": list(result.warnings),
        "errors": list(result.errors),
        "output_dir": str(args.out),
    }
    (args.out / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.status.value == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())


