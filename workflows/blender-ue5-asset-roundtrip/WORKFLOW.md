# Blender -> UE5 Asset Roundtrip

This is a reusable Workflow Definition. It is deliberately a recommendation and
constraint set, not a fixed five-step script. The Agent instantiates a
WorkflowPlan after reading the task, current state, project Tool Registry, and
MCP Server tool lists.

## Intent

Prepare an asset in Blender, transfer it through the selected backend, configure
it in UE5, and prove the required relations and saved state.

## Required invariants

- The selected transfer backend must be explicit.
- A change Stage must freeze execution and acceptance checklists before side effects.
- Blender/UE5 MCP calls remain direct `McpCall` entries.
- AssetsBridge and validation remain project-owned `ToolCall` entries.
- A Tool or MCP success response is not semantic proof without read-back or structured evidence.

## Allowed execution sources

```text
MCP:
    Blender scene inspection and native UE5 editor operations

Project Tools:
    transfer.assetsbridge.*
    transfer.direct.*
    validation.workflow.*
    blender.workflow.*
    ue5.workflow.*
```

See `plan.template.yaml` for the stable plan shape.
