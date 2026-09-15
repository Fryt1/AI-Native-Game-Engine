# Workflow Policy: Asset Edit

This policy describes an asset-edit lifecycle. A concrete Workflow such as
`asset-roundtrip.md` supplies host-pair constraints; the Agent writes the actual
Workflow.

## Purpose

Change an existing asset while making the edit representation, preservation
policy, publication, and validation explicit.

## Recommended macro flow

```text
prepare asset context when needed
    ↓
make the asset available to the edit host when needed
    ↓
perform the requested edit
    ↓
return or publish the result when requested
    ↓
validate the declared output and preserved relations
```

These are phase goals, not fixed Tool Calls. A Step may contain multiple Stages,
and optional phases may be omitted when their contract is already satisfied.

## Stage contract requirements

Every Stage selected by the Agent should declare:

```text
local purpose
inputs
outputs
gate
Agent-selected host MCP calls
validation
evidence
failure / recovery
```

The Stage declares the exact MCP calls the Agent will make; it does not invent raw
host API calls, and Python resolves none of them.

## Completion

The Agent completes the Workflow only after every required validation Stage in
its Workflow passes. Call and Stage results remain available for the next Stage or
for re-planning.

## Failure / recovery

Preserve all produced artifacts and evidence. Resume the failed selected call
when the Workflow remains valid. Supersede and replace the Workflow when the call
selection or Stage contract is wrong.

## Dynamic Stage checklist rule

For each selected Stage, the Agent composes an execution checklist and an
acceptance checklist from the Stage kind, the processing object, the operation
type, the current facts, and the user's requirements, then freezes both in the
Workflow. The Agent supplies that domain competence; the checklist does not
name calls, and the final Workflow stores the exact MCP calls the Agent selected.

A call returning `succeeded` is call-level evidence only. The Stage completes
through evidence-backed `ExecutionItemResult` and `CheckResult` aggregation.
