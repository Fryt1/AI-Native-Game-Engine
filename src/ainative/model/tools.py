"""The call a Workflow declares.

A call names *what the Agent will invoke*. There are two kinds, and both are
first-class here because both are real work:

    project Tool   a Tool implemented in this repository
    MCP call       a tool on a host's own MCP server, invoked by the Agent's client

Both carry a target and arguments. This repository does not execute either one —
the Agent does. What the contract provides is enough structure for the Workflow to
declare its calls, their order, and what each result must prove.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .coercion import coerce_enum


class CallKind(StrEnum):
    """Where a declared call is executed."""

    PROJECT_TOOL = "project_tool"
    MCP = "mcp"


@dataclass(frozen=True, slots=True)
class CallTarget:
    """The exact thing a call invokes.

    For a project Tool, ``owner`` is the Toolset id and ``name`` the Tool id.
    For an MCP call, ``owner`` is the MCP server name and ``name`` the tool name
    on that server. One shape covers both because the Agent, not this repository,
    resolves them.
    """

    owner: str
    name: str

    def to_dict(self) -> dict[str, str]:
        return {"owner": self.owner, "name": self.name}


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One call the Agent declared in its Workflow."""

    call_id: str
    target: CallTarget
    kind: CallKind = CallKind.MCP
    arguments: dict[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        coerce_enum(self, "kind", CallKind)

    @property
    def qualified_name(self) -> str:
        """Return ``owner/name`` for messages and evidence references."""

        return f"{self.target.owner}/{self.target.name}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "kind": self.kind.value,
            "target": self.target.to_dict(),
            "arguments": self.arguments,
            "depends_on": list(self.depends_on),
        }
