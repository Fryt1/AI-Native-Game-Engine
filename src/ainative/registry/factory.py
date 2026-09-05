from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from ainative.orchestration.contracts.tools import (
    ToolDefinition,
    ToolExecutionKind,
    ToolsetDefinition,
)


def normalize_tool_name(operation: str) -> str:
    value = operation.strip().replace("-", "_").replace(" ", "_")
    value = re.sub(r"[^a-zA-Z0-9_.]+", "_", value)
    return value.strip("_").lower()


def tool_id_for(toolset_id: str, operation: str) -> str:
    return f"{toolset_id}.{normalize_tool_name(operation)}"


def toolset_from_operations(
    *,
    toolset_id: str,
    provider_id: str,
    execution_kind: ToolExecutionKind,
    operations: Mapping[str, str] | tuple[str, ...],
    title: str = "",
    description: str = "",
    metadata: dict[str, Any] | None = None,
    input_schemas: Mapping[str, dict[str, Any]] | None = None,
    output_schemas: Mapping[str, dict[str, Any]] | None = None,
) -> ToolsetDefinition:
    operation_descriptions = (
        dict(operations)
        if isinstance(operations, Mapping)
        else {operation: "" for operation in operations}
    )
    tools_by_id: dict[str, ToolDefinition] = {}
    for operation, tool_description in operation_descriptions.items():
        tool_id = tool_id_for(toolset_id, operation)
        tools_by_id.setdefault(
            tool_id,
            ToolDefinition(
                tool_id=tool_id,
                operation=operation,
                execution_kind=execution_kind,
                description=tool_description,
                input_schema=dict((input_schemas or {}).get(operation, {"type": "object"})),
                output_schema=dict((output_schemas or {}).get(operation, {"type": "object"})),
            ),
        )
    tools = tuple(tools_by_id.values())
    return ToolsetDefinition(
        toolset_id=toolset_id,
        provider_id=provider_id,
        title=title,
        description=description,
        tools=tools,
        metadata=dict(metadata or {}),
    )
