# UE5 Editor Toolset

## Toolset ID

```text
ue5.editor
```

This package owns the UE5 Tools and their execution details:

```text
execution/python.py
    UnrealEditor.exe / UnrealEditor-Cmd.exe Python execution

execution/command.py
    injected project-specific command surface

execution/bridge_entry.py
    UE5-side Python entry used by the Tool implementations
```

The Toolset publishes Actor, Level, and verified asset operations through the
unified Toolset Registry. The Agent-facing contract lives in
`D:\work\AI-Native-Game-Engine\skills\ai-native-workflow-orchestration\toolsets\ue5-editor\TOOLSET.md`.
