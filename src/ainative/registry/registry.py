from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ainative.orchestration.contracts.tools import (
    ToolCall,
    ToolDefinition,
    ToolsetDefinition,
)


class ToolResolutionError(LookupError):
    """A project Toolset, Tool, provider, or ready implementation is unavailable."""


@dataclass(frozen=True, slots=True)
class ResolvedTool:
    provider: Any
    toolset: ToolsetDefinition
    tool: ToolDefinition


class ToolsetRegistry:
    """Registry for project-owned Toolsets and Tools.

    This registry does not contain MCP Tools. MCP calls use the Agent MCP Client
    directly. The registry only indexes project-owned implementations such as
    AssetsBridge, validation, script runners, and ComfyUI workflow runners.
    """

    def __init__(self, providers: dict[str, Any] | None = None) -> None:
        self._providers: dict[str, Any] = {}
        for provider_id, provider in (providers or {}).items():
            self.register_provider(provider_id, provider)

    def register_provider(self, provider_id: str, provider: Any) -> None:
        if not provider_id:
            raise ValueError("Toolset provider id is required")
        self._providers[provider_id] = provider

    def unregister_provider(self, provider_id: str) -> None:
        self._providers.pop(provider_id, None)

    def _provider_aliases(self, provider_id: str, provider: Any) -> set[str]:
        aliases = {provider_id}
        for name in ("executor_id", "backend_id", "provider_id", "validator_id", "host_id"):
            value = getattr(provider, name, None)
            if value:
                aliases.add(str(value))
        return aliases

    def _published(self) -> tuple[tuple[str, Any, ToolsetDefinition], ...]:
        published: list[tuple[str, Any, ToolsetDefinition]] = []
        seen: set[tuple[int, str]] = set()
        for registered_id, provider in self._providers.items():
            publisher = getattr(provider, "toolsets", None)
            if not callable(publisher):
                continue
            aliases = self._provider_aliases(registered_id, provider)
            for toolset in publisher():
                if toolset.provider_id not in aliases:
                    continue
                key = (id(provider), toolset.toolset_id)
                if key in seen:
                    continue
                seen.add(key)
                published.append((registered_id, provider, toolset))
        return tuple(published)

    def list_toolsets(self) -> tuple[ToolsetDefinition, ...]:
        return tuple(toolset for _, _, toolset in self._published())

    def search_toolsets(self, query: str, limit: int = 20) -> tuple[ToolsetDefinition, ...]:
        tokens = self._tokens(query)
        scored: list[tuple[int, str, ToolsetDefinition]] = []
        for toolset in self.list_toolsets():
            haystack = self._search_text(toolset.toolset_id, toolset.title, toolset.description)
            score = sum(token in haystack for token in tokens)
            if not tokens or score:
                scored.append((score, toolset.toolset_id, toolset))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return tuple(toolset for _, _, toolset in scored[:limit])

    def describe_toolset(self, toolset_id: str) -> ToolsetDefinition:
        matches = tuple(toolset for _, _, toolset in self._published() if toolset.toolset_id == toolset_id)
        if len(matches) != 1:
            raise ToolResolutionError(f"Toolset is not uniquely available: {toolset_id}")
        return matches[0]

    def list_tools(self, toolset_id: str) -> tuple[ToolDefinition, ...]:
        return self.describe_toolset(toolset_id).tools

    def search_tools(self, toolset_id: str, query: str, limit: int = 20) -> tuple[ToolDefinition, ...]:
        tokens = self._tokens(query)
        scored: list[tuple[int, str, ToolDefinition]] = []
        for tool in self.list_tools(toolset_id):
            haystack = self._search_text(tool.tool_id, tool.operation, tool.description)
            score = sum(token in haystack for token in tokens)
            if not tokens or score:
                scored.append((score, tool.tool_id, tool))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return tuple(tool for _, _, tool in scored[:limit])

    def describe_tool(self, toolset_id: str, tool_id: str) -> ToolDefinition:
        toolset = self.describe_toolset(toolset_id)
        tool = toolset.find_tool(tool_id=tool_id)
        if tool is None:
            raise ToolResolutionError(f"Tool is not available in {toolset_id}: {tool_id}")
        return tool

    def resolve_call(self, call: ToolCall) -> ResolvedTool:
        """Resolve one exact project ToolCall selected by the Agent."""

        matches: list[ResolvedTool] = []
        for _, provider, toolset in self._published():
            if toolset.toolset_id != call.toolset_id:
                continue
            tool = toolset.find_tool(tool_id=call.tool_id)
            if tool is not None:
                matches.append(ResolvedTool(provider=provider, toolset=toolset, tool=tool))
        if len(matches) != 1:
            raise ToolResolutionError(f"Selected Tool is not uniquely available: {call.toolset_id}/{call.tool_id}")
        self._check_ready(matches[0])
        return matches[0]

    @staticmethod
    def _check_ready(resolved: ResolvedTool) -> None:
        readiness = getattr(resolved.provider, "is_ready", None)
        if callable(readiness) and not readiness():
            raise ToolResolutionError(
                f"Tool provider is not ready: {resolved.toolset.toolset_id}/{resolved.tool.tool_id}"
            )

    @staticmethod
    def _tokens(value: str) -> tuple[str, ...]:
        normalized = value.lower().replace(".", " ").replace("_", " ").replace("-", " ")
        return tuple(token for token in normalized.split() if token)

    @staticmethod
    def _search_text(*values: str) -> str:
        return " ".join(values).lower().replace(".", " ").replace("_", " ").replace("-", " ")
