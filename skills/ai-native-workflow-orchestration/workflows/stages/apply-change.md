# Stage Contract: Apply Host Change

## Stage ID

```text
stage.apply_change
```

## Purpose

Execute the requested mutation against the resolved host context.

## Inputs

```text
resolved context
before-state snapshot when required
mutation intent
typed operation parameters
Agent-selected host Tool Call
```

## Current Tool examples

```text
blender.editor
    translate-active
    set-location
    set-scale
    rename-active
    create-cube
    configure-scene-unreal
    import-glb
    export-glb

ue5.editor
    resolve_actor
    read_actor_transform
    set_actor_transform
    create_actor
    create_level_from_template
    inspect_level
    save_level
```

The Agent must use the exact operation and Tool ID published by the live
Toolset Registry. Dashed aliases are normalized only when the selected Tool
explicitly publishes that operation; Python does not invent an alias.

## Gate

- operation parameters are complete and typed
- mutation is authorized by the task
- destructive changes have required confirmation
- selected Tool can operate in the current host context

## Outputs

```text
changed host state
operation result
changed fields
operation evidence
```

## Failure / Resume

An operation error stops this local goal. Preserve the ExecutionResult and evidence;
retry the selected Tool or author a new plan revision. Do not switch to a
different mutation method silently.

## Dynamic checklist composition

```text
stage_kind: change
knowledge: selected object plus modify/configure/create knowledge
```

Execution checklist must resolve scope, before-state, authorization, recovery, and operation parameters.

Acceptance checklist must prove that requested host state is independently readable and matches the target. Required results need
structured evidence; unresolved facts remain `unknown` and do not complete the
Stage.
