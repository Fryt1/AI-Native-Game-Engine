from typing import Protocol

from ainative.orchestration.contracts.tools import ToolsetDefinition


class ToolsetProvider(Protocol):
    """Runtime provider that publishes project-owned Toolsets."""

    def toolsets(self) -> tuple[ToolsetDefinition, ...]: ...
