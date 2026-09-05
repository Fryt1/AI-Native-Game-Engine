# UE5 Editor Toolset

## Toolset ID

```text
ue5.editor
```

Owns UE5 Tools and execution details:

```text
execution/python.py
    UnrealEditor.exe / UnrealEditor-Cmd.exe Python execution

execution/command.py
    injected project-specific command surface

execution/bridge_entry.py
    UE5-side Python entry used by Tool implementations
```

Publishes Actor, Level, and asset operations through the unified Toolset Registry. Agent-facing contract: `skills/ai-native-workflow-orchestration/toolsets/ue5-editor/TOOLSET.md`.
