"""Run one project ToolCall from the CLI.

Agent usage example:

    python -m ainative.tools run \
      --toolset blender.editor \
      --tool blender.editor.set-location \
      --task task.json \
      --args '{"x":1,"y":2}'

The runner:
  1. builds a RuntimeContext from JSON configuration,
  2. resolves the exact ToolCall through the Project Tool Registry,
  3. executes the project Tool,
  4. prints a structured ExecutionResult on stdout,
  5. exits non-zero when the result is not succeeded.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ainative.cli.execute import (
    ToolExecutionContext,
    execute_resolved,
    to_execution_result,
)
from ainative.orchestration import RuntimeContext
from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.orchestration.contracts.results import TaskStatus
from ainative.orchestration.contracts.task import TaskContract, TaskRoute
from ainative.orchestration.contracts.tools import ToolCall, ToolCallUsage
from ainative.registry import tool_id_for
from ainative.toolsets.blender_editor.execution import BlenderExecutor
from ainative.toolsets.transfer_assetsbridge import (
    AssetsBridgeBackend,
    AssetsBridgeJsonProtocol,
    JsonUE5BridgeConnector,
    LocalBlenderBridgeConnector,
)
from ainative.toolsets.transfer_direct import DirectTransferBackend, FileTransferIO
from ainative.toolsets.ue5_editor.execution import UnrealEditorPythonExecutor
from ainative.toolsets.validation_workflow import (
    AssetsBridgeValidator,
    ManifestValidator,
)


def build_runtime(config: dict[str, Any]) -> RuntimeContext:
    """Build a RuntimeContext from a minimal JSON configuration.

    Configuration example:
    {
      "blender": {"executable": "E:/Blender/blender.exe"},
      "ue5": {
        "executable": "D:/UnrealEngine/ue5.7.1/UnrealEngine/Engine/Binaries/Win64/UnrealEditor-Cmd.exe",
        "project": "D:/project/Game.uproject",
        "script": "D:/work/AI-Native-Game-Engine/src/ainative/toolsets/ue5_editor/execution/bridge_entry.py"
      },
      "assetsbridge": {"directory": "D:/bridge"}
    }
    """

    blender = None
    blender_conf = config.get("blender")
    if blender_conf:
        from ainative.orchestration.contracts.task import BlenderCallSurface
        from ainative.toolsets.blender_editor.execution import BlenderCliSurface
        surface = BlenderCliSurface(executable=blender_conf.get("executable"))
        blender = BlenderExecutor({BlenderCallSurface.CLI_PYTHON: surface})

    ue5 = None
    ue5_conf = config.get("ue5")
    if ue5_conf:
        ue5 = UnrealEditorPythonExecutor(
            executable=ue5_conf["executable"],
            project_file=ue5_conf["project"],
            script=ue5_conf["script"],
            launch_mode=ue5_conf.get("launch_mode", "commandlet"),
            timeout=int(ue5_conf.get("timeout", 300)),
        )

    transfer_backends = {}
    ab_conf = config.get("assetsbridge")
    if ab_conf:
        bridge_dir = Path(ab_conf["directory"])
        protocol = AssetsBridgeJsonProtocol(bridge_dir)
        if blender is None:
            raise ValueError("assetsbridge config requires blender config")
        from ainative.orchestration.contracts.task import (
            BlenderCallSurface,
            TransferBackendKind,
        )
        from ainative.toolsets.blender_editor.execution import BlenderCliSurface
        surface = BlenderCliSurface(executable=(config.get("blender") or {}).get("executable"))
        backend = AssetsBridgeBackend(
            JsonUE5BridgeConnector(protocol),
            LocalBlenderBridgeConnector(blender, bridge_dir, BlenderCallSurface.CLI_PYTHON),
        )
        transfer_backends[TransferBackendKind.ASSETSBRIDGE] = backend

    direct_conf = config.get("direct")
    if direct_conf:
        from ainative.orchestration.contracts.task import TransferBackendKind
        transfer_backends[TransferBackendKind.DIRECT] = DirectTransferBackend(FileTransferIO())

    validator = None
    if "assetsbridge" in config:
        validator = AssetsBridgeValidator(AssetsBridgeJsonProtocol(Path(config["assetsbridge"]["directory"])))
    elif "validator" in config or ue5 is not None:
        validator = ManifestValidator()

    return RuntimeContext(
        blender=blender,
        ue5=ue5,
        transfer_backends=transfer_backends,
        validator=validator,
    )


def run_tool_call(args: argparse.Namespace) -> int:
    raw_config = json.loads(Path(args.config).read_text(encoding="utf-8")) if args.config else {}
    runtime = build_runtime(raw_config)
    task = None
    if args.task:
        raw = json.loads(Path(args.task).read_text(encoding="utf-8"))
        task = TaskContract(
            task_id=raw.get("task_id", "cli-task"),
            objective=raw.get("objective", ""),
            route=TaskRoute(raw.get("route", "host_operation")),
            profile=raw.get("profile", "default"),
            metadata=raw.get("metadata", {}),
            preserve_relations=frozenset(raw.get("preserve_relations", [])),
            acceptable_loss=frozenset(raw.get("acceptable_loss", [])),
            source_context=raw.get("source_context", {}),
            target_context=raw.get("target_context", {}),
        )
    arguments = json.loads(args.args) if args.args else {}
    call = ToolCall(
        call_id=args.call_id or "cli-call",
        toolset_id=args.toolset,
        tool_id=args.tool if args.tool else tool_id_for(args.toolset, args.operation),
        arguments=arguments,
        usage=ToolCallUsage(args.usage),
    )
    ctx = ToolExecutionContext(task=task, task_metadata=(task.metadata if task else None))
    if task is not None:
        ctx.manifest = TransferManifest.from_task(task)
    try:
        resolved = runtime.resolve_tool(call)
        task_result = execute_resolved(runtime, call, resolved, ctx)
    except Exception as exc:  # noqa: BLE001 - CLI must return JSON even on config errors
        result = {
            "status": "blocked",
            "call_id": call.call_id,
            "kind": "tool",
            "toolset_id": call.toolset_id,
            "tool_id": call.tool_id,
            "outputs": {},
            "artifacts": [],
            "warnings": [],
            "errors": [str(exc)],
            "resume_pointer": call.call_id,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    result = to_execution_result(call, task_result)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.status in {TaskStatus.SUCCEEDED, TaskStatus.DEGRADED} else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ainative.tools")
    parser.add_argument("--config", help="JSON file describing host/runtime providers")
    parser.add_argument("--task", help="JSON TaskContract file")
    parser.add_argument("--toolset", required=True)
    parser.add_argument("--tool", help="exact tool_id; defaults to toolset + operation")
    parser.add_argument("--operation", help="published operation name")
    parser.add_argument("--args", default="{}", help="JSON arguments object")
    parser.add_argument("--call-id", default="cli-call")
    parser.add_argument("--usage", default="execute", choices=["execute", "observe", "verify", "report"])
    args = parser.parse_args(argv)
    if not args.tool and not args.operation:
        parser.error("--tool or --operation is required")
    return run_tool_call(args)


if __name__ == "__main__":
    raise SystemExit(main())
