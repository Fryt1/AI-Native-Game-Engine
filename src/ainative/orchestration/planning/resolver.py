from __future__ import annotations

from dataclasses import replace

from ainative.orchestration.contracts.plan import WorkflowSelection
from ainative.orchestration.contracts.task import (
    BlenderCallSurface,
    ProfileName,
    TaskContract,
    TaskRoute,
    TransferBackendKind,
)
from ainative.orchestration.route_guards import ROUTE_AUTHORITIES


class RouteResolutionError(ValueError):
    """The request cannot select a declared Route and active Profile."""


class UnsupportedRoute(RouteResolutionError):
    pass


class UnsupportedProfile(RouteResolutionError):
    pass


def _host_app(task: TaskContract) -> str:
    return str(
        task.target_context.get("app")
        or task.source_context.get("app")
        or task.metadata.get("host_app")
        or "blender"
    ).lower()


def _blender_surface(task: TaskContract, fallback: BlenderCallSurface) -> BlenderCallSurface:
    if task.preferred_call_surface:
        return task.preferred_call_surface
    if task.profile == ProfileName.HEADLESS_BATCH.value:
        return BlenderCallSurface.CLI_PYTHON
    if task.profile == ProfileName.INTERACTIVE.value:
        return BlenderCallSurface.ADDON
    return fallback


def select_workflow(task: TaskContract) -> WorkflowSelection:
    """Select only the Route/Workflow context the Agent should read.

    This function intentionally does not construct Steps, Stages, Tool Calls,
    or an executable plan. The Agent reads the selected Workflow document and
    authors the concrete WorkflowPlan.
    """

    authority = ROUTE_AUTHORITIES.get(task.route)
    if authority is None:
        raise UnsupportedRoute(f"unsupported route: {task.route}")
    profile = task.profile or authority.default_profile
    if not authority.supports_profile(profile):
        raise UnsupportedProfile(f"unsupported profile for {task.route.value}: {profile}")
    if profile != task.profile:
        task = replace(task, profile=profile)

    if task.route is TaskRoute.HOST_OPERATION:
        host_app = _host_app(task)
        workflow_id = task.preferred_workflow_id or (
            "native-blender-operation" if host_app == "blender" else "host-operation"
        )
        if workflow_id not in {"host-operation", "native-blender-operation"}:
            raise RouteResolutionError(f"unsupported host-operation workflow: {workflow_id}")
        if host_app == "ue5":
            return WorkflowSelection(
                workflow_id=workflow_id,
                route=task.route,
                profile=profile,
                authority_id=authority.authority_id,
                modification_method="host_operation",
                host_app="ue5",
                host_call_surface=str(task.metadata.get("ue5_call_surface", "ue5-python")),
            )
        surface = _blender_surface(task, BlenderCallSurface.CLI_PYTHON)
        return WorkflowSelection(
            workflow_id=workflow_id,
            route=task.route,
            profile=profile,
            authority_id=authority.authority_id,
            blender_call_surface=surface,
            modification_method="native_host_operation",
            host_app="blender",
            host_call_surface=surface.value,
        )

    if task.route is TaskRoute.ASSET_TRANSFER:
        backend = task.preferred_backend or (
            TransferBackendKind.ASSETSBRIDGE if task.preserve_relations else TransferBackendKind.DIRECT
        )
        surface = _blender_surface(
            task,
            BlenderCallSurface.ADDON if backend is TransferBackendKind.ASSETSBRIDGE else BlenderCallSurface.CLI_PYTHON,
        )
        workflow_id = task.preferred_workflow_id or "asset-roundtrip"
        if workflow_id not in {"asset-roundtrip", "asset-edit"}:
            raise RouteResolutionError(f"unsupported asset-transfer workflow: {workflow_id}")
        return WorkflowSelection(
            workflow_id=workflow_id,
            route=task.route,
            profile=profile,
            authority_id=authority.authority_id,
            transfer_backend=backend,
            blender_call_surface=surface,
            modification_method=(
                "assetsbridge_compatible_asset_edit"
                if backend is TransferBackendKind.ASSETSBRIDGE
                else "direct_transfer_safe_asset_edit"
            ),
            host_app="blender",
            host_call_surface=surface.value,
        )

    host_app = _host_app(task)
    if host_app == "ue5":
        surface = None
        host_surface = str(task.metadata.get("ue5_call_surface", "ue5-python"))
    else:
        surface = _blender_surface(task, BlenderCallSurface.CLI_PYTHON)
        host_surface = surface.value
    workflow_id = task.preferred_workflow_id or "provider-artifact-apply"
    if workflow_id != "provider-artifact-apply":
        raise RouteResolutionError(f"unsupported artifact workflow: {workflow_id}")
    return WorkflowSelection(
        workflow_id=workflow_id,
        route=task.route,
        profile=profile,
        authority_id=authority.authority_id,
        blender_call_surface=surface,
        modification_method="artifact_apply_to_host",
        host_app=host_app,
        host_call_surface=host_surface,
    )
