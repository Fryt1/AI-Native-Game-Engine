from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ArtifactKind(StrEnum):
    IMAGE = "image"
    TEXTURE = "texture"
    MESH = "mesh"
    SKELETAL_MESH = "skeletal_mesh"
    ANIMATION = "animation"
    SCENE = "scene"
    AUDIO = "audio"
    VIDEO = "video"
    BUNDLE = "bundle"
    UNKNOWN = "unknown"


class ArtifactStatus(StrEnum):
    REQUESTED = "requested"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """A produced or staged artifact without knowing its provider implementation."""

    artifact_id: str
    kind: ArtifactKind
    uri: str
    provider_id: str | None = None
    media_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "kind": self.kind.value,
            "uri": self.uri,
            "provider_id": self.provider_id,
            "media_type": self.media_type,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class ArtifactGenerationRequest:
    task_id: str
    objective: str
    kind: ArtifactKind
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderJob:
    job_id: str
    provider_id: str
    status: ArtifactStatus


@dataclass(frozen=True, slots=True)
class ArtifactResult:
    status: ArtifactStatus
    job: ProviderJob
    artifacts: tuple[ArtifactRef, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
