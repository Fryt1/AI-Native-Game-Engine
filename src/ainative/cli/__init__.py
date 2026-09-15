"""The Agent-facing acceptance-loop CLI.

This package is where an Agent hands Python its own Workflow and its own reported
results, and gets back a deterministic Stage verdict. It executes nothing: the
Agent performs every call itself through its own MCP client, and this surface
only records evidence and evaluates the frozen checklists.
"""

from .commands import main

__all__ = ["main"]
