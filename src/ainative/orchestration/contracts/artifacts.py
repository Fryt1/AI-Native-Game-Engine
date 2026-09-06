"""Shared artifact reference model for project Tools and hosts.

ArtifactRef is a generic "produced file reference" used by host, transfer,
and validator Tools. It is not tied to a generator-specific seam; ComfyUI
and similar generators register as ordinary project Tools or MCP servers.
"""

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


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """A produced or staged file reference without knowing its producer."""

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
