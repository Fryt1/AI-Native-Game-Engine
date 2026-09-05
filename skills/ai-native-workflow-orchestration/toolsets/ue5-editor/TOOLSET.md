# Toolset: UE5 Editor

## Toolset ID

```text
ue5.editor
```

## Publisher / implementation

The Toolset is published by the configured UE5 host owner. Current concrete
publishers include the UE5 Python process executor and the project-specific UE5
command executor. Their launch and connection details are implementation
internals of the Tool; they are not separate Workflow or Stage types.

## Registered Tools

```text
list_actors
create_actor
create_level_from_template
inspect_level
resolve_actor / resolve-actor
read_actor_transform / read-actor-transform
set_actor_transform / set-actor-transform
save_level / save-level
```

The UE5 Python transfer operations `export_asset` and `import_asset` are
published through the transfer Toolset when a transfer Backend uses them; they
do not turn asset transfer into a host-operation Workflow.

## Execution surfaces currently implemented

```text
UnrealEditor-Cmd.exe + -ExecutePythonScript
    headless / commandlet-style Tool execution

UnrealEditor.exe + -ExecutePythonScript
    visible Editor Tool execution when UI/editor context is required

project-specific command executor
    injected command surface for operations that do not use the Python entry
    script
```

The current repository implementation runs one Tool operation through the
configured executor and reads its structured result. It does not yet connect to
an already-open UE5 Editor through Python Remote Execution. Remote Execution is
a future execution-surface enhancement, not a Toolset or Workflow concept.

## Boundary

This Toolset currently covers Actor Transform operations, Level template
provisioning, Level inspection/save, and the verified bridge operations. It does
not claim arbitrary Material Graph, animation, Blueprint Graph, or production
project editing.
