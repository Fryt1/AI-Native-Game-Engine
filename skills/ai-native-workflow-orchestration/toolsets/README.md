# Project Toolsets

Agent-facing contracts for the project-owned Toolsets published to the Project Tool Registry.

These documents are not a second Registry, not an MCP catalog, and not parsed as a Workflow.

## Current Toolsets

- [`ue5-editor/TOOLSET.md`](ue5-editor/TOOLSET.md) — `ue5.editor`
- [`blender-editor/TOOLSET.md`](blender-editor/TOOLSET.md) — `blender.editor`
- [`transfer-assetsbridge/TOOLSET.md`](transfer-assetsbridge/TOOLSET.md) — `transfer.assetsbridge`
- [`transfer-direct/TOOLSET.md`](transfer-direct/TOOLSET.md) — `transfer.direct`
- [`workflow-validation/TOOLSET.md`](workflow-validation/TOOLSET.md) — `validation.workflow`

The Agent queries these project Toolsets only when it needs a project-owned `ToolCall`. Host-native Blender and UE5 capabilities exposed by MCP are queried by the Agent MCP Client and remain direct `McpCall` entries in WorkflowPlan. Generators such as ComfyUI are either ordinary project Toolsets here or direct MCP Server tools; they are not a separate generator seam.

A Tool has no permanent execution, observation, or validation role. The current call records `usage: execute | observe | verify | report` for audit. Complex checkers remain ordinary project Tools in the same Registry.

## License

MIT © [Fry](https://github.com/Fryt1). See [LICENSE](../../../LICENSE).
