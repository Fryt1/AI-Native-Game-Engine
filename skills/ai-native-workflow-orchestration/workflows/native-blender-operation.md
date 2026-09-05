# Workflow Guidance: Native Blender Operation

## Route Family

```text
host_operation
```

## Purpose

Inspect or modify a Blender-owned object, Scene, or asset without a cross-host
transfer.

## Recommended lifecycle

```text
resolve the Scene / object when needed
    ↓
inspect current state when needed
    ↓
perform the requested Blender operation
    ↓
save when requested
    ↓
read back or validate when required
```

The Agent may omit any optional part or add more local Stages. The examples are
not a fixed execution script.

## Call surface choice

```text
Blender Add-on
    current UI Selection / Mode / interactive Scene context

Blender CLI + Python
    explicit .blend files and deterministic background operations
```

The call surface is an implementation detail of the selected
`blender.editor` Tool. It does not change the Workflow or create another Route.

## Tool planning rule

The Agent queries `blender.editor`, selects exact Tool functions, writes them in
the WorkflowPlan, and calls them one at a time. A save or validation action is
never inferred from a Stage name.

## Failure / recovery

Preserve the source file, operation result, and evidence. Retry the selected
Tool or author a new plan revision if the target or operation interpretation
was wrong.

## Dynamic Stage checklist rule

For each selected Stage, the Agent loads the relevant `knowledge/stage-kinds`,
`knowledge/objects`, and `knowledge/operations` documents, then freezes an
execution checklist and an acceptance checklist in the WorkflowPlan. Checklist
knowledge does not name Tools; the final plan stores exact Tool Calls from the
live Registry.

A Tool returning `succeeded` is call-level evidence only. The Stage completes
through evidence-backed `ExecutionItemResult` and `CheckResult` aggregation.
