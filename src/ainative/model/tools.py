"""The call a Workflow declares.

A call names *what the Agent will invoke*: a tool on a host's own MCP server,
invoked by the Agent's own MCP client. The contract carries the target and the
arguments, and nothing else, because this repository executes no call — the Agent
does. What it provides is enough structure for the Workflow to declare its calls,
their order, and what each result must prove.
"""

from __future__ import annotations

import hashlib
import json
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


def call_digest(target: CallTarget, arguments: dict[str, Any]) -> str:
    """Return a digest of what a call would DO on the host.

    The repeat guard needs to know whether reporting a result again means applying
    the same host change twice. A call's identity is its target and its arguments --
    that pair is what the host sees. It is deliberately NOT the node's fingerprint:
    a fingerprint covers the goal, the checklists and the children too, so editing a
    checklist would unlock a call whose host effect is byte-for-byte identical, which
    is the repeat the guard exists to prevent.

    ``call_id`` is excluded for the mirror reason: the same host change declared
    under a new id is still the same host change, and renaming it must not launder a
    repeat.

    Arguments are serialised with sorted keys, so two spellings of one mapping agree.
    ``default=str`` matches the fingerprint's own handling of values JSON cannot
    carry directly.

    @param target: the MCP server and tool the call invokes.
    @param arguments: the arguments the call carries.
    @returns a short stable digest.
    """

    payload = json.dumps(
        {"target": target.to_dict(), "arguments": arguments},
        sort_keys=True, default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


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

    @property
    def digest(self) -> str:
        """Return what this call would do on the host. See :func:`call_digest`."""

        return call_digest(self.target, self.arguments)

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "target": self.target.to_dict(),
            "arguments": self.arguments,
            "depends_on": list(self.depends_on),
        }
