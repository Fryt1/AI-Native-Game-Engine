# Project Toolsets

Documents project-owned Toolsets published to the Project Tool Registry. Not a second Registry, not an MCP catalog, and not parsed as a Workflow.

## Current Toolsets

- `ue5-editor/TOOLSET.md` — `ue5.editor`
- `blender-editor/TOOLSET.md` — `blender.editor`
- `transfer-assetsbridge/TOOLSET.md` — `transfer.assetsbridge`
- `transfer-direct/TOOLSET.md` — `transfer.direct`
- `artifact-provider/TOOLSET.md` — `artifact.<provider_id>`
- `workflow-validation/TOOLSET.md` — `validation.workflow`

The Agent queries these project Toolsets only when it needs a project-owned `ToolCall`. Host-native Blender and UE5 capabilities exposed by MCP are queried by the Agent MCP Client and remain direct `McpCall` entries in WorkflowPlan.

A Tool has no permanent execution, observation, or validation role. The current call records `usage: execute | observe | verify | report` for audit. Complex checkers remain ordinary project Tools in the same Registry.
