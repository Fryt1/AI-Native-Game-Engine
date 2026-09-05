from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from ainative.orchestration.contracts.plan import ExecutionPlan, GateResult
from ainative.orchestration.contracts.task import (
    TaskContract,
    TaskRoute,
    TransferBackendKind,
)
from ainative.orchestration.contracts.tools import ToolCall
from ainative.registry import ResolvedTool, ToolsetRegistry
from ainative.toolsets.ports.artifact_provider import ArtifactProvider
from ainative.toolsets.ports.host_executor import HostExecutor
from ainative.toolsets.ports.transfer_backend import AssetTransferBackend
from ainative.toolsets.ports.validation import WorkflowValidator


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    """Live project Tool providers used for optional plan replay/tests."""

    blender: HostExecutor | None = None
    ue5: HostExecutor | None = None
    host_executors: Mapping[str, HostExecutor] = field(default_factory=dict)
    transfer_backends: Mapping[TransferBackendKind, AssetTransferBackend] = field(default_factory=dict)
    artifact_provider: ArtifactProvider | None = None
    artifact_providers: Mapping[str, ArtifactProvider] = field(default_factory=dict)
    validator: WorkflowValidator | None = None

    def tool_providers(self) -> dict[str, object]:
        """Return live providers that publish project Toolsets for this runtime."""

        providers: dict[str, object] = dict(self.host_executors)
        if self.blender is not None:
            providers["blender"] = self.blender
        if self.ue5 is not None:
            providers["ue5"] = self.ue5
        for key, backend in self.transfer_backends.items():
            providers[getattr(key, "value", str(key))] = backend
        if self.artifact_provider is not None:
            providers["artifact-provider"] = self.artifact_provider
            providers[getattr(self.artifact_provider, "provider_id", "artifact-provider")] = self.artifact_provider
        providers.update(self.artifact_providers)
        if self.validator is not None:
            providers["validator"] = self.validator
        return providers

    def tool_registry(self) -> ToolsetRegistry:
        """Create a live Registry view; it is not a per-run capability snapshot."""

        return ToolsetRegistry(self.tool_providers())

    def resolve_tool(self, call: ToolCall) -> ResolvedTool:
        """Resolve an already selected Tool immediately before invocation."""

        return self.tool_registry().resolve_call(call)


class WorkflowAuthority(Protocol):
    authority_id: str
    route: TaskRoute
    default_profile: str

    def supports_profile(self, profile: str) -> bool: ...

    def check_preconditions(self, task: TaskContract, plan: ExecutionPlan, runtime: RuntimeContext) -> GateResult: ...
