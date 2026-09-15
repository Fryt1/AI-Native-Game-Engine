# Workflow Guidance: Native Blender Operation

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

The call surface is an implementation detail of the selected MCP call on the
`blender` server. It does not change the Workflow or create another Route.

## Tool planning rule

The Agent selects exact MCP calls on the `blender` server, naming the server as
`target.owner` and the tool on it as `target.name` — for example an
`inspect-active` read call, a `translate-active` mutation call, or a
`save-mainfile` publish call. These names are examples of the operations, not a
guarantee that the running server publishes them; confirm the real tool before
declaring the call.

The Agent writes those calls in the Workflow and invokes them one at a time
through its own MCP client. Python validates the Workflow's structure only and never
guesses an API. A save or validation action is never inferred from a Stage name.

## Failure / recovery

Preserve the source file, operation result, and evidence. Retry the selected
MCP call or author a new Workflow revision if the target or operation interpretation
was wrong.

## Dynamic Stage checklist rule

For each selected Stage, the Agent composes an execution checklist and an
acceptance checklist from the Stage kind, the processing object, the operation
type, the current facts, and the user's requirements, then freezes both in the
Workflow. The Agent supplies that domain competence; the checklist does not
name calls, and the final Workflow stores the exact MCP calls the Agent selected.

A call returning `succeeded` is call-level evidence only. The Stage completes
through evidence-backed `ExecutionItemResult` and `CheckResult` aggregation.
