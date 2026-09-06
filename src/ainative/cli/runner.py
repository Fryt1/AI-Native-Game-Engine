"""Run one exact project ToolCall from the CLI.

The CLI is an execution boundary, not a WorkflowPlan scheduler. When a Task
Contract is supplied it derives the same coarse runtime selection as the Agent
so transfer and host-specific Tools receive the correct execution context.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
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
from ainative.orchestration.contracts.task import (
    BlenderCallSurface,
    TaskContract,
    TaskRoute,
    TransferBackendKind,
)
from ainative.orchestration.contracts.tools import ToolCall, ToolCallUsage
from ainative.orchestration.planning import select_workflow
from ainative.registry import tool_id_for
from ainative.toolsets.blender_editor.execution import (
    BlenderCliSurface,
    BlenderExecutor,
)
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


def _safe_path_token(value: str) -> str:
    return "".join(character if character.isalnum() or character in "-_." else "_" for character in value) or "task"


def task_from_dict(raw: dict[str, Any]) -> TaskContract:
    """Deserialize the complete TaskContract surface used by the CLI."""

    if not isinstance(raw, dict):
        raise TypeError("task JSON must be an object")
    preferred_backend = raw.get("preferred_backend")
    preferred_surface = raw.get("preferred_call_surface")
    return TaskContract(
        task_id=str(raw.get("task_id", "cli-task")),
        objective=str(raw.get("objective", "")),
        route=TaskRoute(raw.get("route", TaskRoute.HOST_OPERATION.value)),
        profile=str(raw.get("profile", "default")),
        asset_type=str(raw.get("asset_type", "unknown")),
        direction=str(raw.get("direction", "none")),
        preserve_relations=frozenset(raw.get("preserve_relations", [])),
        acceptable_loss=frozenset(raw.get("acceptable_loss", [])),
        destructive=bool(raw.get("destructive", False)),
        preferred_backend=TransferBackendKind(preferred_backend) if preferred_backend else None,
        preferred_call_surface=BlenderCallSurface(preferred_surface) if preferred_surface else None,
        preferred_provider_id=raw.get("preferred_provider_id"),
        preferred_workflow_id=raw.get("preferred_workflow_id"),
        source_context=dict(raw.get("source_context", {})),
        target_context=dict(raw.get("target_context", {})),
        confirmation_required=bool(raw.get("confirmation_required", False)),
        metadata=dict(raw.get("metadata", {})),
    )


def build_runtime(config: dict[str, Any]) -> RuntimeContext:
    """Build a RuntimeContext from a minimal JSON configuration.

    AssetsBridge uses the real UE5 executor when one is configured. The JSON
    connector remains available only as a protocol-only test seam for runtimes
    that intentionally do not configure UE5.
    """

    if not isinstance(config, dict):
        raise TypeError("runtime config must be an object")

    blender = None
    blender_conf = config.get("blender")
    if blender_conf:
        surface = BlenderCliSurface(
            executable=blender_conf.get("executable"),
            timeout=int(blender_conf.get("timeout", 300)),
        )
        blender = BlenderExecutor({BlenderCallSurface.CLI_PYTHON: surface})

    assetsbridge_conf = config.get("assetsbridge")
    ue5 = None
    ue5_conf = config.get("ue5")
    if ue5_conf:
        ue5 = UnrealEditorPythonExecutor(
            executable=ue5_conf["executable"],
            project_file=ue5_conf["project"],
            script=ue5_conf["script"],
            bridge_dir=Path(assetsbridge_conf["directory"]) if assetsbridge_conf else None,
            launch_mode=ue5_conf.get("launch_mode", "commandlet"),
            timeout=int(ue5_conf.get("timeout", 300)),
        )

    transfer_backends = {}
    if assetsbridge_conf:
        bridge_dir = Path(assetsbridge_conf["directory"])
        bridge_dir.mkdir(parents=True, exist_ok=True)
        protocol = AssetsBridgeJsonProtocol(bridge_dir)
        if blender is None:
            raise ValueError("assetsbridge config requires blender config")
        if ue5 is None and not bool(assetsbridge_conf.get("protocol_only", False)):
            raise ValueError("assetsbridge config requires ue5 config unless protocol_only=true")
        ue5_connector = ue5 if ue5 is not None else JsonUE5BridgeConnector(protocol)
        backend = AssetsBridgeBackend(
            ue5_connector,
            LocalBlenderBridgeConnector(
                blender,
                bridge_dir,
                BlenderCallSurface.CLI_PYTHON,
            ),
        )
        transfer_backends[TransferBackendKind.ASSETSBRIDGE] = backend

    if "direct" in config:
        transfer_backends[TransferBackendKind.DIRECT] = DirectTransferBackend(FileTransferIO())

    validator = None
    if assetsbridge_conf:
        validator = AssetsBridgeValidator(AssetsBridgeJsonProtocol(Path(assetsbridge_conf["directory"])))
    elif "validator" in config or ue5 is not None:
        validator = ManifestValidator()

    executors = {}
    if blender is not None:
        executors["blender"] = blender
    if ue5 is not None:
        executors["ue5"] = ue5
    return RuntimeContext(
        executors=executors,
        transfer_backends=transfer_backends,
        validator=validator,
    )


def _blocked_payload(args: argparse.Namespace, error: Exception) -> dict[str, Any]:
    operation = args.operation or ""
    tool_id = args.tool or (tool_id_for(args.toolset, operation) if operation else "")
    return {
        "status": "blocked",
        "call_id": args.call_id or "cli-call",
        "kind": "tool",
        "toolset_id": args.toolset,
        "tool_id": tool_id,
        "outputs": {},
        "artifacts": [],
        "warnings": [],
        "errors": [str(error)],
        "resume_pointer": args.call_id or "cli-call",
    }


def run_tool_call(args: argparse.Namespace) -> int:
    try:
        raw_config = json.loads(Path(args.config).read_text(encoding="utf-8")) if args.config else {}
        runtime = build_runtime(raw_config)
        task = None
        if args.task:
            task = task_from_dict(json.loads(Path(args.task).read_text(encoding="utf-8")))

        arguments = json.loads(args.args) if args.args else {}
        if not isinstance(arguments, dict):
            raise TypeError("--args must be a JSON object")
        call = ToolCall(
            call_id=args.call_id or "cli-call",
            toolset_id=args.toolset,
            tool_id=args.tool if args.tool else tool_id_for(args.toolset, args.operation),
            arguments=arguments,
            usage=ToolCallUsage(args.usage),
    )
        ctx = ToolExecutionContext(task=task, task_metadata=(dict(task.metadata) if task else None))
        if task is not None:
            selection = select_workflow(task)
            ctx.plan_route = selection.route.value
            ctx.plan_host_app = selection.host_app
            ctx.plan_host_call_surface = selection.host_call_surface
            ctx.plan_blender_call_surface = selection.blender_call_surface.value if selection.blender_call_surface else None
            ctx.plan_transfer_backend = selection.transfer_backend.value if selection.transfer_backend else None
            manifest = TransferManifest.from_task(task).with_execution_selection(
                backend=selection.transfer_backend.value if selection.transfer_backend else None,
                modification_method=selection.modification_method,
                call_surface=selection.host_call_surface or (
                    selection.blender_call_surface.value if selection.blender_call_surface else None
                ),
                workflow_id=selection.workflow_id,
            )
            if selection.transfer_backend is TransferBackendKind.ASSETSBRIDGE and raw_config.get("assetsbridge"):
                bridge_root = Path(raw_config["assetsbridge"]["directory"])
                transfer_bridge = bridge_root / _safe_path_token(task.task_id)
                transfer_bridge.mkdir(parents=True, exist_ok=True)
                manifest = replace(
                    manifest,
                    metadata={**manifest.metadata, "bridge_dir": str(transfer_bridge)},
                )
            ctx.manifest = manifest

        resolved = runtime.resolve_tool(call)
        task_result = execute_resolved(runtime, call, resolved, ctx)
        result = to_execution_result(call, task_result)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))
        return 0 if result.status in {TaskStatus.SUCCEEDED, TaskStatus.DEGRADED} else 1
    except Exception as exc:  # noqa: BLE001 - CLI must always return structured JSON
        print(json.dumps(_blocked_payload(args, exc), ensure_ascii=False, indent=2, default=str))
        return 2


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
