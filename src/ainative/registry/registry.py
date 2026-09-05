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
        self._check_arguments(call, matches[0].tool)
        return matches[0]

    def validate_output(
        self,
        call: ToolCall,
        outputs: dict[str, Any],
        tool: ToolDefinition | None = None,
    ) -> None:
        """Validate a Tool output without re-checking provider readiness.

        A caller that already opened a plan may pass the ToolDefinition captured
        at plan start; this keeps result validation stable if a provider changes
        its published set after the external process has finished.
        """

        if tool is None:
            matches = [
                candidate
                for _, _, toolset in self._published()
                if toolset.toolset_id == call.toolset_id
                for candidate in toolset.tools
                if candidate.tool_id == call.tool_id
            ]
            if len(matches) != 1:
                raise ToolResolutionError(f"Selected Tool is not uniquely available: {call.toolset_id}/{call.tool_id}")
            tool = matches[0]
        error = self._schema_error(outputs, tool.output_schema or {"type": "object"}, "$outputs")
        if error:
            raise ToolResolutionError(f"Invalid output for {call.toolset_id}/{call.tool_id}: {error}")

    @staticmethod
    def _check_ready(resolved: ResolvedTool) -> None:
        readiness = getattr(resolved.provider, "is_ready", None)
        if callable(readiness) and not readiness():
            raise ToolResolutionError(
                f"Tool provider is not ready: {resolved.toolset.toolset_id}/{resolved.tool.tool_id}"
            )


    @staticmethod
    def _check_arguments(call: ToolCall, tool: ToolDefinition) -> None:
        """Validate the small JSON-schema subset used by project Tool contracts."""

        schema = tool.input_schema or {"type": "object"}
        error = ToolsetRegistry._schema_error(call.arguments, schema, "$arguments")
        if error:
            raise ToolResolutionError(f"Invalid arguments for {call.toolset_id}/{call.tool_id}: {error}")

    @classmethod
    def _schema_error(cls, value: Any, schema: dict[str, Any], path: str) -> str | None:
        expected_type = schema.get("type")
        if expected_type == "object":
            if not isinstance(value, dict):
                return f"{path} must be an object"
            for key in schema.get("required", []):
                if key not in value:
                    return f"{path}.{key} is required"
            properties = schema.get("properties", {})
            for key, child_schema in properties.items():
                if key in value:
                    error = cls._schema_error(value[key], child_schema, f"{path}.{key}")
                    if error:
                        return error
        elif expected_type == "array":
            if not isinstance(value, (list, tuple)):
                return f"{path} must be an array"
            if "minItems" in schema and len(value) < int(schema["minItems"]):
                return f"{path} must contain at least {schema['minItems']} items"
            if "maxItems" in schema and len(value) > int(schema["maxItems"]):
                return f"{path} must contain at most {schema['maxItems']} items"
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                for index, item in enumerate(value):
                    error = cls._schema_error(item, item_schema, f"{path}[{index}]")
                    if error:
                        return error
        elif expected_type == "string" and not isinstance(value, str):
            return f"{path} must be a string"
        elif expected_type == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            return f"{path} must be a number"
        elif expected_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            return f"{path} must be an integer"
        elif expected_type == "boolean" and not isinstance(value, bool):
            return f"{path} must be a boolean"
        if "enum" in schema and value not in schema["enum"]:
            return f"{path} must be one of {schema['enum']}"
        return None

    @staticmethod
    def _tokens(value: str) -> tuple[str, ...]:
        normalized = value.lower().replace(".", " ").replace("_", " ").replace("-", " ")
        return tuple(token for token in normalized.split() if token)

    @staticmethod
    def _search_text(*values: str) -> str:
        return " ".join(values).lower().replace(".", " ").replace("_", " ").replace("-", " ")
