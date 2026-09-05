# Blender Editor Toolset

## Toolset ID

```text
blender.editor
```

Owns Blender Tools and both call surfaces:

```text
execution/cli.py
    Blender CLI + Python process execution

execution/addon.py
    Add-on surface for current Blender context

execution/blender_addon/
    AI Native bpy operations used by the CLI and Add-on
```

Publishes Scene, object, asset, and file operations through the unified Toolset Registry. Agent-facing contract: `skills/ai-native-workflow-orchestration/toolsets/blender-editor/TOOLSET.md`.
