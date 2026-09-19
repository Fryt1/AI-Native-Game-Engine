"""Shared artifact reference model.

An ArtifactRef is a reference to a file a call produced. It is not tied to a
generator-specific seam, and it is deliberately small: the engine stores these and
exposes them as evidence, so a check can address `artifact_count` or `artifacts`,
but nothing in this repository classifies or inspects them.

`artifact_id` and `uri` are required, because a reference that names nothing is not
a reference. `metadata` is free-form and optional, for whatever a call wants to
record alongside the file.

Three fields were removed: `kind`, `provider_id`, and `media_type`. All three were
read from a submitted result and written back out, and nothing else -- no engine
code branched on them, no document listed their permitted values, and no code ever
produced a `kind` other than the default. `kind` was the clearest case: it declared
ten artifact types, an Agent could not discover any of them, and every value that
was not the default appeared only in its own enum declaration.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """A produced or staged file reference without knowing its producer."""

    artifact_id: str
    uri: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "uri": self.uri,
            "metadata": self.metadata,
        }
