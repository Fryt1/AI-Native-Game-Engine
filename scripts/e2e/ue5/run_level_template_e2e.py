"""Exercise the UE5 Level template Stage against a real UE5 project."""

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

from support.plan_fixtures import execute_agent_plan, level_template_plan
from transfer.run_visible_ue5_assetsbridge_e2e import _visible_editor_runner

from ainative.orchestration import RuntimeContext
from ainative.orchestration.contracts import TaskContract, TaskRoute
from ainative.toolsets.ue5_editor.execution import UnrealEditorPythonExecutor

DEFAULT_EDITOR = Path(r"D:\UnrealEngine\ue5.7.1\UnrealEngine\Engine\Binaries\Win64\UnrealEditor.exe")
DEFAULT_CMD = Path(r"D:\UnrealEngine\ue5.7.1\UnrealEngine\Engine\Binaries\Win64\UnrealEditor-Cmd.exe")
DEFAULT_PROJECT = ROOT / "projects" / "fixtures" / "ue5" / "level-template-fixture" / "LevelTemplateFixture.uproject"
DEFAULT_SCRIPT = ROOT / "src" / "ainative" / "toolsets" / "ue5_editor" / "execution" / "bridge_entry.py"
DEFAULT_OUT = ROOT / "artifacts" / "evidence" / "ue5-level-template"
DEFAULT_TEMPLATE = "/Engine/Maps/Templates/Template_Default"
DEFAULT_TARGET = "/Game/DefaultLightingLevel"
DEFAULT_EXPECTED = ("DirectionalLight", "SkyLight")


def ensure_fixture_project(project: Path) -> None:
    project.parent.mkdir(parents=True, exist_ok=True)
    config = project.parent / "Config"
    config.mkdir(parents=True, exist_ok=True)
    if not project.is_file():
        project.write_text(
            json.dumps(
                {
                    "FileVersion": 3,
                    "EngineAssociation": "{1683C69B-4C4C-C3FF-9603-2682BDE8A313}",
                    "Category": "",
                    "Description": "AI Native UE5 Level template capability fixture",
                    "Plugins": [
                        {"Name": "EditorScriptingUtilities", "Enabled": True},
                        {"Name": "PythonScriptPlugin", "Enabled": True},
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    default_engine = config / "DefaultEngine.ini"
    if not default_engine.is_file():
        default_engine.write_text(
            "[/Script/EngineSettings.GameMapsSettings]\n"
            "GameDefaultMap=/Engine/Maps/Entry\n"
            "EditorStartupMap=/Engine/Maps/Entry\n",
            encoding="utf-8",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ue5-editor", type=Path, default=DEFAULT_EDITOR)
    parser.add_argument("--ue5-cmd", type=Path, default=DEFAULT_CMD)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--template", default=DEFAULT_TEMPLATE)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--launch-mode", choices=("commandlet", "editor"), default="commandlet")
    parser.add_argument("--no-reuse", action="store_true", help="fail if the target Level already exists")
    args = parser.parse_args()

    executable = (args.ue5_editor if args.launch_mode == "editor" else args.ue5_cmd).resolve()
    project = args.project.resolve()
    out = args.out.resolve()
    script = DEFAULT_SCRIPT.resolve()
    missing = [str(path) for path in (executable, project, script) if not path.is_file()]
    if missing:
        print(json.dumps({"status": "blocked", "missing": missing}, ensure_ascii=False, indent=2))
        return 2

    ensure_fixture_project(project)
    out.mkdir(parents=True, exist_ok=True)
    executor = UnrealEditorPythonExecutor(
        executable,
        project,
        script,
        runner=_visible_editor_runner if args.launch_mode == "editor" else None,
        timeout=args.timeout,
        launch_mode=args.launch_mode,
    )
    task = TaskContract(
        task_id="ue5-level-template-workflow",
        objective="Create and open a UE5 Level from the default lighting template",
        route=TaskRoute.HOST_OPERATION,
        target_context={"app": "ue5"},
        metadata={
            "operation": "create_level_from_template",
            "template": args.template,
            "target": args.target,
            "expected_default_objects": list(DEFAULT_EXPECTED),
            "reuse_existing": not args.no_reuse,
            "result_dir": str(out),
        },
    )
    plan = level_template_plan(task)
    result = execute_agent_plan(task, plan, RuntimeContext(executors={"ue5": executor}))
    editor_evidence_path = out / "ue5" / "create_level_from_template" / "editor-ui-evidence.json"
    payload = {
        "status": result.status.value,
        "skill_id": "ai-native-workflow-orchestration",
        "route": result.route,
        "workflow_id": result.workflow_id,
        "profile": result.profile,
        "authority_id": result.authority_id,
        "call_surface": result.call_surface,
        "modification_method": result.modification_method,
        "steps_completed": list(result.steps_completed),
        "stages_completed": list(result.stages_completed),
        "stage_results": [stage.to_dict() for stage in result.stage_results],
        "artifacts": [artifact.to_dict() for artifact in result.artifacts],
        "warnings": list(result.warnings),
        "errors": list(result.errors),
        "resume_pointer": result.resume_pointer,
        "project": str(project),
        "template": args.template,
        "target": args.target,
        "launch_mode": args.launch_mode,
        "editor_window_evidence": json.loads(editor_evidence_path.read_text(encoding="utf-8")) if editor_evidence_path.is_file() else None,
        "output_dir": str(out),
    }
    (out / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.status.value == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
