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

These are phase goals, not fixed Tool Calls. A WORKFLOW node may contain multiple
STAGE leaves, and optional phases may be omitted when their contract is already
satisfied.

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

See `SKILL.md` → "Workflow rules". The rule is the same for every lifecycle and is
stated once there; this document adds only what is specific to an asset edit.
