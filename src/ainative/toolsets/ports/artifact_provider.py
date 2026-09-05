from typing import Protocol

from ainative.orchestration.contracts.artifacts import (
    ArtifactGenerationRequest,
    ArtifactResult,
    ProviderJob,
)
from ainative.orchestration.contracts.tools import ToolsetDefinition


class ArtifactProvider(Protocol):
    """Seam for ComfyUI or another artifact-producing provider."""

    provider_id: str

    def is_ready(self) -> bool: ...

    def toolsets(self) -> tuple[ToolsetDefinition, ...]: ...

    def submit(self, request: ArtifactGenerationRequest) -> ProviderJob: ...

    def get_result(self, job_id: str) -> ArtifactResult: ...
