# Workflow Guidance: Host Operation

## Route Family

```text
host_operation
```

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

The following is a recommended shape, not a mandatory five-Step script. The
Agent includes only the Steps and Stages required by the task:

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

Each local goal becomes a Stage. Each Stage contains the exact Tool Calls the
Agent selected from the relevant Toolset. A Stage is not required to have one
Tool, and a Workflow example must not cause the Agent to invent unused calls.

## Conditional Stage guidance

### Resolve context

Read `stages/resolve-context.md` when project, Level, Scene, object, or asset
identity is ambiguous. If the request already identifies the target, the Agent
may omit this Stage or use a small explicit resolution Tool.

### Read state

Read `stages/read-state.md` when the operation depends on current state or
requires before/after evidence. Examples include
`ue5.editor.read_actor_transform` and `blender.editor.inspect-active`.

### Apply change

Read `stages/apply-change.md` when the task mutates host state. Examples include
`ue5.editor.set_actor_transform`, `blender.editor.translate-active`, and
`blender.editor.create-cube`.

### Publish result

Read `stages/publish-result.md` only when persistence or publication is part of
the task. Saving is an explicit Tool Call such as `ue5.editor.save_level` or
`blender.editor.save-mainfile`; a Stage label never implies a hidden save.

### Validate result

Read `stages/validate-result.md` when the task requires read-back, evidence, or
an independently checkable result. The Agent selects the appropriate read or
validation Tool.

## Toolset guidance

```text
ue5.editor       UE5 host Tools
blender.editor   Blender host Tools
```

CLI, Add-on, Editor Python, command execution, and open-editor connection are
implementation details of the selected Tool. They are not additional Workflow
Stages.

## Example: move a UE5 Actor

One valid Agent-authored plan is:

```text
Stage: read target state
    → ue5.editor.read_actor_transform

Stage: apply transform
    → ue5.editor.set_actor_transform

Stage: save Level (only if requested)
    → ue5.editor.save_level

Stage: read back transform
    → ue5.editor.read_actor_transform
```

A read-only request may contain only the read Stage. A task that changes an
Actor but does not request saving may omit the publish Stage.

## Example: create a UE5 Level from a template

There is no existing Actor state to read first, so the Agent may choose:

```text
Stage: create Level
    → ue5.editor.create_level_from_template

Stage: verify Level
    → ue5.editor.inspect_level
```

The create Tool receives the declared template, target, and expected default
objects as arguments. The validation Tool independently reads the result.

## Failure / recovery

- unresolved target → Agent adds or retries a context-resolution Tool
- unreadable state → retry the selected read Tool
- operation failure → retry or re-plan the apply Stage
- save failure → retry the selected publish Tool
- read-back failure → retry or re-plan the validation Stage

Preserve all completed ExecutionResults and evidence. If the plan itself is wrong,
create a new plan revision instead of editing the running plan.

## Dynamic Stage checklist rule

For each selected Stage, the Agent loads the relevant `knowledge/stage-kinds`,
`knowledge/objects`, and `knowledge/operations` documents, then freezes an
execution checklist and an acceptance checklist in the WorkflowPlan. Checklist
knowledge does not name Tools; the final plan stores exact Tool Calls from the
live Registry.

A Tool returning `succeeded` is call-level evidence only. The Stage completes
through evidence-backed `ExecutionItemResult` and `CheckResult` aggregation.
