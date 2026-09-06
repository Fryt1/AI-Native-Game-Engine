from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, TypeAlias


class ToolExecutionKind(StrEnum):
    """Execution domain used by a registered project Tool."""

    HOST = "host"
    TRANSFER = "transfer"
    VALIDATOR = "validator"


class ToolCallUsage(StrEnum):
    """Purpose of one call in the current Stage, not a permanent Tool role."""

    EXECUTE = "execute"
    OBSERVE = "observe"
    VERIFY = "verify"
    REPORT = "report"


def _normalized_operation(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """One project-owned executable Tool published by a Toolset."""

    tool_id: str
    operation: str
    execution_kind: ToolExecutionKind
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object"})
    output_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object"})
    metadata: dict[str, Any] = field(default_factory=dict)

    def matches_operation(self, operation: str) -> bool:
        return _normalized_operation(self.operation) == _normalized_operation(operation)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "operation": self.operation,
            "execution_kind": self.execution_kind.value,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class ToolsetDefinition:
    """A discoverable group of project-owned executable Tools."""

    toolset_id: str
    provider_id: str
    tools: tuple[ToolDefinition, ...]
    title: str = ""
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def find_tool(self, *, tool_id: str | None = None, operation: str | None = None) -> ToolDefinition | None:
        matches = tuple(
            tool
            for tool in self.tools
            if (tool_id is None or tool.tool_id == tool_id)
            and (operation is None or tool.matches_operation(operation))
        )
        return matches[0] if len(matches) == 1 else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "toolset_id": self.toolset_id,
            "provider_id": self.provider_id,
            "title": self.title,
            "description": self.description,
            "tools": [tool.to_dict() for tool in self.tools],
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One project-owned Tool selected in a WorkflowPlan."""

    call_id: str
    toolset_id: str
    tool_id: str
    arguments: dict[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    usage: ToolCallUsage = ToolCallUsage.EXECUTE

    @property
    def kind(self) -> str:
        return "tool"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "call_id": self.call_id,
            "toolset_id": self.toolset_id,
            "tool_id": self.tool_id,
            "arguments": self.arguments,
            "depends_on": list(self.depends_on),
            "usage": self.usage.value,
        }


@dataclass(frozen=True, slots=True)
class McpCall:
    """One direct call to a Tool exposed by an MCP Server."""

    call_id: str
    server_id: str
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    usage: ToolCallUsage = ToolCallUsage.EXECUTE

    @property
    def kind(self) -> str:
        return "mcp"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "call_id": self.call_id,
            "server_id": self.server_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "depends_on": list(self.depends_on),
            "usage": self.usage.value,
        }


ExecutionCall: TypeAlias = ToolCall | McpCall
