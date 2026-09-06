"""Route guardrails (authorities) for planning gate checks."""

from __future__ import annotations

from dataclasses import dataclass

from ainative.orchestration.contracts.plan import ExecutionPlan, GateResult
from ainative.orchestration.contracts.task import ProfileName, TaskContract, TaskRoute

from .runtime_context import RuntimeContext


def _confirmation_gate(task: TaskContract) -> GateResult | None:
    if not task.confirmation_required:
        return None
    reason = str(task.metadata.get("clarification_reason", "task intent requires confirmation"))
    return GateResult(
        False,
        (f"Task intent requires confirmation: {reason}",),
        next_action="clarify the target host, direction, or requested lifecycle and create a revised TaskContract",
    )


DEFAULT = ProfileName.DEFAULT.value
SUPPORTED_PROFILES = {DEFAULT, ProfileName.INTERACTIVE.value, ProfileName.HEADLESS_BATCH.value}


def _host_readiness_gate(plan: ExecutionPlan, runtime: RuntimeContext) -> GateResult:
    """Shared host readiness check used by route authorities.

    Direct MCP calls are executed by the Agent's configured MCP client. The
    project-side route guard only validates the plan shape; it does not own
    MCP connections or server readiness. Local host execution still requires
    the matching host executor.
    """

    if plan.host_call_surface == "mcp":
        return GateResult(True)
    if plan.host_app == "ue5":
        if runtime.executor("ue5") is None or not runtime.executor("ue5").is_ready():
            return GateResult(False, ("UE5 host executor is not ready",), next_action="make the UE5 Tool executor ready")
        return GateResult(True)
    if runtime.executor("blender") is None or not runtime.executor("blender").can_use(plan.blender_call_surface):
        surface = plan.blender_call_surface.value if plan.blender_call_surface else "unknown"
        return GateResult(False, (f"Blender call surface is not ready: {surface}",), next_action="make the selected Blender call surface ready")
    return GateResult(True)


@dataclass(frozen=True, slots=True)
class HostOperationAuthority:
    """Route guardrail for operations whose primary state is in one host."""

    authority_id: str = "host-operation"
    route: TaskRoute = TaskRoute.HOST_OPERATION
    default_profile: str = DEFAULT

    def supports_profile(self, profile: str) -> bool:
        return profile in SUPPORTED_PROFILES

    def check_preconditions(self, task: TaskContract, plan: ExecutionPlan, runtime: RuntimeContext) -> GateResult:
        if confirmation_gate := _confirmation_gate(task):
            return confirmation_gate
        return _host_readiness_gate(plan, runtime)


@dataclass(frozen=True, slots=True)
class AssetRoundtripAuthority:
    """Route guardrail for an existing asset crossing host boundaries."""

    authority_id: str = "asset-roundtrip"
    route: TaskRoute = TaskRoute.ASSET_TRANSFER
    default_profile: str = DEFAULT

    def supports_profile(self, profile: str) -> bool:
        return profile in SUPPORTED_PROFILES

    def check_preconditions(self, task: TaskContract, plan: ExecutionPlan, runtime: RuntimeContext) -> GateResult:
        if confirmation_gate := _confirmation_gate(task):
            return confirmation_gate
        if plan.host_call_surface == "mcp":
            return GateResult(True)
        blocked: list[str] = []
        source_app = str(task.source_context.get("app", "ue5")).lower()
        target_app = str(task.target_context.get("app", "ue5")).lower()
        if runtime.executor("blender") is None or not runtime.executor("blender").can_use(plan.blender_call_surface):
            surface = plan.blender_call_surface.value if plan.blender_call_surface else "unknown"
            blocked.append(f"Blender call surface is not ready: {surface}")
        if (source_app == "ue5" or target_app == "ue5") and (runtime.executor("ue5") is None or not runtime.executor("ue5").is_ready()):
            blocked.append("UE5 executor is not ready")
        backend = runtime.transfer_backends.get(plan.transfer_backend) if plan.transfer_backend else None
        if backend is None or not backend.is_ready():
            blocked.append(f"transfer backend is not ready: {plan.transfer_backend.value if plan.transfer_backend else 'none'}")
        if plan.transfer_backend is not None and plan.transfer_backend.value == "direct":
            unacceptable = task.preserve_relations - task.acceptable_loss
            if unacceptable:
                blocked.append("Direct Transfer would lose required relations: " + ", ".join(sorted(unacceptable)))
        if runtime.validator is None:
            blocked.append("workflow validator is not configured")
        if blocked:
            return GateResult(False, tuple(blocked), next_action="repair the selected branch or ask the Agent to re-plan")
        return GateResult(True)


@dataclass(frozen=True, slots=True)
class ArtifactApplyAuthority:
    """Route guardrail for applying an external Artifact to a host.

    Generation itself is an ordinary project Tool or an MCP Server tool; the
    route guardrail only checks that the selected host is ready to apply or
    publish the artifact.
    """

    authority_id: str = "artifact-apply"
    route: TaskRoute = TaskRoute.ARTIFACT_PIPELINE
    default_profile: str = DEFAULT

    def supports_profile(self, profile: str) -> bool:
        return profile in SUPPORTED_PROFILES

    def check_preconditions(self, task: TaskContract, plan: ExecutionPlan, runtime: RuntimeContext) -> GateResult:
        if confirmation_gate := _confirmation_gate(task):
            return confirmation_gate
        return _host_readiness_gate(plan, runtime)


ROUTE_AUTHORITIES = {
    TaskRoute.HOST_OPERATION: HostOperationAuthority(),
    TaskRoute.ASSET_TRANSFER: AssetRoundtripAuthority(),
    TaskRoute.ARTIFACT_PIPELINE: ArtifactApplyAuthority(),
}
