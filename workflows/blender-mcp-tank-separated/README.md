# Blender MCP: Separated Tank

Experimental Workflow Definition for building a stylized, game-ready tank in Blender through the installed Blender MCP bridge.

It is not a published, promoted Workflow: the composite build operation is sent through the direct `McpCall` path and is not copied into the Project Tool Registry for this experiment.

## Intent

Every functional tank part remains a separate named object and is organized into semantic collections.

## Plan

```text
inspect current Blender scene
    → execute one composite build Tool through Blender MCP
    → save .blend and render a preview
    → read back object names, collections, and separation invariants
    → machine acceptance
    → optional human visual acceptance
```

See `WORKFLOW.md`, `requirements.yaml`, and `plan.template.yaml` in this directory.

## License

MIT © [Fry](https://github.com/Fryt1). See [LICENSE](../../LICENSE).
