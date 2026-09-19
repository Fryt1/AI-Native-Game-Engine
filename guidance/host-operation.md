# Workflow Guidance: Host Operation

## Purpose

Inspect, create, modify, save, or publish a host-owned object, Scene, asset, or
project state without requiring a cross-host transfer for the requested result.
This includes moving an Unreal Actor in a Level and changing an object in a
Blender Scene.

## Inputs

```text
host and project context
object / Scene / asset reference
operation intent and parameters
confirmation policy
required read-back fields
publish policy
```

## Output Contract

```text
operation result
changed object / asset reference
published file / package when requested
before / after evidence when required
validation result
resume pointer on failure
```

## Recommended lifecycle

The following is a recommended shape, not a mandatory five-node script. The
Agent includes only the nodes required by the task:

```text
resolve context when the target is ambiguous
    ↓
read current state when the operation needs current values or a before/after proof
    ↓
apply the requested host operation when the task changes state
    ↓
publish / save when the user requests persistence
    ↓
validate the declared result when read-back or evidence is required
```

Each local goal becomes a Stage. Each Stage contains the exact MCP calls the
Agent selected, named by `target.owner` (the MCP server) and `target.name` (the
tool on that server). A Stage is not required to have one call, and a Workflow
example must not cause the Agent to invent unused calls.

## Conditional Stage guidance

Each of these is optional. Read it when its condition holds; otherwise omit it.

```text
resolve context
    when project, Level, Scene, object, or asset identity is ambiguous

read state
    when the operation depends on current state, or needs before/after evidence
    example calls: a ue5 call named read_actor_transform,
                   a blender call named inspect-active

apply change
    when the task mutates host state
    example calls: a ue5 call named set_actor_transform,
                   blender calls named translate-active or create-cube

publish result
    only when persistence or publication is part of the task
    example calls: a ue5 call named save_level,
                   a blender call named save-mainfile
    A Stage label never implies a hidden save.

validate result
    when the task requires read-back, evidence, or an independently checkable
    result; the Agent selects the appropriate read or validation MCP call
```

These names illustrate the shape of the calls, not a guarantee that a server
publishes that exact tool. Confirm the real `target.name` against the running
server before declaring the call.

## MCP server guidance

```text
ue5       UE5 host MCP server
blender   Blender host MCP server
comfyui   ComfyUI host MCP server
```

The tool names used above are examples of the operations each Stage performs.
They are not a promise that a given server publishes that exact tool: confirm the
real `target.name` against the running server, and load
`docs/DEPENDENCIES.md` for that server's prerequisites.

CLI, Add-on, Editor Python, command execution, and open-editor connection are
implementation details of the MCP server behind the selected call. They are not
additional Workflow Stages.

## Example: move a UE5 Actor

One valid Agent-authored Workflow is:

```text
Stage: read target state
    → owner: ue5 / name: read_actor_transform

Stage: apply transform
    → owner: ue5 / name: set_actor_transform

Stage: save Level (only if requested)
    → owner: ue5 / name: save_level

Stage: read back transform
    → owner: ue5 / name: read_actor_transform
```

A read-only request may contain only the read Stage. A task that changes an
Actor but does not request saving may omit the publish Stage.

## Example: create a UE5 Level from a template

There is no existing Actor state to read first, so the Agent may choose:

```text
Stage: create Level
    → owner: ue5 / name: create_level_from_template

Stage: verify Level
    → owner: ue5 / name: inspect_level
```

The create call receives the declared template, target, and expected default
objects as arguments. The validation call independently reads the result.

## Failure / recovery

- unresolved target → Agent adds or retries a context-resolution call
- unreadable state → retry the selected read call
- operation failure → retry or re-plan the apply Stage
- save failure → retry the selected publish call
- read-back failure → retry or re-plan the validation Stage

Preserve all completed ExecutionResults and evidence. If the Workflow itself is wrong,
create a new Workflow revision instead of editing the running Workflow.

## Dynamic Stage checklist rule

See `SKILL.md` → "Workflow rules". The rule is the same for every lifecycle and is
stated once there; this document adds only what is specific to a host operation.
