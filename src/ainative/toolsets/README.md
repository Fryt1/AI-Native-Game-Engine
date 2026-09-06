# Runtime Project Toolsets

Each directory in this folder is one concrete maintenance unit for capabilities we own. The Project Tool Registry discovers these Toolsets and resolves exact ToolCalls. Direct MCP Tools do not appear here.

| Directory | Toolset ID | Owns |
|---|---|---|
| `ue5_editor/` | `ue5.editor` | UE5 local Tools and Python/command execution |
| `blender_editor/` | `blender.editor` | Blender local Tools, CLI/Add-on execution, and `bpy` operations |
| `workflow_tools/` | `*.workflow` | Script-backed reusable Workflow Tools |
| `transfer_assetsbridge/` | `transfer.assetsbridge` | AssetsBridge Backend, connectors, protocol, and endpoint |
| `transfer_direct/` | `transfer.direct` | Explicit file-transfer Backend and I/O |
| `validation_workflow/` | `validation.workflow` | Workflow validation Tools |
| `ports/` | — | Shared project Toolset interfaces |

Generators such as ComfyUI are not a separate Toolset category. They register as ordinary project Toolsets (for example under their own `Toolset ID`) or are reached as direct MCP Server tools; there is no generator-specific seam.

When changing one Toolset, update its implementation, its Agent-facing contract at `skills/ai-native-workflow-orchestration/toolsets/<toolset>/TOOLSET.md`, and the matching tests together.
