"""Project Tool CLI entrypoints used by Agents.

These modules build a RuntimeContext from JSON configuration, resolve an exact
ToolCall through the Project Tool Registry, execute the Project Tool, and print
a structured ExecutionResult. They are the Agent-facing CLI surface for our
project-owned Tools; MCP Servers remain configured directly on the Agent.
"""

from .runner import run_tool_call

__all__ = ["run_tool_call"]
