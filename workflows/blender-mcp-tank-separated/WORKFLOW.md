# Blender MCP: Separated Tank

<!-- provenance: this Workflow Definition implements the shared guidance below. When the guidance changes, review and update this file; do not let the two diverge. -->

- **Shared guidance:** [`host-operation.md`](../../skills/ai-native-workflow-orchestration/workflows/host-operation.md) (route: `host_operation`)

## Intent

Build a stylized game-ready tank in Blender through the installed Blender MCP
bridge. Every functional tank part remains a separate named object and is
organized into semantic collections.

## Plan

```text
inspect current Blender scene
    → execute one composite build Tool through Blender MCP
    → save .blend and render a preview
    → read back object names, collections, and separation invariants
    → machine acceptance
    → optional human visual acceptance
```

The composite operation is sent through the direct `McpCall` path. It is not
copied into the Project Tool Registry for this experiment.
