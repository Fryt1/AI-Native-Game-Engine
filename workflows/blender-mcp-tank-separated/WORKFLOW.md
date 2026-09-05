# Blender MCP: Separated Tank

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
