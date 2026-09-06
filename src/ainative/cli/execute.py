"""Generic Project Tool execution for the CLI/Agent boundary.

This module knows how to dispatch one resolved Project ToolCall to its owner
implementation. It is intentionally separate from WorkflowSession: WorkflowSession
only validates submitted results, while this module is what an Agent (or a test
runner) invokes before submitting those results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ainative.orchestration import RuntimeContext
from ainative.orchestration.contracts.manifest import TransferManifest
from ainative.orchestration.contracts.plan import StageRequest
from ainative.orchestration.contracts.results import (
    ExecutionResult,
    TaskResult,
    TaskStatus,
)
from ainative.orchestration.contracts.task import TaskContract
from ainative.orchestration.contracts.tools import ToolCall, ToolExecutionKind
from ainative.registry import ResolvedTool
from ainative.toolsets.ports.host_executor import HostOperationRequest


@dataclass(slots=True)
class ToolExecutionContext:
    task: TaskContract | None = None
    stage: StageRequest | None = None
    manifest: TransferManifest | None = None
    plan_route: str = "host_operation"
    plan_host_app: str = "blender"
    plan_host_call_surface: str | None = None
    plan_blender_call_surface: str | None = None
    plan_transfer_backend: str | None = None
    task_metadata: dict[str, Any] | None = None


def execute_resolved(
    runtime: RuntimeContext,
    call: ToolCall,
    resolved: ResolvedTool,
    ctx: ToolExecutionContext | None = None,
) -> TaskResult:
    ctx = ctx or ToolExecutionContext()
    kind = resolved.tool.execution_kind
    provider = resolved.provider
    operation = resolved.tool.operation
    manifest = ctx.manifest
    metadata = ctx.task_metadata or (ctx.task.metadata if ctx.task else {})

    if kind is ToolExecutionKind.HOST:
        parameters = dict(metadata)
        parameters.update(call.arguments)
        parameters.update({
            "stage_id": ctx.stage.stage_id if ctx.stage else "",
            "tool_call_id": call.call_id,
            "manifest": manifest,
        })
        request = HostOperationRequest(
            task_id=f"{ctx.task.task_id if ctx.task else 'cli'}-{ctx.stage.stage_id if ctx.stage else ''}-{call.call_id}",
            operation=operation,
            call_surface=(
                ctx.plan_blender_call_surface
                if ctx.plan_host_app == "blender" and ctx.plan_blender_call_surface
                else ctx.plan_host_call_surface
            ),
            parameters=parameters,
        )
        return provider.execute(request)

    if kind is ToolExecutionKind.TRANSFER:
        if manifest is None:
            if ctx.task is not None:
                manifest = TransferManifest.from_task(ctx.task)
            else:
                return TaskResult(status=TaskStatus.BLOCKED, route=ctx.plan_route, errors=("Transfer Tool requires a TaskContract or manifest",))
        is_direct = ctx.plan_transfer_backend == "direct"
        if operation == "transfer_to_edit_host":
            first = provider.export_source(manifest)
            if first.status is not TaskStatus.SUCCEEDED:
                return first
            second = _direct_blender_import(runtime, manifest, ctx) if is_direct else provider.import_for_edit(manifest)
            return _combine(first, second, ctx.plan_route)
        if operation == "return_to_target":
            first = _direct_blender_export(runtime, manifest, ctx) if is_direct else provider.export_modified(manifest)
            if first.status is not TaskStatus.SUCCEEDED:
                return first
            second = provider.import_target(manifest)
            return _combine(first, second, ctx.plan_route)
        fn = getattr(provider, operation, None)
        if not callable(fn):
            return TaskResult(status=TaskStatus.BLOCKED, route=ctx.plan_route, errors=(f"Transfer Tool has no implementation: {operation}",))
        return fn(manifest)

    if kind is ToolExecutionKind.VALIDATOR:
        if manifest is None:
            if ctx.task is not None:
                manifest = TransferManifest.from_task(ctx.task)
            else:
                return TaskResult(status=TaskStatus.BLOCKED, route=ctx.plan_route, errors=("Validator Tool requires a TaskContract or manifest",))
        validate = getattr(provider, operation, None)
        if not callable(validate):
            return TaskResult(status=TaskStatus.BLOCKED, route=ctx.plan_route, errors=(f"Validator Tool has no implementation: {operation}",))
        return validate(ctx.task, manifest)

def to_execution_result(call: ToolCall, result: TaskResult) -> ExecutionResult:
    return ExecutionResult(
        call_id=call.call_id,
        kind="tool",
        toolset_id=call.toolset_id,
        tool_id=call.tool_id,
        status=result.status,
        outputs=dict(result.details),
        artifacts=result.artifacts,
        warnings=result.warnings,
        errors=result.errors,
        resume_pointer=result.resume_pointer,
        preserved_relations=frozenset(result.preserved_relations),
        lost_relations=frozenset(result.lost_relations),
    )


def _direct_blender_import(runtime: RuntimeContext, manifest: TransferManifest, ctx: ToolExecutionContext) -> TaskResult:
    if runtime.executor("blender") is None:
        return TaskResult(status=TaskStatus.BLOCKED, route=ctx.plan_route, errors=("Direct Transfer requires the Blender edit host",))
    metadata = ctx.task_metadata or (ctx.task.metadata if ctx.task else {})
    params = dict(metadata)
    params.update({"filepath": manifest.export_file, "blend_file": None, "save_after": metadata.get("blender_edit_file")})
    return runtime.executor("blender").execute(HostOperationRequest(
        task_id=f"{ctx.task.task_id if ctx.task else 'cli'}-transfer-import",
        operation="import-glb",
        call_surface=ctx.plan_blender_call_surface,
        parameters=params,
    ))


def _direct_blender_export(runtime: RuntimeContext, manifest: TransferManifest, ctx: ToolExecutionContext) -> TaskResult:
    if runtime.executor("blender") is None:
        return TaskResult(status=TaskStatus.BLOCKED, route=ctx.plan_route, errors=("Direct Transfer requires the Blender edit host",))
    metadata = ctx.task_metadata or (ctx.task.metadata if ctx.task else {})
    params = dict(metadata)
    params.update({"filepath": manifest.export_file})
    if metadata.get("modified_blend_file"):
        params["blend_file"] = metadata["modified_blend_file"]
    return runtime.executor("blender").execute(HostOperationRequest(
        task_id=f"{ctx.task.task_id if ctx.task else 'cli'}-return-export",
        operation="export-glb",
        call_surface=ctx.plan_blender_call_surface,
        parameters=params,
    ))


def _combine(first: TaskResult, second: TaskResult, route: str) -> TaskResult:
    artifacts = list(first.artifacts)
    seen = {a.artifact_id for a in first.artifacts}
    for a in second.artifacts:
        if a.artifact_id not in seen:
            artifacts.append(a)
            seen.add(a.artifact_id)
    details = dict(first.details)
    details.update(second.details)
    status = second.status if second.status is not TaskStatus.SUCCEEDED else first.status
    return TaskResult(
        status=status,
        route=route,
        artifacts=tuple(artifacts),
        details=details,
        warnings=first.warnings + second.warnings,
        errors=first.errors + second.errors,
        resume_pointer=second.resume_pointer or first.resume_pointer,
        preserved_relations=frozenset(first.preserved_relations | second.preserved_relations),
        lost_relations=frozenset(first.lost_relations | second.lost_relations),
    )
