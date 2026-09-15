"""The call a Workflow declares.

A call names *what the Agent will invoke*: a tool on a host's own MCP server,
invoked by the Agent's own MCP client. The contract carries the target and the
arguments, and nothing else, because this repository executes no call — the Agent
does. What it provides is enough structure for the Workflow to declare its calls,
their order, and what each result must prove.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CallTarget:
    """The exact thing a call invokes: an MCP server and a tool on it.

    ``owner`` is the MCP server name and ``name`` the tool name on that server.
    The Agent's MCP client resolves them; this repository resolves nothing.
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
    arguments: dict[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()

    @property
    def qualified_name(self) -> str:
        """Return ``owner/name`` for messages and evidence references."""

        return f"{self.target.owner}/{self.target.name}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "target": self.target.to_dict(),
            "arguments": self.arguments,
            "depends_on": list(self.depends_on),
        }
